from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd


# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
)

OUTPUT_DATA_DIR = (
    PROJECT_ROOT
    / "output"
    / "data"
)

OUTPUT_FIGURE_DIR = (
    PROJECT_ROOT
    / "output"
    / "figures"
)

OUTPUT_CHAIN_RECORDS_CSV = (
    OUTPUT_DATA_DIR
    / "figure03_primary_chain_records.csv"
)

OUTPUT_RFC_SUMMARY_CSV = (
    OUTPUT_DATA_DIR
    / "figure03_primary_chain_rfc_summary.csv"
)

OUTPUT_YEAR_SUMMARY_CSV = (
    OUTPUT_DATA_DIR
    / "figure03_primary_chain_year_summary.csv"
)

OUTPUT_REJECTED_CANDIDATES_CSV = (
    OUTPUT_DATA_DIR
    / "figure03_primary_chain_rejected_candidates.csv"
)

OUTPUT_EXCLUDED_CSV = (
    OUTPUT_DATA_DIR
    / "figure03_primary_chain_excluded_records.csv"
)

OUTPUT_FIGURE_PNG = (
    OUTPUT_FIGURE_DIR
    / "figure03_primary_predecessor_chain_2013_2025.png"
)


# =============================================================================
# Settings
# =============================================================================

START_YEAR = 2013
END_YEAR = 2025

MAX_CHAIN_DEPTH = 30
MAX_DEVELOPMENT_DAYS = 20 * 365

# A predecessor must reach at least this score to be selected.
# Lowering it includes more uncertain predecessors.
# Raising it produces shorter, more conservative chains.
MIN_PREDECESSOR_SCORE = 0.30

RFC_DOCUMENT_TYPE = (
    "/api/v1/name/doctypename/rfc/"
)

BECAME_RFC_RELATIONSHIP = (
    "/api/v1/name/docrelationshipname/became_rfc/"
)

REPLACES_RELATIONSHIP = (
    "/api/v1/name/docrelationshipname/replaces/"
)

POSTED_SUBMISSION_STATE = (
    "/api/v1/name/draftsubmissionstatename/posted/"
)


# =============================================================================
# Data structures
# =============================================================================

@dataclass(frozen=True)
class DraftRecord:
    uri: str
    name: str
    title: str
    latest_rev: str
    document_time: pd.Timestamp | pd.NaT
    first_submission: pd.Timestamp | pd.NaT


@dataclass(frozen=True)
class CandidateScore:
    source_uri: str
    target_uri: str
    source_name: str
    target_name: str
    title_similarity: float
    name_similarity: float
    token_similarity: float
    date_score: float
    total_score: float


# =============================================================================
# Utility functions
# =============================================================================

def normalise_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    text = str(value).lower()

    text = re.sub(
        r"^draft-(ietf|irtf)-[a-z0-9]+-",
        "",
        text,
    )

    text = re.sub(
        r"^draft-[a-z0-9]+-",
        "",
        text,
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def tokenise(value: object) -> set[str]:
    text = normalise_text(value)

    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
        "protocol",
        "specification",
        "document",
        "version",
    }

    return {
        token
        for token in text.split()
        if len(token) >= 3
        and token not in stopwords
    }


def sequence_similarity(
    left: object,
    right: object,
) -> float:
    left_text = normalise_text(left)
    right_text = normalise_text(right)

    if not left_text or not right_text:
        return 0.0

    return SequenceMatcher(
        None,
        left_text,
        right_text,
    ).ratio()


def jaccard_similarity(
    left: object,
    right: object,
) -> float:
    left_tokens = tokenise(left)
    right_tokens = tokenise(right)

    if not left_tokens or not right_tokens:
        return 0.0

    union = left_tokens | right_tokens

    if not union:
        return 0.0

    return len(
        left_tokens & right_tokens
    ) / len(union)


