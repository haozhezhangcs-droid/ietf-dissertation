#-------------------------------------------
#Observation window and Inactivity threshold  
#became_rfc = False
#AND
#observation_time >= 6 years
#AND
#last_activity > 3 years ago
#-------------------------------------------
from __future__ import annotations

from pathlib import Path
from statistics import median

import numpy as np
import matplotlib.pyplot as plt

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

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FIGURE = (
    OUTPUT_DIR
    / "draft_to_rfc_duration_distribution.png"
)


# ============================================================
# 2. Open Datatracker database
# ============================================================

dt = DataTracker(
    DTBackendArchive(
        str(DATABASE_PATH)
    )
)


# ============================================================
# 3. Find RFC publication time
# ============================================================

def publication_time_for_rfc(
    rfc_document: Document,
):

    events = list(
        dt.document_events(
            doc=rfc_document,
            event_type="published_rfc",
        )
    )

    if not events:
        return None

    return min(
        event.time
        for event in events
    )


# ============================================================
# 4. Find the RFC produced by a draft
# ============================================================

def follow_replacement_chain(
    start_name,
):

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

        if next_draft in visited:
            break

        chain.append(
            next_draft
        )

        visited.add(
            next_draft
        )

        current = next_draft

    return chain
def rfc_for_chain(
    chain,
):

    for draft_name in chain:

        draft_document = drafts_by_name[
            draft_name
        ]

        relations = list(
            dt.related_documents(
                source=draft_document,
                relationship_type_slug="became_rfc",
            )
        )

        if relations:

            relation = relations[0]

            return dt.document(
                relation.target
            )

    return None

# ============================================================
# 5. Find the first submission date of a draft
# ============================================================

def earliest_submission_time(
    chain,
):

    dates = []

    for draft_name in chain:

        draft_document = drafts_by_name[
            draft_name
        ]

        for submission_uri in draft_document.submissions:

            submission = dt.submission(
                submission_uri
            )

            if submission.submission_date is not None:

                dates.append(
                    submission.submission_date
                )

    if not dates:
        return None

    return min(
        dates
    )

# ============================================================
# 6. Obtain the Internet-Draft document type
# ============================================================

draft_type = dt.document_type_from_slug(
    "draft"
)

if draft_type is None:
    raise RuntimeError(
        "Could not find the draft document type."
    )

# ============================================================
# Build replacement index
# ============================================================

drafts_by_name = {}
replaced_by = {}

for draft_document in dt.documents(
    doctype=draft_type
):

    drafts_by_name[
        draft_document.name
    ] = draft_document

    for submission_uri in draft_document.submissions:

        try:
            submission = dt.submission(
                submission_uri
            )
        except Exception:
            continue

        if not submission.replaces:
            continue

        old_names = [
            name.strip()
            for name in submission.replaces.split(",")
            if name.strip()
        ]

        for old_name in old_names:

            replaced_by[
                old_name
            ] = draft_document.name

# ============================================================
# 7. Calculate development duration for successful lineages
# ============================================================

durations_days = []

processed_lineages = 0
successful_lineages = 0
missing_submission = 0
missing_publication = 0
negative_duration = 0
errors = 0


# ------------------------------------------------------------
# Helper: convert datetime to date when necessary
# ------------------------------------------------------------

def to_date(
    value,
):

    if value is None:
        return None

    # datetime.datetime has .date()
    # datetime.date normally does not need conversion
    if hasattr(value, "date"):

        try:
            return value.date()

        except TypeError:
            pass

    return value


# ------------------------------------------------------------
# Find all drafts which are themselves replacements
#
# Example:
#
# A -> B -> C
#
# B and C appear as values in replaced_by.
# Therefore only A is a lineage starting point.
# ------------------------------------------------------------

replacement_targets = set(
    replaced_by.values()
)


# ------------------------------------------------------------
# Find lineage roots
# ------------------------------------------------------------

lineage_roots = [
    draft_name
    for draft_name in drafts_by_name
    if draft_name not in replacement_targets
]


print(
    "\nLineage roots found:",
    len(lineage_roots)
)


# ------------------------------------------------------------
# Process each lineage only once
# ------------------------------------------------------------

