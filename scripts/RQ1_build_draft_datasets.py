from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive
from ietfdata.datatracker_types import Document


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
)

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "draft_dataset.csv"
)


# ============================================================
# 2. Open database
# ============================================================

dt = DataTracker(
    DTBackendArchive(
        str(DATABASE_PATH)
    )
)


# ============================================================
# 3. Get Internet-Draft document type
# ============================================================

draft_type = dt.document_type_from_slug(
    "draft"
)

if draft_type is None:
    raise RuntimeError(
        "Could not find draft document type."
    )


# ============================================================
# 4. Find RFC directly produced by one draft
# ============================================================

def rfc_for_draft(
    draft_document: Document,
):

    relations = list(
        dt.related_documents(
            source=draft_document,
            relationship_type_slug="became_rfc",
        )
    )

    if not relations:
        return None

    relation = relations[0]

    return dt.document(
        relation.target
    )


# ============================================================
# 5. Build document, submission and replacement indexes
# ============================================================
last_submission_by_name = {}
# draft name -> complete Document object
drafts_by_name = {}

# draft name -> first submission date
first_submission_by_name = {}

# draft name -> number of unique revisions
revision_count_by_name = {}

# old draft -> set of drafts that claim to replace it
replacement_candidates = defaultdict(set)


processed = 0
submission_errors = 0


for draft_document in dt.documents(
    doctype=draft_type
):

    processed += 1

    draft_name = draft_document.name

    drafts_by_name[
        draft_name
    ] = draft_document


    # --------------------------------------------------------
    # Read submissions only once
    # --------------------------------------------------------

    dates = []

    revisions = set()


    for submission_uri in draft_document.submissions:

        try:

            submission = dt.submission(
                submission_uri
            )

        except Exception as error:

            submission_errors += 1

            print(
                "Submission error:",
                draft_name,
                "-",
                type(error).__name__,
                error,
            )

            continue


        # ----------------------------------------------------
        # Submission date
        # ----------------------------------------------------

        if submission.submission_date is not None:

            dates.append(
                submission.submission_date
            )


        # ----------------------------------------------------
        # Revision
        # ----------------------------------------------------

        if submission.rev is not None:

            revisions.add(
                submission.rev
            )


        # ----------------------------------------------------
        # Replacement information
        #
        # New draft:
        # submission.replaces = old draft name
        #
        # Therefore:
        #
        # old draft -> new draft
        # ----------------------------------------------------

        if submission.replaces:

            old_names = [
                name.strip()
                for name in submission.replaces.split(",")
                if name.strip()
            ]

            
            for old_name in old_names:

    # Ignore self-replacement records.
                if old_name == draft_name:
                    continue

                replacement_candidates[
                    old_name
                ].add(
                    draft_name
            )

    # --------------------------------------------------------
    # Save first submission
    # --------------------------------------------------------

   

    # --------------------------------------------------------
# Save first and last submission
# --------------------------------------------------------

    if dates:

        first_submission_by_name[
            draft_name
        ] = min(dates)

        last_submission_by_name[
            draft_name
        ] = max(dates)

    else:

        first_submission_by_name[
            draft_name
        ] = None

        last_submission_by_name[
            draft_name
        ] = None

    # --------------------------------------------------------
    # Save revision count
    # --------------------------------------------------------

    revision_count_by_name[
        draft_name
    ] = len(revisions)


    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    if processed % 500 == 0:

        print(
            f"Indexed {processed:,} drafts",
            flush=True,
        )


print("\nInitial indexing summary")
print("-" * 60)

print(
    "Draft documents indexed:",
    len(drafts_by_name)
)

print(
    "Submission read errors:",
    submission_errors
)

print(
    "Drafts mentioned in replaces:",
    len(replacement_candidates)
)


# ============================================================
# 6. Build successor graph
# ============================================================

# old draft -> set of successor drafts
successors_by_name = {
    old_name: set(successors)
    for old_name, successors
    in replacement_candidates.items()
}


