from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
)

LINEAGE_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "intermediate"
    / "lineage_dataset.csv"
)

HISTORY_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "common"
    / "lineage_history_records.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "validation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


NAME_CANDIDATE_FILE = (
    OUTPUT_DIR
    / "01_name_candidates.csv"
)

CHRONOLOGY_FILE = (
    OUTPUT_DIR
    / "02_chronology_candidates.csv"
)

HIGH_CONFIDENCE_FILE = (
    OUTPUT_DIR
    / "03_high_confidence_missing_links.csv"
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "crosscheck_summary.csv"
)


# ============================================================
# 2. Conservative name filtering
# ============================================================

# These terms occur in many unrelated Internet-Drafts.
# Matching only one of these terms is not useful evidence
# that an Individual draft became a WG draft.

GENERIC_TOPICS = {
    "framework",
    "requirement",
    "requirements",
    "architecture",
    "arch",
    "protocol",
    "spec",
    "specification",
    "extension",
    "extensions",
    "model",
    "models",
    "overview",
    "guide",
    "guidelines",
    "process",
    "procedure",
    "procedures",
    "security",
    "base",
    "core",
    "general",
    "update",
    "updates",
    "bis",
    "api",
    "iana",
    "routing",
    "mapping",
    "format",
    "deployment",
    "transition",
    "discovery",
    "notification",
    "terminology",
    "considerations",
    "problem-statement",
}


# ============================================================
# 3. Initialise ietfdata library
# ============================================================

print()
print("=" * 72)
print("INITIALISING IETFDATA")
print("=" * 72)

dt = DataTrackerExt(
    DTBackendArchive(
        str(DATABASE_PATH)
    )
)

print(
    f"Datatracker archive: {DATABASE_PATH}"
)


# ============================================================
# 4. Load generated datasets
# ============================================================

print()
print("=" * 72)
print("LOADING DATA")
print("=" * 72)

lineage_df = pd.read_csv(
    LINEAGE_FILE,
    dtype=str,
).fillna("")

history_df = pd.read_csv(
    HISTORY_FILE,
    dtype=str,
).fillna("")


print(
    f"Lineages: "
    f"{len(lineage_df):,}"
)

print(
    f"History records: "
    f"{len(history_df):,}"
)


# ============================================================
# 5. Helper functions
# ============================================================

def is_wg_draft(
    draft_name: str,
) -> bool:
    """
    WG draft naming convention:

        draft-ietf-<wg>-<topic>
    """

    return draft_name.startswith(
        "draft-ietf-"
    )


def individual_topic(
    draft_name: str,
) -> str:
    """
    Remove the first component following 'draft-'.

    Example:

        draft-davie-ecn-mpls
        -> ecn-mpls

        draft-6tisch-enrollment-enhanced-beacon
        -> enrollment-enhanced-beacon
    """

    if not draft_name.startswith(
        "draft-"
    ):
        return ""

    parts = draft_name.split("-")

    if len(parts) < 3:
        return ""

    return "-".join(
        parts[2:]
    ).lower()


def wg_topic(
    draft_name: str,
) -> str:
    """
    Remove:

        draft-ietf-<wg>-

    Example:

        draft-ietf-tsvwg-ecn-mpls
        -> ecn-mpls
    """

    if not draft_name.startswith(
        "draft-ietf-"
    ):
        return ""

    parts = draft_name.split("-")

    if len(parts) < 4:
        return ""

    return "-".join(
        parts[3:]
    ).lower()


def topic_is_specific(
    topic: str,
) -> bool:
    """
    Conservative test for whether a topic is sufficiently
    specific to be useful for a cross-check.

    We intentionally prefer precision over recall.
    """

    if not topic:
        return False

    topic = topic.strip().lower()

    if topic in GENERIC_TOPICS:
        return False

    tokens = [
        token
        for token in topic.split("-")
        if token
    ]

    # Single very short terms such as:
    #   api, qos, sip, cap
    # are too ambiguous.
    if len(tokens) == 1:
        if len(topic) < 8:
            return False

    return True