def is_valid_timestamp(
    value: pd.Timestamp | pd.NaT,
) -> bool:
    return not pd.isna(value)


# =============================================================================
# Database checks
# =============================================================================

def check_required_tables(
    connection: sqlite3.Connection,
) -> None:
    required_tables = {
        "ietf_dt_doc_document",
        "ietf_dt_doc_docevent",
        "ietf_dt_doc_relateddocument",
        "ietf_dt_submit_submission",
    }

    existing_tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()
    }

    missing_tables = (
        required_tables - existing_tables
    )

    if missing_tables:
        raise RuntimeError(
            "Missing required tables: "
            f"{sorted(missing_tables)}"
        )


# =============================================================================
# Database loading
# =============================================================================

def load_rfc_records(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    query = """
    WITH publication_events AS (
        SELECT
            doc,
            MIN(time) AS publication_time
        FROM ietf_dt_doc_docevent
        WHERE type = 'published_rfc'
        GROUP BY doc
    )

    SELECT DISTINCT
        rfc.resource_uri AS rfc_uri,
        rfc.rfc_number,
        rfc.name AS rfc_name,
        rfc.title AS rfc_title,
        publication_events.publication_time,
        relation.source AS final_draft_uri

    FROM ietf_dt_doc_document AS rfc

    INNER JOIN publication_events
        ON publication_events.doc =
           rfc.resource_uri

    INNER JOIN ietf_dt_doc_relateddocument AS relation
        ON relation.target =
           rfc.resource_uri

    WHERE rfc.type = ?
      AND rfc.rfc_number IS NOT NULL
      AND relation.relationship = ?
      AND relation.source LIKE
          '/api/v1/doc/document/draft-%/'

    ORDER BY
        publication_events.publication_time,
        rfc.rfc_number
    """

    print(
        "Loading RFC records and final Draft mappings...",
        flush=True,
    )

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(
            RFC_DOCUMENT_TYPE,
            BECAME_RFC_RELATIONSHIP,
        ),
    )

    print(
        f"Loaded {len(dataframe):,} RFC-to-Draft mappings.",
        flush=True,
    )

    return dataframe


def load_draft_records(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    query = """
    WITH first_submissions AS (
        SELECT
            name,
            MIN(submission_date) AS first_submission
        FROM ietf_dt_submit_submission
        WHERE state = ?
        GROUP BY name
    )

    SELECT
        document.resource_uri AS draft_uri,
        document.name AS draft_name,
        document.title AS draft_title,
        document.rev AS latest_rev,
        document.time AS document_time,
        first_submissions.first_submission

    FROM ietf_dt_doc_document AS document

    LEFT JOIN first_submissions
        ON first_submissions.name =
           document.name

    WHERE document.resource_uri LIKE
          '/api/v1/doc/document/draft-%/'
    """

    print(
        "Loading Draft metadata and submission dates...",
        flush=True,
    )

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(
            POSTED_SUBMISSION_STATE,
        ),
    )

    print(
        f"Loaded {len(dataframe):,} Draft records.",
        flush=True,
    )

    return dataframe


def load_replaces_relationships(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    query = """
    SELECT DISTINCT
        source AS source_uri,
        target AS target_uri
    FROM ietf_dt_doc_relateddocument
    WHERE relationship = ?
      AND source LIKE
          '/api/v1/doc/document/draft-%/'
      AND target LIKE
          '/api/v1/doc/document/draft-%/'
    """

    print(
        "Loading Draft replaces relationships...",
        flush=True,
    )

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(
            REPLACES_RELATIONSHIP,
        ),
    )

    print(
        f"Loaded {len(dataframe):,} replaces relationships.",
        flush=True,
    )

    return dataframe


# =============================================================================
# Prepare loaded records
# =============================================================================