multiple_successors = {
    old_name: successors
    for old_name, successors
    in successors_by_name.items()
    if len(successors) > 1
}


print("\nReplacement graph summary")
print("-" * 60)

print(
    "Drafts with successor:",
    len(successors_by_name)
)

print(
    "Drafts with multiple successors:",
    len(multiple_successors)
)


# ============================================================
# 7. Find all reachable successor drafts
# ============================================================

def replacement_descendants(
    start_name: str,
):

    """
    Return every draft reachable from start_name
    through replacement relationships.

    Example:

        A -> B
        A -> C
        B -> D

    returns:

        {A, B, C, D}
    """

    visited = set()

    stack = [
        start_name
    ]


    while stack:

        current = stack.pop()


        if current in visited:
            continue


        visited.add(
            current
        )


        for successor in successors_by_name.get(
            current,
            set(),
        ):

            if successor not in visited:

                stack.append(
                    successor
                )


    return visited


# ============================================================
# 7. Convert replacement candidates into simple index
# ============================================================

# Because the validation above confirms that each old draft
# has at most one successor, we can now safely create:
#
# old draft -> successor draft

replaced_by = {}


for old_name, successors in replacement_candidates.items():

    if not successors:
        continue

    successor_name = next(
        iter(successors)
    )

    replaced_by[
        old_name
    ] = successor_name


print(
    "Replacement relationships:",
    len(replaced_by)
)


# ============================================================
# 8. Cache direct became_rfc results
# ============================================================

# draft name -> RFC Document or None

direct_rfc_by_name = {}

processed_rfc_checks = 0
rfc_errors = 0


for draft_name, draft_document in drafts_by_name.items():

    processed_rfc_checks += 1

    try:

        direct_rfc_by_name[
            draft_name
        ] = rfc_for_draft(
            draft_document
        )

    except Exception as error:

        rfc_errors += 1

        direct_rfc_by_name[
            draft_name
        ] = None

        print(
            "RFC relationship error:",
            draft_name,
            "-",
            type(error).__name__,
            error,
        )


    if processed_rfc_checks % 500 == 0:

        print(
            f"Checked RFC relationship for "
            f"{processed_rfc_checks:,} drafts",
            flush=True,
        )


print("\nRFC relationship summary")
print("-" * 60)

print(
    "RFC relationship checks:",
    processed_rfc_checks
)

print(
    "RFC relationship errors:",
    rfc_errors
)


# ============================================================
# 9. Follow replacement chain
# ============================================================

def follow_replacement_chain(
    start_name: str,
):

    """
    Follow:

        draft-A
        -> draft-B
        -> draft-C

    until no successor is found.
    """

    chain = [
        start_name
    ]

    current = start_name

    visited = {
        start_name
    }


    while current in replaced_by:

        next_draft = replaced_by[
            current
        ]


        # Avoid accidental loops.
        if next_draft in visited:

            print(
                "Replacement loop detected:",
                start_name,
                "->",
                next_draft
            )

            break


        chain.append(
            next_draft
        )

        visited.add(
            next_draft
        )

        current = next_draft


    return chain


# ============================================================
# 10. Find RFC outcome for a lineage
# ============================================================

def rfc_for_lineage(
    chain,
):

    """
    Check each draft in a replacement chain.

    Return:
        RFC Document
        draft name that directly became the RFC

    If no RFC is found:
        None, None
    """

    for draft_name in chain:

        rfc_document = direct_rfc_by_name.get(
            draft_name
        )

        if rfc_document is not None:

            return (
                rfc_document,
                draft_name,
            )


    return (
        None,
        None,
    )


# ============================================================
# 11. Build final dataset
# ============================================================

rows = []

processed_rows = 0


