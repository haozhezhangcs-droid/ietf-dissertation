from __future__ import annotations

from pathlib import Path
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

OUTPUT_FAMILY_CSV = (
    OUTPUT_DATA_DIR
    / "figure04_document_rev_family_records.csv"
)

OUTPUT_RFC_SUMMARY_CSV = (
    OUTPUT_DATA_DIR
    / "figure04_document_rev_rfc_summary.csv"
)

OUTPUT_YEAR_SUMMARY_CSV = (
    OUTPUT_DATA_DIR
    / "figure04_document_rev_year_summary.csv"
)

OUTPUT_FIGURE_PNG = (
    OUTPUT_FIGURE_DIR
    / "figure04_document_rev_lineage_2001_2025.png"
)


# =============================================================================
# Settings
# =============================================================================

START_YEAR = 2001
END_YEAR = 2025

RFC_DOCUMENT_TYPE = (
    "/api/v1/name/doctypename/rfc/"
)

DRAFT_DOCUMENT_TYPE = (
    "/api/v1/name/doctypename/draft/"
)

BECAME_RFC_RELATIONSHIP = (
    "/api/v1/name/docrelationshipname/became_rfc/"
)

REPLACES_RELATIONSHIP = (
    "/api/v1/name/docrelationshipname/replaces/"
)


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

    missing_tables = required_tables - existing_tables

    if missing_tables:
        raise RuntimeError(
            "Missing required tables: "
            f"{sorted(missing_tables)}"
        )


def print_database_checks(
    connection: sqlite3.Connection,
) -> None:
    checks = [
        (
            "RFC documents",
            """
            SELECT COUNT(*)
            FROM ietf_dt_doc_document
            WHERE type = ?
            """,
            (RFC_DOCUMENT_TYPE,),
        ),
        (
            "Draft documents",
            """
            SELECT COUNT(*)
            FROM ietf_dt_doc_document
            WHERE type = ?
            """,
            (DRAFT_DOCUMENT_TYPE,),
        ),
        (
            "became_rfc relationships",
            """
            SELECT COUNT(*)
            FROM ietf_dt_doc_relateddocument
            WHERE relationship = ?
            """,
            (BECAME_RFC_RELATIONSHIP,),
        ),
        (
            "replaces relationships",
            """
            SELECT COUNT(*)
            FROM ietf_dt_doc_relateddocument
            WHERE relationship = ?
            """,
            (REPLACES_RELATIONSHIP,),
        ),
    ]

    print("\nDatabase checks:")

    for label, query, params in checks:
        count = connection.execute(
            query,
            params,
        ).fetchone()[0]

        print(f"  {label}: {count:,}")


# =============================================================================
# Load complete draft lineage
# =============================================================================