def uri_text(
    value,
) -> str:
    """
    Convert ietfdata URI objects into stable strings.
    """

    if value is None:
        return ""

    uri = getattr(
        value,
        "uri",
        None,
    )

    if uri:
        return str(uri)

    return str(value)


def person_id_from_author(
    author,
) -> str:
    """
    Prefer Datatracker Person URI as the stable identity.

    Fall back to email URI where Person information is
    unavailable.
    """

    person = getattr(
        author,
        "person",
        None,
    )

    person_text = uri_text(
        person
    )

    if person_text:
        return person_text

    email = getattr(
        author,
        "email",
        None,
    )

    return uri_text(
        email
    )


# ============================================================
# 6. Construct draft -> lineage mapping
# ============================================================

print()
print("=" * 72)
print("BUILDING DRAFT INDEX")
print("=" * 72)

draft_to_lineage: dict[str, str] = {}

for _, row in history_df.iterrows():

    draft_name = row[
        "draft_name"
    ]

    lineage_id = row[
        "lineage_id"
    ]

    if not draft_name:
        continue

    draft_to_lineage[
        draft_name
    ] = lineage_id


all_drafts = sorted(
    draft_to_lineage.keys()
)

individual_drafts = [
    name
    for name in all_drafts
    if not is_wg_draft(name)
]

wg_drafts = [
    name
    for name in all_drafts
    if is_wg_draft(name)
]


print(
    f"Draft documents: "
    f"{len(all_drafts):,}"
)

print(
    f"Individual/non-WG drafts: "
    f"{len(individual_drafts):,}"
)

print(
    f"WG drafts: "
    f"{len(wg_drafts):,}"
)


# ============================================================
# 7. Determine first observed date for each draft
# ============================================================

history_df[
    "date_parsed"
] = pd.to_datetime(
    history_df["date"],
    errors="coerce",
    utc=True,
)


draft_first_date = (
    history_df
    .dropna(
        subset=[
            "date_parsed"
        ]
    )
    .groupby(
        "draft_name"
    )["date_parsed"]
    .min()
    .to_dict()
)


# ============================================================
# 8. Build topic indexes
#
# Important:
# We do NOT compare every Individual draft against every WG
# draft. That would require hundreds of millions of comparisons.
#
# Instead, WG drafts are indexed by their normalised topic.
# ============================================================

print()
print("=" * 72)
print("INDEXING DRAFT NAMES")
print("=" * 72)


wg_by_topic: dict[
    str,
    list[str],
] = defaultdict(list)


for draft_name in wg_drafts:

    topic = wg_topic(
        draft_name
    )

    if not topic_is_specific(
        topic
    ):
        continue

    wg_by_topic[
        topic
    ].append(
        draft_name
    )


print(
    f"Specific WG topics: "
    f"{len(wg_by_topic):,}"
)


# ============================================================
# 9. Stage 1:
# Exact, specific name candidates
# ============================================================

print()
print("=" * 72)
print("STAGE 1: NAME CROSS-CHECK")
print("=" * 72)


name_candidates = []


for individual_name in individual_drafts:

    topic = individual_topic(
        individual_name
    )

    if not topic_is_specific(
        topic
    ):
        continue

    matching_wg_drafts = (
        wg_by_topic.get(
            topic,
            [],
        )
    )

    for wg_name in matching_wg_drafts:

        individual_lineage = (
            draft_to_lineage[
                individual_name
            ]
        )

        wg_lineage = (
            draft_to_lineage[
                wg_name
            ]
        )

        # If already in same reconstructed lineage,
        # there is nothing to cross-check.
        if (
            individual_lineage
            == wg_lineage
        ):
            continue

        individual_date = (
            draft_first_date.get(
                individual_name
            )
        )

        wg_date = (
            draft_first_date.get(
                wg_name
            )
        )

        name_candidates.append(
            {
                "individual_draft":
                    individual_name,

                "individual_lineage":
                    individual_lineage,

                "wg_draft":
                    wg_name,

                "wg_lineage":
                    wg_lineage,

                "topic":
                    topic,

                "individual_first_date":
                    (
                        individual_date.isoformat()
                        if individual_date is not None
                        else ""
                    ),

                "wg_first_date":
                    (
                        wg_date.isoformat()
                        if wg_date is not None
                        else ""
                    ),
            }
        )


