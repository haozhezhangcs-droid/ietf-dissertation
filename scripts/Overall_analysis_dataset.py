from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
)

DATABASE_FILE = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
)

RQ3_AUTHOR_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "CSV"
    / "rq3_author_affiliation_normalised.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "CSV"
    / "rq_analysis_dataset.csv"
)


# ============================================================
# 2. Outcome thresholds
# ============================================================

OBSERVATION_YEARS = 7
INACTIVITY_YEARS = 3

OBSERVATION_THRESHOLD_DAYS = (
    OBSERVATION_YEARS
    * 365.25
)

INACTIVITY_THRESHOLD_DAYS = (
    INACTIVITY_YEARS
    * 365.25
)


# ============================================================
# 3. Open Datatracker
# ============================================================

dt = DataTracker(
    DTBackendArchive(
        str(DATABASE_FILE)
    )
)

draft_type = (
    dt.document_type_from_slug(
        "draft"
    )
)


# ============================================================
# 4. Helper functions
# ============================================================

def uri_text(value):

    if value is None:
        return ""

    if hasattr(value, "uri"):
        return value.uri

    return str(value)


def is_working_group(group):

    if group is None:
        return False

    return uri_text(
        group.type
    ).endswith(
        "/wg/"
    )


def split_replaces(value):

    if value is None:
        return []

    text = str(value).strip()

    if not text:
        return []

    return [
        item.strip()
        for item in text.split(",")
        if item.strip()
    ]


# ============================================================
# 5. Load Internet-Drafts
# ============================================================

print(
    "Loading Internet-Drafts..."
)

draft_documents = {
    draft.name: draft
    for draft in dt.documents(
        doctype=draft_type
    )
}


print(
    "Draft documents:",
    len(draft_documents)
)


# ============================================================
# 6. Draft-level data
# ============================================================

first_submission_by_draft = {}
last_submission_by_draft = {}
revision_count_by_draft = {}

successors = defaultdict(set)

became_rfc_by_draft = {}

wg_by_draft = {}


# ============================================================
# 7. Submission history + replacement graph
# ============================================================

print(
    "\nReading submissions and replacements..."
)


for number, (
    draft_name,
    draft,
) in enumerate(
    draft_documents.items(),
    start=1,
):

    if number % 1000 == 0:

        print(
            "Processed drafts:",
            number
        )


    dates = []
    revisions = set()


    for submission_uri in draft.submissions:

        try:

            submission = dt.submission(
                submission_uri
            )

        except Exception:

            continue


        # ----------------------------------------------------
        # Submission date
        # ----------------------------------------------------

        if (
            submission.submission_date
            is not None
        ):

            dates.append(
                pd.Timestamp(
                    submission.submission_date
                )
            )


        # ----------------------------------------------------
        # Revision
        # ----------------------------------------------------

        if (
            submission.rev
            is not None
        ):

            revisions.add(
                str(
                    submission.rev
                )
            )


        # ----------------------------------------------------
        # Replacement
        #
        # B replaces A:
        #
        # A -> B
        # ----------------------------------------------------

        for old_name in split_replaces(
            submission.replaces
        ):

            if old_name == draft_name:
                continue

            if (
                old_name
                not in
                draft_documents
            ):
                continue

            successors[
                old_name
            ].add(
                draft_name
            )


    if dates:

        first_submission_by_draft[
            draft_name
        ] = min(
            dates
        )

        last_submission_by_draft[
            draft_name
        ] = max(
            dates
        )

    else:

        first_submission_by_draft[
            draft_name
        ] = None

        last_submission_by_draft[
            draft_name
        ] = None


    revision_count_by_draft[
        draft_name
    ] = len(
        revisions
    )


# ============================================================
# 8. became_rfc
# ============================================================

print(
    "\nReading became_rfc relationships..."
)


for number, (
    draft_name,
    draft,
) in enumerate(
    draft_documents.items(),
    start=1,
):

    if number % 2000 == 0:

        print(
            "RFC relationships checked:",
            number
        )


    try:

        relations = list(
            dt.related_documents(
                source=draft,
                relationship_type_slug=
                    "became_rfc",
            )
        )

    except Exception:

        relations = []


    became_rfc_by_draft[
        draft_name
    ] = (
        len(relations) > 0
    )