def load_family_records(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    """
    Return one row for every distinct Draft document in an RFC lineage.

    Direction used by the database:

        newer draft --replaces--> older draft

    Starting from the Draft connected to the RFC through became_rfc,
    recursively follow replaces from source to target.
    """

    query = """
    WITH RECURSIVE

    publication_events AS (
        SELECT
            doc,
            MIN(time) AS publication_time
        FROM ietf_dt_doc_docevent
        WHERE type = 'published_rfc'
        GROUP BY doc
    ),

    rfc_base AS (
        SELECT
            document.resource_uri AS rfc_uri,
            document.rfc_number,
            document.name AS rfc_name,
            document.title AS rfc_title,
            publication_events.publication_time
        FROM ietf_dt_doc_document AS document

        INNER JOIN publication_events
            ON publication_events.doc =
               document.resource_uri

        WHERE document.type = ?
          AND document.rfc_number IS NOT NULL
    ),

    final_drafts AS (
        SELECT DISTINCT
            rfc_base.rfc_uri,
            rfc_base.rfc_number,
            rfc_base.rfc_name,
            rfc_base.rfc_title,
            rfc_base.publication_time,
            relation.source AS final_draft_uri
        FROM rfc_base

        INNER JOIN ietf_dt_doc_relateddocument AS relation
            ON relation.target = rfc_base.rfc_uri

        WHERE relation.relationship = ?
          AND relation.source LIKE
              '/api/v1/doc/document/draft-%/'
    ),

    draft_lineage AS (
        /*
        Anchor:
        the final Draft directly connected to the RFC.
        */
        SELECT
            final_drafts.rfc_uri,
            final_drafts.rfc_number,
            final_drafts.rfc_name,
            final_drafts.rfc_title,
            final_drafts.publication_time,
            final_drafts.final_draft_uri,
            final_drafts.final_draft_uri AS draft_uri,
            0 AS lineage_depth,

            '|' || final_drafts.final_draft_uri || '|'
                AS visited_path

        FROM final_drafts

        UNION ALL

        /*
        Recursion:
        current/newer Draft is relation.source;
        predecessor/older Draft is relation.target.
        */
        SELECT
            draft_lineage.rfc_uri,
            draft_lineage.rfc_number,
            draft_lineage.rfc_name,
            draft_lineage.rfc_title,
            draft_lineage.publication_time,
            draft_lineage.final_draft_uri,
            relation.target AS draft_uri,
            draft_lineage.lineage_depth + 1,

            draft_lineage.visited_path
                || relation.target
                || '|'

        FROM draft_lineage

        INNER JOIN ietf_dt_doc_relateddocument AS relation
            ON relation.source = draft_lineage.draft_uri

        WHERE relation.relationship = ?

          AND relation.target LIKE
              '/api/v1/doc/document/draft-%/'

          /*
          Avoid loops if malformed relationships exist.
          */
          AND INSTR(
              draft_lineage.visited_path,
              '|' || relation.target || '|'
          ) = 0

          /*
          Prevent pathological recursion.
          */
          AND draft_lineage.lineage_depth < 50
    ),

    distinct_lineage AS (
        SELECT
            rfc_uri,
            rfc_number,
            rfc_name,
            rfc_title,
            publication_time,
            final_draft_uri,
            draft_uri,
            MIN(lineage_depth) AS lineage_depth
        FROM draft_lineage

        GROUP BY
            rfc_uri,
            rfc_number,
            rfc_name,
            rfc_title,
            publication_time,
            final_draft_uri,
            draft_uri
    )

    SELECT
        distinct_lineage.rfc_uri,
        distinct_lineage.rfc_number,
        distinct_lineage.rfc_name,
        distinct_lineage.rfc_title,
        distinct_lineage.publication_time,
        distinct_lineage.final_draft_uri,
        distinct_lineage.draft_uri,
        distinct_lineage.lineage_depth,

        draft_document.name AS draft_name,
        draft_document.rev AS latest_rev,
        draft_document.title AS draft_title,
        draft_document.type AS draft_type,

        CASE
            WHEN draft_document.rev IS NULL
                THEN NULL

            WHEN TRIM(draft_document.rev) = ''
                THEN NULL

            WHEN TRIM(draft_document.rev)
                 GLOB '*[^0-9]*'
                THEN NULL

            ELSE
                CAST(
                    TRIM(draft_document.rev)
                    AS INTEGER
                ) + 1
        END AS revision_count

    FROM distinct_lineage

    LEFT JOIN ietf_dt_doc_document AS draft_document
        ON draft_document.resource_uri =
           distinct_lineage.draft_uri

    ORDER BY
        distinct_lineage.publication_time,
        distinct_lineage.rfc_number,
        distinct_lineage.lineage_depth DESC
    """

    print(
        "\nLoading RFC Draft lineages and document.rev values...",
        flush=True,
    )

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(
            RFC_DOCUMENT_TYPE,
            BECAME_RFC_RELATIONSHIP,
            REPLACES_RELATIONSHIP,
        ),
    )

    print(
        f"Loaded {len(dataframe):,} RFC-Draft family records.",
        flush=True,
    )

    return dataframe


# =============================================================================
# Data preparation
# =============================================================================