for draft_name, draft_document in drafts_by_name.items():

    processed_rows += 1


    # --------------------------------------------------------
    # A. Direct became_rfc
    # --------------------------------------------------------

    direct_rfc_document = (
        direct_rfc_by_name.get(
            draft_name
        )
    )

    direct_became_rfc = (
        direct_rfc_document is not None
    )


    # --------------------------------------------------------
    # B. Immediate successor
    # --------------------------------------------------------

    successor_draft = replaced_by.get(
        draft_name,
        "",
    )


    # --------------------------------------------------------
    # C. Complete replacement chain
    # --------------------------------------------------------

    chain = follow_replacement_chain(
        draft_name
    )


    # --------------------------------------------------------
    # D. Final draft in lineage
    # --------------------------------------------------------

    lineage_final_draft = (
        chain[-1]
    )


    # --------------------------------------------------------
    # E. Check whether lineage became RFC
    # --------------------------------------------------------

    (
        lineage_rfc_document,
        lineage_rfc_draft,
    ) = rfc_for_lineage(
        chain
    )


    lineage_became_rfc = (
        lineage_rfc_document is not None
    )


    # --------------------------------------------------------
    # F. Existing variables
    # --------------------------------------------------------

    first_submission = (
        first_submission_by_name.get(
            draft_name
        )
    )

    last_submission = (
    last_submission_by_name.get(
        draft_name
        )
    )

    
    
    revision_count = (
        revision_count_by_name.get(
            draft_name,
            0,
        )
    )


    # --------------------------------------------------------
    # G. Add one row
    # --------------------------------------------------------

    rows.append(
        {
            "draft_name":
                draft_name,

            "direct_became_rfc":
                int(
                    direct_became_rfc
                ),

            "rfc_name":
                (
                    direct_rfc_document.name
                    if direct_rfc_document
                    is not None
                    else ""
                ),

            "last_submission":
                (
                    last_submission
                    if last_submission is not None
                    else ""
                ),

            "first_submission":
                (
                    first_submission
                    if first_submission
                    is not None
                    else ""
                ),

            "revision_count":
                revision_count,

            "successor_draft":
                successor_draft,

            "lineage_final_draft":
                lineage_final_draft,

            "lineage_became_rfc":
                int(
                    lineage_became_rfc
                ),

            "lineage_rfc_name":
                (
                    lineage_rfc_document.name
                    if lineage_rfc_document
                    is not None
                    else ""
                ),

            "lineage_rfc_draft":
                (
                    lineage_rfc_draft
                    if lineage_rfc_draft
                    is not None
                    else ""
                ),

            "lineage_length":
                len(chain),
        }
    )


    if processed_rows % 500 == 0:

        print(
            f"Built {processed_rows:,} dataset rows",
            flush=True,
        )


# ============================================================
# 12. Save CSV
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
)


with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "draft_name",
            "direct_became_rfc",
            "rfc_name",
            "first_submission",
            "last_submission",
            "revision_count",
            "successor_draft",
            "lineage_final_draft",
            "lineage_became_rfc",
            "lineage_rfc_name",
            "lineage_rfc_draft",
            "lineage_length",
        ],
    )

    writer.writeheader()

    writer.writerows(
        rows
    )


# ============================================================
# 13. Summary
# ============================================================

direct_success = sum(
    row["direct_became_rfc"]
    for row in rows
)

lineage_success = sum(
    row["lineage_became_rfc"]
    for row in rows
)

replaced_drafts = sum(
    1
    for row in rows
    if row["successor_draft"]
)

lineage_success_without_direct = sum(
    1
    for row in rows
    if (
        row["direct_became_rfc"] == 0
        and
        row["lineage_became_rfc"] == 1
    )
)


print("\nFinal dataset summary")
print("-" * 60)

print(
    "Rows created:",
    len(rows)
)

print(
    "Direct became_rfc:",
    direct_success
)

print(
    "Drafts with successor:",
    replaced_drafts
)

print(
    "Lineage became_rfc:",
    lineage_success
)

print(
    "No direct RFC but successful lineage:",
    lineage_success_without_direct
)

print(
    "\nSaved to:",
    OUTPUT_FILE
)