for root_name in lineage_roots:

    processed_lineages += 1

    try:

        # ----------------------------------------------------
        # Step 1: Follow the complete replacement chain
        # ----------------------------------------------------

        chain = follow_replacement_chain(
            root_name
        )


        # ----------------------------------------------------
        # Step 2: Check whether any draft in this lineage
        # directly became an RFC
        # ----------------------------------------------------

        rfc_document = rfc_for_chain(
            chain
        )

        if rfc_document is None:
            continue


        successful_lineages += 1


        # ----------------------------------------------------
        # Step 3: Find earliest submission in the whole lineage
        # ----------------------------------------------------

        first_time = earliest_submission_time(
            chain
        )

        if first_time is None:

            missing_submission += 1
            continue


        # ----------------------------------------------------
        # Step 4: Find RFC publication time
        # ----------------------------------------------------

        publication_time = publication_time_for_rfc(
            rfc_document
        )

        if publication_time is None:

            missing_publication += 1
            continue


        # ----------------------------------------------------
        # Step 5: Convert both values to date
        # ----------------------------------------------------

        first_date = to_date(
            first_time
        )

        publication_date = to_date(
            publication_time
        )


        # ----------------------------------------------------
        # Step 6: Calculate lineage development duration
        # ----------------------------------------------------

        duration = (
            publication_date
            - first_date
        ).days


        if duration < 0:

            negative_duration += 1

            print(
                "Negative duration:",
                root_name,
                first_date,
                publication_date,
            )

            continue


        durations_days.append(
            duration
        )


        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if successful_lineages % 100 == 0:

            print(
                f"Successful lineages processed: "
                f"{successful_lineages:,}",
                flush=True,
            )


    except Exception as error:

        errors += 1

        print(
            "Skipping lineage",
            root_name,
            "-",
            type(error).__name__,
            error,
        )


# ============================================================
# 8. Print validation information
# ============================================================

print("\nProcessing summary")
print("-" * 60)

print(
    "Lineage roots checked:",
    processed_lineages,
)

print(
    "Successful lineages:",
    successful_lineages,
)

print(
    "Missing first submission:",
    missing_submission,
)

print(
    "Missing RFC publication time:",
    missing_publication,
)

print(
    "Negative duration records:",
    negative_duration,
)

print(
    "Errors:",
    errors,
)

print(
    "Valid duration records:",
    len(durations_days),
)


if not durations_days:

    raise RuntimeError(
        "No valid lineage-to-RFC durations found."
    )



# ============================================================
# 9. Calculate percentiles
# ============================================================

median_days = np.percentile(
    durations_days,
    50,
)

p75_days = np.percentile(
    durations_days,
    75,
)

p90_days = np.percentile(
    durations_days,
    90,
)

p95_days = np.percentile(
    durations_days,
    95,
)


print("\nDevelopment duration")
print("-" * 60)

print(
    f"Median (50%): "
    f"{median_days:.0f} days "
    f"({median_days / 365.25:.2f} years)"
)

print(
    f"75th percentile: "
    f"{p75_days:.0f} days "
    f"({p75_days / 365.25:.2f} years)"
)

print(
    f"90th percentile: "
    f"{p90_days:.0f} days "
    f"({p90_days / 365.25:.2f} years)"
)

print(
    f"95th percentile: "
    f"{p95_days:.0f} days "
    f"({p95_days / 365.25:.2f} years)"
)


# ============================================================
# 10. Draw duration distribution
# ============================================================

durations_years = [
    days / 365.25
    for days in durations_days
]


plt.figure(
    figsize=(10, 6)
)

plt.hist(
    durations_years,
    bins=40,
)

plt.xlabel(
    "Years from first Internet-Draft submission to RFC publication"
)

plt.ylabel(
    "Number of drafts"
)

plt.title(
    "Development Duration of Internet-Drafts "
    "That Became RFCs"
)

plt.axvline(
    median_days / 365.25,
    linestyle="--",
    label="Median",
)

plt.axvline(
    p95_days / 365.25,
    linestyle="--",
    label="95th percentile",
)

plt.legend()

plt.tight_layout()

plt.savefig(
    OUTPUT_FIGURE,
    dpi=300,
    bbox_inches="tight",
)

plt.show()


print(
    "\nFigure saved to:",
    OUTPUT_FIGURE,
)