def prepare_rfc_records(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = dataframe.copy()

    dataframe["publication_time"] = pd.to_datetime(
        dataframe["publication_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["publication_year"] = (
        dataframe["publication_time"].dt.year
    )

    dataframe = dataframe.dropna(
        subset=[
            "rfc_uri",
            "rfc_number",
            "publication_time",
            "publication_year",
            "final_draft_uri",
        ]
    ).copy()

    dataframe["rfc_number"] = (
        dataframe["rfc_number"].astype(int)
    )

    dataframe["publication_year"] = (
        dataframe["publication_year"].astype(int)
    )

    dataframe = dataframe[
        dataframe["publication_year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    return dataframe.drop_duplicates(
        subset=[
            "rfc_uri",
            "final_draft_uri",
        ]
    ).copy()


def prepare_draft_records(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = dataframe.copy()

    dataframe["draft_name"] = (
        dataframe["draft_name"]
        .fillna("")
        .astype(str)
    )

    dataframe["draft_title"] = (
        dataframe["draft_title"]
        .fillna("")
        .astype(str)
    )

    dataframe["document_time"] = pd.to_datetime(
        dataframe["document_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["first_submission"] = pd.to_datetime(
        dataframe["first_submission"],
        utc=True,
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["draft_uri"]
    ).copy()

    return dataframe.drop_duplicates(
        subset=["draft_uri"]
    ).copy()


def create_draft_lookup(
    dataframe: pd.DataFrame,
) -> dict[str, DraftRecord]:
    lookup: dict[str, DraftRecord] = {}

    for row in dataframe.itertuples(
        index=False
    ):
        lookup[row.draft_uri] = DraftRecord(
            uri=row.draft_uri,
            name=row.draft_name,
            title=row.draft_title,
            latest_rev=row.latest_rev,
            document_time=row.document_time,
            first_submission=row.first_submission,
        )

    return lookup


def create_replaces_lookup(
    dataframe: pd.DataFrame,
) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = defaultdict(list)

    for row in dataframe.itertuples(
        index=False
    ):
        lookup[row.source_uri].append(
            row.target_uri
        )

    return dict(lookup)


# =============================================================================
# Candidate scoring
# =============================================================================

def calculate_candidate_score(
    source: DraftRecord,
    target: DraftRecord,
) -> CandidateScore:
    title_similarity = sequence_similarity(
        source.title,
        target.title,
    )

    name_similarity = sequence_similarity(
        source.name,
        target.name,
    )

    title_token_similarity = jaccard_similarity(
        source.title,
        target.title,
    )

    name_token_similarity = jaccard_similarity(
        source.name,
        target.name,
    )

    token_similarity = max(
        title_token_similarity,
        name_token_similarity,
    )

    date_score = 0.0

    source_date = (
        source.first_submission
        if is_valid_timestamp(
            source.first_submission
        )
        else source.document_time
    )

    target_date = (
        target.first_submission
        if is_valid_timestamp(
            target.first_submission
        )
        else target.document_time
    )

    if (
        is_valid_timestamp(source_date)
        and is_valid_timestamp(target_date)
    ):
        if target_date <= source_date:
            date_score = 1.0
        else:
            date_score = -0.5

    # Title is most important.
    # Name similarity and shared keywords provide supporting evidence.
    total_score = (
        0.45 * title_similarity
        + 0.25 * name_similarity
        + 0.20 * token_similarity
        + 0.10 * date_score
    )

    return CandidateScore(
        source_uri=source.uri,
        target_uri=target.uri,
        source_name=source.name,
        target_name=target.name,
        title_similarity=title_similarity,
        name_similarity=name_similarity,
        token_similarity=token_similarity,
        date_score=date_score,
        total_score=total_score,
    )


def choose_primary_predecessor(
    source_uri: str,
    draft_lookup: dict[str, DraftRecord],
    replaces_lookup: dict[str, list[str]],
) -> tuple[
    str | None,
    list[CandidateScore],
]:
    source = draft_lookup.get(source_uri)

    if source is None:
        return None, []

    target_uris = replaces_lookup.get(
        source_uri,
        [],
    )

    scores: list[CandidateScore] = []

    for target_uri in target_uris:
        target = draft_lookup.get(target_uri)

        if target is None:
            continue

        score = calculate_candidate_score(
            source,
            target,
        )

        scores.append(score)

    if not scores:
        return None, []

    scores.sort(
        key=lambda item: item.total_score,
        reverse=True,
    )

    best = scores[0]

    if best.total_score < MIN_PREDECESSOR_SCORE:
        return None, scores

    return best.target_uri, scores


# =============================================================================
# Build primary predecessor chains
# =============================================================================

def build_primary_chain(
    final_draft_uri: str,
    draft_lookup: dict[str, DraftRecord],
    replaces_lookup: dict[str, list[str]],
) -> tuple[
    list[tuple[str, int, float | None]],
    list[CandidateScore],
]:
    chain: list[
        tuple[str, int, float | None]
    ] = []

    candidate_scores: list[
        CandidateScore
    ] = []

    visited: set[str] = set()

    current_uri = final_draft_uri
    depth = 0
    selected_score: float | None = None

    while (
        current_uri
        and current_uri not in visited
        and depth <= MAX_CHAIN_DEPTH
    ):
        visited.add(current_uri)

        chain.append(
            (
                current_uri,
                depth,
                selected_score,
            )
        )

        predecessor_uri, scores = (
            choose_primary_predecessor(
                current_uri,
                draft_lookup,
                replaces_lookup,
            )
        )

        candidate_scores.extend(scores)

        if predecessor_uri is None:
            break

        matching_score = next(
            (
                item.total_score
                for item in scores
                if item.target_uri
                == predecessor_uri
            ),
            None,
        )

        current_uri = predecessor_uri
        selected_score = matching_score
        depth += 1

    return chain, candidate_scores


def create_chain_records(
    rfc_records: pd.DataFrame,
    draft_lookup: dict[str, DraftRecord],
    replaces_lookup: dict[str, list[str]],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    chain_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []

    total = len(rfc_records)

    for position, row in enumerate(
        rfc_records.itertuples(index=False),
        start=1,
    ):
        if (
            position == 1
            or position % 500 == 0
            or position == total
        ):
            print(
                f"Building primary chains: "
                f"{position:,}/{total:,}",
                flush=True,
            )

        chain, candidate_scores = (
            build_primary_chain(
                row.final_draft_uri,
                draft_lookup,
                replaces_lookup,
            )
        )

        selected_edges = {
            (
                chain[index][0],
                chain[index + 1][0],
            )
            for index in range(
                len(chain) - 1
            )
        }

        for (
            draft_uri,
            depth,
            selected_score,
        ) in chain:
            draft = draft_lookup.get(
                draft_uri
            )

            if draft is None:
                continue

            chain_rows.append(
                {
                    "rfc_uri": row.rfc_uri,
                    "rfc_number": row.rfc_number,
                    "rfc_name": row.rfc_name,
                    "rfc_title": row.rfc_title,
                    "publication_time":
                        row.publication_time,
                    "publication_year":
                        row.publication_year,
                    "final_draft_uri":
                        row.final_draft_uri,
                    "draft_uri": draft.uri,
                    "draft_name": draft.name,
                    "draft_title": draft.title,
                    "latest_rev":
                        draft.latest_rev,
                    "document_time":
                        draft.document_time,
                    "first_submission":
                        draft.first_submission,
                    "chain_depth": depth,
                    "selected_edge_score":
                        selected_score,
                    "is_final_draft":
                        depth == 0,
                }
            )

        for score in candidate_scores:
            selected = (
                score.source_uri,
                score.target_uri,
            ) in selected_edges

            rejected_rows.append(
                {
                    "rfc_number":
                        row.rfc_number,
                    "rfc_title":
                        row.rfc_title,
                    "publication_year":
                        row.publication_year,
                    "source_uri":
                        score.source_uri,
                    "target_uri":
                        score.target_uri,
                    "source_name":
                        score.source_name,
                    "target_name":
                        score.target_name,
                    "title_similarity":
                        score.title_similarity,
                    "name_similarity":
                        score.name_similarity,
                    "token_similarity":
                        score.token_similarity,
                    "date_score":
                        score.date_score,
                    "total_score":
                        score.total_score,
                    "selected": selected,
                }
            )

    return (
        pd.DataFrame(chain_rows),
        pd.DataFrame(rejected_rows),
    )


# =============================================================================
# RFC-level summary
# =============================================================================

def create_rfc_summary(
    chain_records: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = chain_records.copy()

    dataframe["publication_time"] = pd.to_datetime(
        dataframe["publication_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["first_submission"] = pd.to_datetime(
        dataframe["first_submission"],
        utc=True,
        errors="coerce",
    )

    # Only real posted submission dates are used.
    # document.time is not used as the main Figure 3 date.
    valid_submission = (
        dataframe["first_submission"].notna()
        & (
            dataframe["first_submission"]
            <= dataframe["publication_time"]
        )
    )

    dataframe.loc[
        ~valid_submission,
        "first_submission",
    ] = pd.NaT

    summary = (
        dataframe
        .groupby(
            [
                "rfc_uri",
                "rfc_number",
                "rfc_name",
                "rfc_title",
                "publication_time",
                "publication_year",
                "final_draft_uri",
            ],
            dropna=False,
        )
        .agg(
            first_draft_date=(
                "first_submission",
                "min",
            ),
            primary_chain_draft_count=(
                "draft_uri",
                "nunique",
            ),
            maximum_chain_depth=(
                "chain_depth",
                "max",
            ),
        )
        .reset_index()
    )

    summary = summary.dropna(
        subset=[
            "first_draft_date",
            "publication_time",
        ]
    ).copy()

    summary["days_to_publication"] = (
        summary["publication_time"]
        - summary["first_draft_date"]
    ).dt.days

    summary = summary[
        summary["days_to_publication"] >= 0
    ].copy()

    return summary.sort_values(
        [
            "publication_year",
            "rfc_number",
        ]
    ).reset_index(drop=True)


def split_valid_records(
    dataframe: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    excluded = dataframe[
        dataframe["days_to_publication"]
        > MAX_DEVELOPMENT_DAYS
    ].copy()

    valid = dataframe[
        dataframe["days_to_publication"]
        <= MAX_DEVELOPMENT_DAYS
    ].copy()

    return valid, excluded


# =============================================================================
# Year-level summary
# =============================================================================

def create_year_summary(
    rfc_summary: pd.DataFrame,
) -> pd.DataFrame:
    summary = (
        rfc_summary
        .groupby("publication_year")
        ["days_to_publication"]
        .agg(
            rfc_count="count",
            minimum="min",
            q1=lambda values:
                values.quantile(0.25),
            median="median",
            q3=lambda values:
                values.quantile(0.75),
            maximum="max",
            mean="mean",
        )
        .reset_index()
    )

    all_years = pd.DataFrame(
        {
            "publication_year": range(
                START_YEAR,
                END_YEAR + 1,
            )
        }
    )

    return all_years.merge(
        summary,
        on="publication_year",
        how="left",
    )


# =============================================================================
# Plot
# =============================================================================

def create_figure(
    year_summary: pd.DataFrame,
) -> None:
    valid = year_summary.dropna(
        subset=[
            "q1",
            "median",
            "q3",
        ]
    ).copy()

    if valid.empty:
        raise RuntimeError(
            "No valid yearly summary data "
            "is available for plotting."
        )

    figure, axis = plt.subplots(
        figsize=(11, 6.5)
    )

    axis.fill_between(
        valid["publication_year"],
        valid["q1"],
        valid["q3"],
        alpha=0.25,
        label="25th–75th percentile",
    )

    axis.plot(
        valid["publication_year"],
        valid["median"],
        marker="o",
        linewidth=2,
        markersize=4,
        label="Median",
    )

    axis.set_title(
        "Days from First Draft in the Primary "
        "Predecessor Chain to RFC Publication, "
        "2001–2025"
    )

    axis.set_xlabel(
        "RFC publication year"
    )

    axis.set_ylabel(
        "Days from first Draft to publication"
    )

    axis.set_xlim(
        START_YEAR - 0.5,
        END_YEAR + 0.5,
    )

    axis.set_xticks(
        range(
            START_YEAR,
            END_YEAR + 1,
        )
    )

    axis.tick_params(
        axis="x",
        rotation=90,
    )

    axis.set_ylim(bottom=0)

    axis.grid(
        True,
        alpha=0.3,
    )

    axis.legend(
        loc="upper left"
    )

    figure.text(
        0.5,
        0.01,
        (
            "For each replaces branch, one primary predecessor is "
            "selected using title, name, keyword, and date similarity. "
            "Only recorded posted submission dates are used."
        ),
        ha="center",
        fontsize=8,
    )

    figure.tight_layout(
        rect=(0, 0.04, 1, 1)
    )

    figure.savefig(
        OUTPUT_FIGURE_PNG,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)


# =============================================================================
# Diagnostics
# =============================================================================

def print_selected_years(
    year_summary: pd.DataFrame,
) -> None:
    selected_years = [
        2001,
        2002,
        2005,
        2007,
        2010,
        2012,
        2015,
        2018,
        2019,
        2020,
        2021,
        2025,
    ]

    selected = year_summary[
        year_summary[
            "publication_year"
        ].isin(selected_years)
    ][
        [
            "publication_year",
            "rfc_count",
            "q1",
            "median",
            "q3",
            "mean",
        ]
    ]

    print("\nSelected year summary:")

    print(
        selected.round(2).to_string(
            index=False
        )
    )


def print_rfc9000_validation(
    chain_records: pd.DataFrame,
    rfc_summary: pd.DataFrame,
    candidate_records: pd.DataFrame,
) -> None:
    print("\n" + "=" * 80)
    print("RFC 9000 VALIDATION")
    print("=" * 80)

    chain = chain_records[
        chain_records["rfc_number"]
        == 9000
    ].sort_values(
        "chain_depth",
        ascending=False,
    )

    print("\nSelected primary chain:")

    if chain.empty:
        print("RFC 9000 chain was not found.")
    else:
        print(
            chain[
                [
                    "draft_name",
                    "draft_title",
                    "chain_depth",
                    "selected_edge_score",
                    "first_submission",
                ]
            ].to_string(index=False)
        )

    candidates = candidate_records[
        candidate_records["rfc_number"]
        == 9000
    ].sort_values(
        [
            "source_name",
            "total_score",
        ],
        ascending=[
            True,
            False,
        ],
    )

    print("\nRFC 9000 predecessor candidates:")

    if candidates.empty:
        print("No candidate records were found.")
    else:
        print(
            candidates[
                [
                    "source_name",
                    "target_name",
                    "title_similarity",
                    "name_similarity",
                    "token_similarity",
                    "date_score",
                    "total_score",
                    "selected",
                ]
            ].round(3).to_string(
                index=False
            )
        )

    result = rfc_summary[
        rfc_summary["rfc_number"]
        == 9000
    ]

    print("\nRFC-level result:")

    if result.empty:
        print("RFC 9000 result was not found.")
    else:
        print(
            result[
                [
                    "rfc_number",
                    "primary_chain_draft_count",
                    "maximum_chain_depth",
                    "first_draft_date",
                    "publication_time",
                    "days_to_publication",
                ]
            ].to_string(index=False)
        )


def print_chain_statistics(
    chain_records: pd.DataFrame,
    rfc_summary: pd.DataFrame,
) -> None:
    print("\n" + "=" * 80)
    print("PRIMARY CHAIN STATISTICS")
    print("=" * 80)

    print(
        f"\nChain records: "
        f"{len(chain_records):,}"
    )

    print(
        f"RFC duration records: "
        f"{len(rfc_summary):,}"
    )

    multiple_drafts = (
        rfc_summary[
            "primary_chain_draft_count"
        ] > 1
    ).sum()

    print(
        "RFCs with a selected predecessor:",
        f"{multiple_drafts:,}",
    )

    if len(rfc_summary) > 0:
        percentage = (
            multiple_drafts
            / len(rfc_summary)
            * 100
        )

        print(
            "Percentage with a selected predecessor:",
            f"{percentage:.2f}%",
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print(
        "Database:",
        DATABASE_PATH.resolve(),
    )

    print(
        "Exists:",
        DATABASE_PATH.exists(),
    )

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: "
            f"{DATABASE_PATH.resolve()}"
        )

    OUTPUT_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FIGURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:
        connection.execute(
            "PRAGMA temp_store=MEMORY"
        )

        connection.execute(
            "PRAGMA cache_size=-500000"
        )

        check_required_tables(
            connection
        )

        rfc_records = load_rfc_records(
            connection
        )

        draft_records = load_draft_records(
            connection
        )

        replaces_records = (
            load_replaces_relationships(
                connection
            )
        )

    finally:
        connection.close()

    rfc_records = prepare_rfc_records(
        rfc_records
    )

    draft_records = prepare_draft_records(
        draft_records
    )

    if rfc_records.empty:
        raise RuntimeError(
            "No RFC records remained after cleaning."
        )

    if draft_records.empty:
        raise RuntimeError(
            "No Draft records remained after cleaning."
        )

    draft_lookup = create_draft_lookup(
        draft_records
    )

    replaces_lookup = create_replaces_lookup(
        replaces_records
    )

    chain_records, candidate_records = (
        create_chain_records(
            rfc_records,
            draft_lookup,
            replaces_lookup,
        )
    )

    if chain_records.empty:
        raise RuntimeError(
            "No primary Draft chains were created."
        )

    all_rfc_summary = create_rfc_summary(
        chain_records
    )

    valid_rfc_summary, excluded_records = (
        split_valid_records(
            all_rfc_summary
        )
    )

    if valid_rfc_summary.empty:
        raise RuntimeError(
            "No valid RFC duration records remained."
        )

    year_summary = create_year_summary(
        valid_rfc_summary
    )

    chain_records.to_csv(
        OUTPUT_CHAIN_RECORDS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    valid_rfc_summary.to_csv(
        OUTPUT_RFC_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    year_summary.to_csv(
        OUTPUT_YEAR_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    candidate_records.to_csv(
        OUTPUT_REJECTED_CANDIDATES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    excluded_records.to_csv(
        OUTPUT_EXCLUDED_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    create_figure(
        year_summary
    )

    print_chain_statistics(
        chain_records,
        valid_rfc_summary,
    )

    print_selected_years(
        year_summary
    )

    print_rfc9000_validation(
        chain_records,
        all_rfc_summary,
        candidate_records,
    )

    print("\nExcluded duration records:")
    print(
        f"{len(excluded_records):,}"
    )

    print("\n" + "=" * 80)
    print("CREATED FILES")
    print("=" * 80)

    print(OUTPUT_CHAIN_RECORDS_CSV)
    print(OUTPUT_RFC_SUMMARY_CSV)
    print(OUTPUT_YEAR_SUMMARY_CSV)
    print(OUTPUT_REJECTED_CANDIDATES_CSV)
    print(OUTPUT_EXCLUDED_CSV)
    print(OUTPUT_FIGURE_PNG)


if __name__ == "__main__":
    main()