name_df = pd.DataFrame(
    name_candidates
)


if not name_df.empty:

    name_df = (
        name_df
        .sort_values(
            [
                "topic",
                "individual_draft",
                "wg_draft",
            ]
        )
        .reset_index(
            drop=True
        )
    )


name_df.to_csv(
    NAME_CANDIDATE_FILE,
    index=False,
)


print(
    f"Specific name candidates: "
    f"{len(name_df):,}"
)


# ============================================================
# 10. Stage 2:
# Chronological filtering
#
# Individual draft must appear before WG draft.
# ============================================================

print()
print("=" * 72)
print("STAGE 2: CHRONOLOGY")
print("=" * 72)


chronology_rows = []


for _, row in name_df.iterrows():

    individual_name = row[
        "individual_draft"
    ]

    wg_name = row[
        "wg_draft"
    ]

    individual_date = (
        draft_first_date.get(
            individual_name
        )
    )

    wg_date = (
        draft_first_date.get(
            wg_name
        )
    )

    if (
        individual_date is None
        or wg_date is None
    ):
        continue

    # Adoption should move from the earlier
    # Individual draft to the later WG draft.
    if individual_date >= wg_date:
        continue

    gap_days = (
        wg_date
        - individual_date
    ).days

    chronology_rows.append(
        {
            **row.to_dict(),

            "gap_days":
                gap_days,

            "chronology_ok":
                1,
        }
    )


chronology_df = pd.DataFrame(
    chronology_rows
)


if not chronology_df.empty:

    chronology_df = (
        chronology_df
        .sort_values(
            [
                "individual_first_date",
                "wg_first_date",
                "topic",
            ]
        )
        .reset_index(
            drop=True
        )
    )


chronology_df.to_csv(
    CHRONOLOGY_FILE,
    index=False,
)


print(
    f"Chronologically plausible candidates: "
    f"{len(chronology_df):,}"
)


# ============================================================
# 11. Load Datatracker Document objects
#
# This uses the supervisor-provided ietfdata library.
# ============================================================

print()
print("=" * 72)
print("LOADING DATATRACKER DOCUMENTS")
print("=" * 72)


draft_type = (
    dt.document_type_from_slug(
        "draft"
    )
)


documents_by_name = {
    document.name: document
    for document in dt.documents(
        doctype=draft_type
    )
}


print(
    f"Datatracker draft Documents: "
    f"{len(documents_by_name):,}"
)


# ============================================================
# 12. Author cache
#
# Only retrieve authors for documents that survived the first
# two filters.
# ============================================================

author_cache: dict[
    str,
    set[str],
] = {}


def authors_for_draft(
    draft_name: str,
) -> set[str]:
    """
    Return stable Datatracker participant identities for a draft.
    """

    if draft_name in author_cache:
        return author_cache[
            draft_name
        ]

    document = (
        documents_by_name.get(
            draft_name
        )
    )

    if document is None:

        author_cache[
            draft_name
        ] = set()

        return set()

    authors: set[str] = set()

    try:

        for author in (
            dt.document_authors(
                document
            )
        ):

            participant = (
                person_id_from_author(
                    author
                )
            )

            if participant:
                authors.add(
                    participant
                )

    except Exception as error:

        print(
            f"WARNING: could not read authors "
            f"for {draft_name}: {error}"
        )

    author_cache[
        draft_name
    ] = authors

    return authors


# ============================================================
# 13. Stage 3:
# Author-overlap cross-check
# ============================================================

print()
print("=" * 72)
print("STAGE 3: AUTHOR OVERLAP")
print("=" * 72)


high_confidence_rows = []