# ============================================================
# 9. Working Group assignment
# ============================================================

print(
    "\nReading Working Group assignments..."
)

group_cache = {}


for draft_name, draft in draft_documents.items():

    group_uri = getattr(
        draft,
        "group",
        None,
    )


    if group_uri is None:

        wg_by_draft[
            draft_name
        ] = None

        continue


    key = uri_text(
        group_uri
    )


    if key not in group_cache:

        try:

            group_cache[
                key
            ] = dt.group(
                group_uri
            )

        except Exception:

            group_cache[
                key
            ] = None


    group = group_cache[
        key
    ]


    if (
        group is not None
        and
        is_working_group(
            group
        )
    ):

        wg_by_draft[
            draft_name
        ] = group.acronym.lower()

    else:

        wg_by_draft[
            draft_name
        ] = None


# ============================================================
# 10. Build replacement components
# ============================================================

print(
    "\nBuilding replacement lineages..."
)

neighbours = defaultdict(set)


for old_name, new_names in successors.items():

    for new_name in new_names:

        neighbours[
            old_name
        ].add(
            new_name
        )

        neighbours[
            new_name
        ].add(
            old_name
        )


for draft_name in draft_documents:

    neighbours[
        draft_name
    ]


visited = set()
lineages = []


for start_name in sorted(
    draft_documents
):

    if start_name in visited:
        continue


    stack = [
        start_name
    ]

    members = set()


    while stack:

        current = stack.pop()

        if current in visited:
            continue


        visited.add(
            current
        )

        members.add(
            current
        )


        for neighbour in neighbours[
            current
        ]:

            if neighbour not in visited:

                stack.append(
                    neighbour
                )


    lineages.append(
        members
    )


print(
    "Replacement lineages:",
    len(lineages)
)


# ============================================================
# 11. Observation date
# ============================================================

valid_last_dates = [

    value

    for value
    in last_submission_by_draft.values()

    if value is not None
]


OBSERVATION_DATE = max(
    valid_last_dates
)


print(
    "Observation date:",
    OBSERVATION_DATE.date()
)


# ============================================================
# 12. Load RQ3 author / affiliation data
# ============================================================

print(
    "\nLoading RQ3 author data..."
)

author_df = pd.read_csv(
    RQ3_AUTHOR_FILE
)


authors_by_draft = defaultdict(set)
organisations_by_draft = defaultdict(set)

mapped_by_draft = defaultdict(int)
unresolved_by_draft = defaultdict(int)


for _, row in author_df.iterrows():

    draft_name = row[
        "draft_name"
    ]


    # --------------------------------------------------------
    # Author
    # --------------------------------------------------------

    person_reference = row.get(
        "person_reference"
    )


    if pd.notna(
        person_reference
    ):

        person_reference = str(
            person_reference
        ).strip()

        if person_reference:

            authors_by_draft[
                draft_name
            ].add(
                person_reference
            )


    # --------------------------------------------------------
    # Affiliation status
    # --------------------------------------------------------

    status = row.get(
        "normalisation_status"
    )


    if pd.isna(status):
        continue


    status = str(status)


    if status in {
        "alias_matched",
        "multi_organisation",
    }:

        mapped_by_draft[
            draft_name
        ] += 1


        organisation = row.get(
            "organisation_normalised"
        )


        if pd.notna(
            organisation
        ):

            for item in str(
                organisation
            ).split(";"):

                item = item.strip()

                if item:

                    organisations_by_draft[
                        draft_name
                    ].add(
                        item
                    )


    elif status in {
        "unmatched",
        "missing",
    }:

        unresolved_by_draft[
            draft_name
        ] += 1


# ============================================================
# 13. Build final RQ1-RQ3 dataset
# ============================================================

print(
    "\nBuilding final analysis dataset..."
)

records = []