def prepare_family_records(
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

    dataframe["revision_count"] = pd.to_numeric(
        dataframe["revision_count"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "publication_year",
            "draft_uri",
            "draft_name",
            "revision_count",
        ]
    ).copy()

    dataframe["publication_year"] = (
        dataframe["publication_year"].astype(int)
    )

    dataframe["revision_count"] = (
        dataframe["revision_count"].astype(int)
    )

    dataframe["lineage_depth"] = (
        pd.to_numeric(
            dataframe["lineage_depth"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    dataframe = dataframe[
        dataframe["publication_year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    dataframe = dataframe[
        dataframe["revision_count"] > 0
    ].copy()

    dataframe["is_final_draft"] = (
        dataframe["draft_uri"]
        == dataframe["final_draft_uri"]
    )

    return dataframe.drop_duplicates(
        subset=[
            "rfc_uri",
            "draft_uri",
        ]
    ).copy()


# =============================================================================
# RFC-level aggregation
# =============================================================================

def create_rfc_summary(
    family_records: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create one row per RFC.

    complete_revision_count:
        sum of latest_rev + 1 for all distinct Draft names
        in the complete recorded lineage.
    """

    total_summary = (
        family_records
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
            family_draft_count=(
                "draft_uri",
                "nunique",
            ),
            maximum_lineage_depth=(
                "lineage_depth",
                "max",
            ),
            complete_revision_count=(
                "revision_count",
                "sum",
            ),
        )
        .reset_index()
    )

    final_summary = (
        family_records[
            family_records["is_final_draft"]
        ]
        .groupby("rfc_uri")
        .agg(
            final_draft_revision_count=(
                "revision_count",
                "sum",
            )
        )
        .reset_index()
    )

    predecessor_summary = (
        family_records[
            ~family_records["is_final_draft"]
        ]
        .groupby("rfc_uri")
        .agg(
            predecessor_draft_count=(
                "draft_uri",
                "nunique",
            ),
            predecessor_revision_count=(
                "revision_count",
                "sum",
            ),
        )
        .reset_index()
    )

    summary = (
        total_summary
        .merge(
            final_summary,
            on="rfc_uri",
            how="left",
        )
        .merge(
            predecessor_summary,
            on="rfc_uri",
            how="left",
        )
    )

    count_columns = [
        "family_draft_count",
        "maximum_lineage_depth",
        "complete_revision_count",
        "final_draft_revision_count",
        "predecessor_draft_count",
        "predecessor_revision_count",
    ]

    for column in count_columns:
        summary[column] = (
            summary[column]
            .fillna(0)
            .astype(int)
        )

    return summary.sort_values(
        [
            "publication_year",
            "rfc_number",
        ]
    ).reset_index(drop=True)


# =============================================================================
# Year-level aggregation
# =============================================================================

def create_year_summary(
    rfc_summary: pd.DataFrame,
) -> pd.DataFrame:
    summary = (
        rfc_summary
        .groupby("publication_year")
        ["complete_revision_count"]
        .agg(
            rfc_count="count",
            minimum="min",
            q1=lambda values: values.quantile(0.25),
            median="median",
            q3=lambda values: values.quantile(0.75),
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
            "No yearly summary data is available for plotting."
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
        "Internet-Draft Versions before RFC Publication, "
        "2001–2025"
    )

    axis.set_xlabel(
        "RFC publication year"
    )

    axis.set_ylabel(
        "Number of Draft versions before publication"
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

    axis.set_ylim(
        bottom=0
    )

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
            "Each Draft contributes latest recorded revision number + 1. "
            "Predecessor Drafts linked through replaces are included."
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
        2003,
        2005,
        2007,
        2008,
        2010,
        2015,
        2020,
        2021,
        2025,
    ]

    selected = year_summary[
        year_summary["publication_year"].isin(
            selected_years
        )
    ][
        [
            "publication_year",
            "rfc_count",
            "q1",
            "median",
            "q3",
            "mean",
        ]
    ].copy()

    print("\nSelected year summary:")
    print(
        selected.round(2).to_string(
            index=False
        )
    )


def print_rfc9000_validation(
    family_records: pd.DataFrame,
    rfc_summary: pd.DataFrame,
) -> None:
    print("\n" + "=" * 80)
    print("RFC 9000 VALIDATION")
    print("=" * 80)

    family = family_records[
        family_records["rfc_number"] == 9000
    ].sort_values(
        "lineage_depth",
        ascending=False,
    )

    print("\nDraft family:")

    if family.empty:
        print("RFC 9000 was not found.")
    else:
        print(
            family[
                [
                    "draft_name",
                    "latest_rev",
                    "revision_count",
                    "lineage_depth",
                    "is_final_draft",
                ]
            ].to_string(index=False)
        )

    summary = rfc_summary[
        rfc_summary["rfc_number"] == 9000
    ]

    print("\nRFC-level summary:")

    if summary.empty:
        print("RFC 9000 summary was not found.")
    else:
        print(
            summary[
                [
                    "rfc_number",
                    "family_draft_count",
                    "predecessor_draft_count",
                    "final_draft_revision_count",
                    "predecessor_revision_count",
                    "complete_revision_count",
                ]
            ].to_string(index=False)
        )


def print_largest_records(
    rfc_summary: pd.DataFrame,
) -> None:
    print("\n" + "=" * 80)
    print("LARGEST REVISION COUNTS")
    print("=" * 80)

    columns = [
        "rfc_number",
        "rfc_title",
        "publication_year",
        "family_draft_count",
        "final_draft_revision_count",
        "predecessor_revision_count",
        "complete_revision_count",
    ]

    print(
        rfc_summary.nlargest(
            20,
            "complete_revision_count",
        )[columns].to_string(index=False)
    )


def print_diagnostics(
    family_records: pd.DataFrame,
    rfc_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> None:
    print("\n" + "=" * 80)
    print("FIGURE 4 — DOCUMENT.REV-BASED DRAFT LINEAGES")
    print("=" * 80)

    print(
        f"\nDraft family records: {len(family_records):,}"
    )

    print(
        f"RFC-level records: {len(rfc_summary):,}"
    )

    print(
        "Publication years:",
        rfc_summary["publication_year"].min(),
        "to",
        rfc_summary["publication_year"].max(),
    )

    predecessor_count = (
        rfc_summary["predecessor_draft_count"] > 0
    ).sum()

    print(
        "RFCs with recorded predecessor Drafts:",
        f"{predecessor_count:,}",
    )

    if len(rfc_summary) > 0:
        percentage = (
            predecessor_count
            / len(rfc_summary)
            * 100
        )

        print(
            "Percentage with predecessor Drafts:",
            f"{percentage:.2f}%",
        )

    print_selected_years(
        year_summary
    )

    print_rfc9000_validation(
        family_records,
        rfc_summary,
    )

    print_largest_records(
        rfc_summary
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

        print_database_checks(
            connection
        )

        family_records = load_family_records(
            connection
        )

    finally:
        connection.close()

    if family_records.empty:
        raise RuntimeError(
            "No Draft lineage records were found."
        )

    family_records = prepare_family_records(
        family_records
    )

    if family_records.empty:
        raise RuntimeError(
            "No usable Draft lineage records remained "
            "after cleaning document.rev values."
        )

    rfc_summary = create_rfc_summary(
        family_records
    )

    if rfc_summary.empty:
        raise RuntimeError(
            "No RFC-level summary records were created."
        )

    year_summary = create_year_summary(
        rfc_summary
    )

    family_records.to_csv(
        OUTPUT_FAMILY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    rfc_summary.to_csv(
        OUTPUT_RFC_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    year_summary.to_csv(
        OUTPUT_YEAR_SUMMARY_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    create_figure(
        year_summary
    )

    print_diagnostics(
        family_records,
        rfc_summary,
        year_summary,
    )

    print("\n" + "=" * 80)
    print("CREATED FILES")
    print("=" * 80)

    print(OUTPUT_FAMILY_CSV)
    print(OUTPUT_RFC_SUMMARY_CSV)
    print(OUTPUT_YEAR_SUMMARY_CSV)
    print(OUTPUT_FIGURE_PNG)


if __name__ == "__main__":
    main()