for index, row in (
    chronology_df.iterrows()
):

    individual_name = row[
        "individual_draft"
    ]

    wg_name = row[
        "wg_draft"
    ]

    individual_authors = (
        authors_for_draft(
            individual_name
        )
    )

    wg_authors = (
        authors_for_draft(
            wg_name
        )
    )

    overlap = (
        individual_authors
        & wg_authors
    )

    union = (
        individual_authors
        | wg_authors
    )


    overlap_count = len(
        overlap
    )

    if union:

        author_jaccard = (
            overlap_count
            / len(union)
        )

    else:

        author_jaccard = 0.0


    # Strong cross-check criterion:
    #
    #   1. same specific topic
    #   2. different reconstructed lineages
    #   3. Individual observed before WG
    #   4. at least one stable participant appears in both
    #
    if overlap_count < 1:
        continue


    high_confidence_rows.append(
        {
            **row.to_dict(),

            "individual_author_count":
                len(
                    individual_authors
                ),

            "wg_author_count":
                len(
                    wg_authors
                ),

            "author_overlap_count":
                overlap_count,

            "author_jaccard":
                round(
                    author_jaccard,
                    4,
                ),

            "overlapping_person_ids":
                ";".join(
                    sorted(
                        overlap
                    )
                ),

            "confidence":
                "high",
        }
    )


    if (
        (index + 1) % 100
        == 0
    ):

        print(
            f"Checked "
            f"{index + 1:,} / "
            f"{len(chronology_df):,}"
        )


high_confidence_df = (
    pd.DataFrame(
        high_confidence_rows
    )
)


if not high_confidence_df.empty:

    high_confidence_df = (
        high_confidence_df
        .sort_values(
            [
                "author_overlap_count",
                "author_jaccard",
                "gap_days",
            ],
            ascending=[
                False,
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )


high_confidence_df.to_csv(
    HIGH_CONFIDENCE_FILE,
    index=False,
)


print(
    f"High-confidence possible "
    f"missing links: "
    f"{len(high_confidence_df):,}"
)
# ============================================================
# 14. Priority candidates for manual inspection
# ============================================================

PRIORITY_FILE = (
    OUTPUT_DIR
    / "04_priority_candidates.csv"
)

if not high_confidence_df.empty:

    priority_df = high_confidence_df.copy()

    # A short time gap makes an Individual -> WG transition
    # more plausible, but long-gap cases are retained in the
    # full candidate file rather than automatically rejected.
    priority_df["priority_score"] = (
        priority_df["author_overlap_count"] * 10
        + priority_df["author_jaccard"] * 10
        - priority_df["gap_days"] / 365.25
    )

    priority_df = (
        priority_df
        .sort_values(
            [
                "gap_days",
                "author_overlap_count",
                "author_jaccard",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )
        .reset_index(drop=True)
    )

    priority_df.to_csv(
        PRIORITY_FILE,
        index=False,
    )

    print(
        f"Priority candidates saved: "
        f"{PRIORITY_FILE}"
    )

# ============================================================
# 14. Summary
# ============================================================

summary_df = pd.DataFrame(
    [
        {
            "stage":
                "all_reconstructed_lineages",

            "count":
                len(lineage_df),
        },
        {
            "stage":
                "all_draft_documents",

            "count":
                len(all_drafts),
        },
        {
            "stage":
                "individual_non_wg_drafts",

            "count":
                len(individual_drafts),
        },
        {
            "stage":
                "wg_drafts",

            "count":
                len(wg_drafts),
        },
        {
            "stage":
                "specific_name_candidates",

            "count":
                len(name_df),
        },
        {
            "stage":
                "chronology_candidates",

            "count":
                len(chronology_df),
        },
        {
            "stage":
                "high_confidence_author_overlap",

            "count":
                len(
                    high_confidence_df
                ),
        },
    ]
)


summary_df.to_csv(
    SUMMARY_FILE,
    index=False,
)


# ============================================================
# 15. Final output
# ============================================================

print()
print("=" * 72)
print("CROSS-CHECK COMPLETE")
print("=" * 72)

print(
    f"Name candidates: "
    f"{len(name_df):,}"
)

print(
    f"Chronology candidates: "
    f"{len(chronology_df):,}"
)

print(
    f"High-confidence candidates: "
    f"{len(high_confidence_df):,}"
)

print()

print(
    f"Stage 1: "
    f"{NAME_CANDIDATE_FILE}"
)

print(
    f"Stage 2: "
    f"{CHRONOLOGY_FILE}"
)

print(
    f"Stage 3: "
    f"{HIGH_CONFIDENCE_FILE}"
)

print(
    f"Summary: "
    f"{SUMMARY_FILE}"
)