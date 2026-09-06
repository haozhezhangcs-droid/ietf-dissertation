from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "outputs"


# Main lineage dataset created earlier.
LINEAGE_FILE = (
    OUTPUT_DIR
    / "intermediate"
    / "lineage_dataset.csv"
)

# Revision-level draft history from 00.
HISTORY_FILE = (
    OUTPUT_DIR
    / "common"
    / "lineage_history_records.csv"
)

# Participant / author resolution output.
#
# Expected to contain at least:
#   draft_name
#   participant_id
#
# Optional:
#   author_name
#   email
PARTICIPANT_FILE = (
    OUTPUT_DIR
    / "draft_participants.csv"
)

# Temporal affiliation evidence.
#
# Expected to contain at least:
#   participant_id
#   date
#   organisation_id
#
# Optional:
#   conflict
AFFILIATION_FILE = (
    OUTPUT_DIR
    / "participant_affiliations.csv"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "rq3_collaboration_dataset.csv"
)


# ============================================================
# 2. Helpers
# ============================================================

def normalise_text(value) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def parse_bool(value) -> int:
    text = normalise_text(value).lower()

    return int(
        text in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


def find_column(
    df: pd.DataFrame,
    candidates: List[str],
    required: bool = True,
) -> str:
    """
    Find the first matching column name.

    This makes the script slightly more robust to earlier
    scripts using different but equivalent column names.
    """

    for column in candidates:
        if column in df.columns:
            return column

    if required:
        raise KeyError(
            "Could not find any of these columns: "
            + ", ".join(candidates)
        )

    return ""


# ============================================================
# 3. Load lineage data
# ============================================================

lineage_df = pd.read_csv(
    LINEAGE_FILE,
    dtype=str,
).fillna("")


lineage_id_col = find_column(
    lineage_df,
    [
        "lineage_id",
    ],
)

lineage_members_col = find_column(
    lineage_df,
    [
        "lineage_members",
    ],
)


# ============================================================
# 4. Load revision history
# ============================================================

history_df = pd.read_csv(
    HISTORY_FILE,
    dtype=str,
).fillna("")


history_lineage_col = find_column(
    history_df,
    [
        "lineage_id",
    ],
)

history_draft_col = find_column(
    history_df,
    [
        "draft_name",
    ],
)

history_date_col = find_column(
    history_df,
    [
        "date",
    ],
)


history_df["date_parsed"] = pd.to_datetime(
    history_df[history_date_col],
    errors="coerce",
)


# ============================================================
# 5. First observed date for each draft Document
#
# Cross-organisation collaboration is evaluated at the first
# observed date of each specific draft Document.
# ============================================================

draft_first_date: Dict[str, pd.Timestamp] = {}


for draft_name, group in history_df.groupby(
    history_draft_col,
    dropna=False,
):

    draft_name = normalise_text(
        draft_name
    )

    if not draft_name:
        continue

    dates = (
        group["date_parsed"]
        .dropna()
    )

    if dates.empty:
        continue

    draft_first_date[draft_name] = (
        dates.min()
    )


# ============================================================
# 6. Draft -> lineage mapping
# ============================================================

draft_to_lineage: Dict[str, str] = {}


for _, row in history_df.iterrows():

    draft_name = normalise_text(
        row.get(
            history_draft_col,
            "",
        )
    )

    lineage_id = normalise_text(
        row.get(
            history_lineage_col,
            "",
        )
    )

    if (
        draft_name
        and lineage_id
    ):
        draft_to_lineage[draft_name] = (
            lineage_id
        )


# ============================================================
# 7. Load participant resolution
# ============================================================

participant_df = pd.read_csv(
    PARTICIPANT_FILE,
    dtype=str,
).fillna("")


participant_draft_col = find_column(
    participant_df,
    [
        "draft_name",
        "document_name",
        "doc_name",
    ],
)

participant_id_col = find_column(
    participant_df,
    [
        "participant_id",
        "pid",
        "person_id",
    ],
)


# Optional diagnostic column.
participant_unresolved_col = find_column(
    participant_df,
    [
        "unresolved_participant",
        "participant_unresolved",
        "identity_unresolved",
    ],
    required=False,
)


# ============================================================
# 8. Draft -> resolved participants
# ============================================================

draft_participants: Dict[
    str,
    Set[str],
] = defaultdict(set)


lineage_unresolved_identity: Dict[
    str,
    int,
] = defaultdict(int)


for _, row in participant_df.iterrows():

    draft_name = normalise_text(
        row.get(
            participant_draft_col,
            "",
        )
    )

    participant_id = normalise_text(
        row.get(
            participant_id_col,
            "",
        )
    )


    if not draft_name:
        continue


    lineage_id = draft_to_lineage.get(
        draft_name,
        "",
    )


    if participant_id:

        draft_participants[
            draft_name
        ].add(
            participant_id
        )

    else:

        if lineage_id:
            lineage_unresolved_identity[
                lineage_id
            ] = 1


    if participant_unresolved_col:

        if parse_bool(
            row.get(
                participant_unresolved_col,
                "0",
            )
        ):

            if lineage_id:
                lineage_unresolved_identity[
                    lineage_id
                ] = 1


# ============================================================
# 9. Load affiliation evidence
# ============================================================

affiliation_df = pd.read_csv(
    AFFILIATION_FILE,
    dtype=str,
).fillna("")


affiliation_pid_col = find_column(
    affiliation_df,
    [
        "participant_id",
        "pid",
        "person_id",
    ],
)

affiliation_org_col = find_column(
    affiliation_df,
    [
        "organisation_id",
        "org_id",
        "organisation",
        "org",
    ],
)

affiliation_date_col = find_column(
    affiliation_df,
    [
        "date",
        "affiliation_date",
        "evidence_date",
    ],
)


affiliation_conflict_col = find_column(
    affiliation_df,
    [
        "conflict",
        "affiliation_conflict",
        "has_conflict",
    ],
    required=False,
)


affiliation_df["date_parsed"] = (
    pd.to_datetime(
        affiliation_df[
            affiliation_date_col
        ],
        errors="coerce",
    )
)


# ============================================================
# 10. Build participant affiliation histories
#
# participant_id ->
# [
#   (date, organisation_id, conflict),
#   ...
# ]
# ============================================================

affiliation_history: Dict[
    str,
    List[dict],
] = defaultdict(list)


for _, row in affiliation_df.iterrows():

    participant_id = normalise_text(
        row.get(
            affiliation_pid_col,
            "",
        )
    )

    organisation_id = normalise_text(
        row.get(
            affiliation_org_col,
            "",
        )
    )

    affiliation_date = row.get(
        "date_parsed"
    )

    if (
        not participant_id
        or not organisation_id
        or pd.isna(
            affiliation_date
        )
    ):
        continue


    conflict = 0

    if affiliation_conflict_col:

        conflict = parse_bool(
            row.get(
                affiliation_conflict_col,
                "0",
            )
        )


    affiliation_history[
        participant_id
    ].append(
        {
            "date":
                affiliation_date,

            "organisation_id":
                organisation_id,

            "conflict":
                conflict,
        }
    )


for participant_id in affiliation_history:

    affiliation_history[
        participant_id
    ].sort(
        key=lambda item:
            item["date"]
    )


# ============================================================
# 11. Resolve affiliation at a specific date
#
# We use the latest affiliation evidence at or before the
# requested date.
#
# If no earlier evidence exists, we do not guess.
# ============================================================

def organisation_at_date(
    participant_id: str,
    target_date: pd.Timestamp,
):

    history = affiliation_history.get(
        participant_id,
        [],
    )

    if not history:
        return (
            "",
            0,
        )


    eligible = [
        item
        for item in history
        if item["date"] <= target_date
    ]


    if not eligible:
        return (
            "",
            0,
        )


    latest_date = max(
        item["date"]
        for item in eligible
    )


    latest = [
        item
        for item in eligible
        if item["date"] == latest_date
    ]


    organisations = {
        item[
            "organisation_id"
        ]
        for item in latest
        if item[
            "organisation_id"
        ]
    }


    conflict = int(
        any(
            item["conflict"]
            for item in latest
        )
        or len(
            organisations
        ) > 1
    )


    if conflict:
        return (
            "",
            1,
        )


    if len(
        organisations
    ) != 1:
        return (
            "",
            conflict,
        )


    return (
        next(
            iter(
                organisations
            )
        ),
        conflict,
    )


# ============================================================
# 12. Build RQ3 lineage-level collaboration variables
# ============================================================

output_rows = []


for _, lineage_row in lineage_df.iterrows():

    lineage_id = normalise_text(
        lineage_row.get(
            lineage_id_col,
            "",
        )
    )

    lineage_members = {
        member.strip()
        for member in normalise_text(
            lineage_row.get(
                lineage_members_col,
                "",
            )
        ).split(";")
        if member.strip()
    }


    # --------------------------------------------------------
    # All resolved participants in the lineage
    # --------------------------------------------------------

    lineage_participants: Set[str] = set()


    for draft_name in lineage_members:

        lineage_participants.update(
            draft_participants.get(
                draft_name,
                set(),
            )
        )


    lineage_author_count = len(
        lineage_participants
    )


    has_resolved_author = int(
        lineage_author_count > 0
    )


    # --------------------------------------------------------
    # Organisation history across whole lineage
    # --------------------------------------------------------

    lineage_organisations: Set[str] = set()

    participants_with_org: Set[str] = set()

    lineage_has_conflict = 0


    for participant_id in lineage_participants:

        participant_history = (
            affiliation_history.get(
                participant_id,
                [],
            )
        )


        if any(
            item["conflict"]
            for item in participant_history
        ):
            lineage_has_conflict = 1


        participant_orgs = {
            item[
                "organisation_id"
            ]
            for item in participant_history
            if item[
                "organisation_id"
            ]
        }


        if participant_orgs:

            participants_with_org.add(
                participant_id
            )

            lineage_organisations.update(
                participant_orgs
            )


    lineage_org_count = len(
        lineage_organisations
    )


    has_resolved_organisation = int(
        lineage_org_count > 0
    )


    multi_organisation_history = int(
        lineage_org_count >= 2
    )


    # --------------------------------------------------------
    # Complete affiliation coverage
    #
    # Every resolved lineage participant must have at least one
    # resolved organisation somewhere in their evidence history.
    # --------------------------------------------------------

    complete_affiliation_coverage = int(
        lineage_author_count > 0
        and len(
            participants_with_org
        )
        == lineage_author_count
    )


    affiliation_coverage_ratio = (
        len(
            participants_with_org
        )
        / lineage_author_count
        if lineage_author_count > 0
        else 0.0
    )


    # --------------------------------------------------------
    # Cross-organisational co-authorship
    #
    # Strong definition:
    #
    # At least one specific draft Document has co-authors from
    # >=2 distinct organisations at that Document's first
    # observed date.
    # --------------------------------------------------------

    cross_org = 0

    cross_org_drafts: List[str] = []


    for draft_name in sorted(
        lineage_members
    ):

        first_date = draft_first_date.get(
            draft_name
        )

        if first_date is None:
            continue


        participants = (
            draft_participants.get(
                draft_name,
                set(),
            )
        )


        if len(
            participants
        ) < 2:
            continue


        draft_orgs: Set[str] = set()


        for participant_id in participants:

            (
                organisation_id,
                conflict,
            ) = organisation_at_date(
                participant_id,
                first_date,
            )


            if conflict:
                lineage_has_conflict = 1


            if organisation_id:

                draft_orgs.add(
                    organisation_id
                )


        if len(
            draft_orgs
        ) >= 2:

            cross_org = 1

            cross_org_drafts.append(
                draft_name
            )


    # --------------------------------------------------------
    # Unresolved participant identity flag
    # --------------------------------------------------------

    unresolved_participant_identity = int(
        lineage_unresolved_identity.get(
            lineage_id,
            0,
        )
    )


    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    out = lineage_row.to_dict()

    out.update(
        {
            "lineage_author_count":
                lineage_author_count,

            "has_resolved_author":
                has_resolved_author,

            "lineage_org_count":
                lineage_org_count,

            "has_resolved_organisation":
                has_resolved_organisation,

            "multi_organisation_history":
                multi_organisation_history,

            "cross_org":
                cross_org,

            "cross_org_drafts":
                ";".join(
                    cross_org_drafts
                ),

            "complete_affiliation_coverage":
                complete_affiliation_coverage,

            "affiliation_coverage_ratio":
                affiliation_coverage_ratio,

            "affiliation_conflict":
                lineage_has_conflict,

            "unresolved_participant_identity":
                unresolved_participant_identity,
        }
    )

    output_rows.append(
        out
    )


# ============================================================
# 13. Save output
# ============================================================

result_df = pd.DataFrame(
    output_rows
)


result_df = result_df.sort_values(
    "lineage_id"
)


result_df.to_csv(
    OUTPUT_FILE,
    index=False,
)


# ============================================================
# 14. Validation summary
# ============================================================

print()
print("=" * 72)
print("RQ3 COLLABORATION DATASET")
print("=" * 72)


print(
    "Lineages:",
    f"{len(result_df):,}",
)


print(
    "Lineages with >=1 resolved author:",
    f"{int(result_df['has_resolved_author'].sum()):,}",
)


print(
    "Lineages with >=1 resolved organisation:",
    f"{int(result_df['has_resolved_organisation'].sum()):,}",
)


print(
    "Lineages with multi-organisation history:",
    f"{int(result_df['multi_organisation_history'].sum()):,}",
)


print(
    "Cross-organisation co-authorship lineages:",
    f"{int(result_df['cross_org'].sum()):,}",
)


print(
    "Lineages with complete affiliation coverage:",
    f"{int(result_df['complete_affiliation_coverage'].sum()):,}",
)


print(
    "Lineages containing affiliation conflict:",
    f"{int(result_df['affiliation_conflict'].sum()):,}",
)


print(
    "Lineages with unresolved participant identity:",
    f"{int(result_df['unresolved_participant_identity'].sum()):,}",
)


print()
print(
    f"Saved: {OUTPUT_FILE}"
)