for members in lineages:

    # ========================================================
    # Identifier
    #
    # Deterministic identifier for the component.
    # ========================================================

    lineage_id = min(
        members
    )


    # ========================================================
    # RQ1
    # ========================================================

    lineage_length = len(
        members
    )


    lineage_revision_count = sum(

        revision_count_by_draft.get(
            name,
            0,
        )

        for name in members
    )


    first_dates = [

        first_submission_by_draft.get(
            name
        )

        for name in members

        if first_submission_by_draft.get(
            name
        )
        is not None
    ]


    last_dates = [

        last_submission_by_draft.get(
            name
        )

        for name in members

        if last_submission_by_draft.get(
            name
        )
        is not None
    ]


    if (
        first_dates
        and
        last_dates
    ):

        lineage_first = min(
            first_dates
        )

        lineage_last = max(
            last_dates
        )


        activity_years = (
            (
                lineage_last
                -
                lineage_first
            ).days
            /
            365.25
        )


        observation_days = (
            OBSERVATION_DATE
            -
            lineage_first
        ).days


        inactivity_days = (
            OBSERVATION_DATE
            -
            lineage_last
        ).days


    else:

        lineage_first = None
        lineage_last = None

        activity_years = None

        observation_days = None
        inactivity_days = None


    # --------------------------------------------------------
    # Publication success
    # --------------------------------------------------------

    became_rfc = any(

        became_rfc_by_draft.get(
            name,
            False,
        )

        for name in members
    )


    if became_rfc:

        publication_outcome = (
            "Successful"
        )


    elif (
        observation_days is None
        or
        inactivity_days is None
    ):

        publication_outcome = (
            "Unknown"
        )


    elif (
        observation_days
        >=
        OBSERVATION_THRESHOLD_DAYS

        and

        inactivity_days
        >=
        INACTIVITY_THRESHOLD_DAYS
    ):

        publication_outcome = (
            "Unsuccessful"
        )


    else:

        publication_outcome = (
            "Ongoing"
        )


    # ========================================================
    # RQ2
    # ========================================================

    wg_names = {

        wg_by_draft[
            name
        ]

        for name in members

        if wg_by_draft.get(
            name
        )
        is not None
    }


    wg_count = len(
        wg_names
    )


    if wg_count >= 1:

        wg_assignment = (
            "Recorded WG"
        )

    else:

        wg_assignment = (
            "No recorded WG"
        )


    # ========================================================
    # RQ3
    # ========================================================

    authors = set()

    organisations = set()


    affiliation_mapped_records = 0
    affiliation_unresolved_records = 0


    for name in members:

        authors.update(
            authors_by_draft[
                name
            ]
        )

        organisations.update(
            organisations_by_draft[
                name
            ]
        )


        affiliation_mapped_records += (
            mapped_by_draft[
                name
            ]
        )

        affiliation_unresolved_records += (
            unresolved_by_draft[
                name
            ]
        )


    author_count = len(
        authors
    )


    organisation_count = len(
        organisations
    )


    cross_organisation = (
        organisation_count >= 2
    )


    # ========================================================
    # Save
    # ========================================================

    records.append(
        {
            "lineage_id":
                lineage_id,

            "publication_outcome":
                publication_outcome,

            # RQ1
            "lineage_revision_count":
                lineage_revision_count,

            "lineage_activity_duration_years":
                activity_years,

            "lineage_length":
                lineage_length,

            # RQ2
            "wg_assignment":
                wg_assignment,

            "wg_count":
                wg_count,

            # RQ3
            "author_count":
                author_count,

            "organisation_count":
                organisation_count,

            "cross_organisation":
                cross_organisation,

            "affiliation_mapped_records":
                affiliation_mapped_records,

            "affiliation_unresolved_records":
                affiliation_unresolved_records,
        }
    )


# ============================================================
# 14. Save
# ============================================================

analysis_df = pd.DataFrame(
    records
)


analysis_df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 15. Summary
# ============================================================

print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ1-RQ3 ANALYSIS DATASET"
)

print(
    "=" * 70
)


print(
    "Lineages:",
    len(
        analysis_df
    )
)


print(
    "\nPublication outcomes:"
)

print(
    analysis_df[
        "publication_outcome"
    ].value_counts()
)


print(
    "\nWG assignment:"
)

print(
    analysis_df[
        "wg_assignment"
    ].value_counts()
)


print(
    "\nCross-organisation:"
)

print(
    analysis_df[
        "cross_organisation"
    ].value_counts()
)


print(
    "\nOutput:"
)

print(
    OUTPUT_FILE
)