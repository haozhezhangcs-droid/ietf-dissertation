from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


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
    / "successful_draft_max_inactivity_gap.png"
)


# ============================================================
# 2. Open Datatracker
# ============================================================

dt = DataTracker(
    DTBackendArchive(
        str(DATABASE_PATH)
    )
)


# ============================================================
# 3. Obtain draft type
# ============================================================

draft_type = dt.document_type_from_slug(
    "draft"
)

if draft_type is None:
    raise RuntimeError(
        "Could not find draft document type."
    )


# ============================================================
# 4. Helper: check whether a draft directly became RFC
# ============================================================

def directly_became_rfc(
    draft_document,
):

    relations = list(
        dt.related_documents(
            source=draft_document,
            relationship_type_slug="became_rfc",
        )
    )

    return len(relations) > 0


# ============================================================
# 5. Helper: obtain all submission dates
# ============================================================

def submission_dates_for_draft(
    draft_document,
):

    dates = []


    for submission_uri in draft_document.submissions:

        try:

            submission = dt.submission(
                submission_uri
            )

        except Exception:
            continue


        if submission.submission_date is not None:

            dates.append(
                submission.submission_date
            )


    # Remove duplicates and sort chronologically.
    dates = sorted(
        set(dates)
    )

    return dates


# ============================================================
# 6. Helper: calculate maximum gap between submissions
# ============================================================

def maximum_submission_gap_days(
    submission_dates,
):

    # Need at least two submissions to calculate a gap.
    if len(submission_dates) < 2:
        return None


    gaps = []


    for index in range(
        1,
        len(submission_dates),
    ):

        previous_date = (
            submission_dates[
                index - 1
            ]
        )

        current_date = (
            submission_dates[
                index
            ]
        )


        gap_days = (
            current_date
            - previous_date
        ).days


        if gap_days >= 0:

            gaps.append(
                gap_days
            )


    if not gaps:
        return None


    return max(
        gaps
    )


# ============================================================
# 7. Analyse successful drafts
# ============================================================

maximum_gaps_days = []

processed = 0
successful = 0
successful_with_two_submissions = 0
successful_with_one_submission = 0
errors = 0


for draft_document in dt.documents(
    doctype=draft_type
):

    processed += 1


    try:

        # ----------------------------------------------------
        # Step 1:
        # Only analyse drafts that directly became RFC.
        # ----------------------------------------------------

        if not directly_became_rfc(
            draft_document
        ):

            continue


        successful += 1


        # ----------------------------------------------------
        # Step 2:
        # Obtain chronological submission dates.
        # ----------------------------------------------------

        submission_dates = (
            submission_dates_for_draft(
                draft_document
            )
        )


        # ----------------------------------------------------
        # Step 3:
        # Need at least two submissions to calculate inactivity.
        # ----------------------------------------------------

        if len(submission_dates) < 2:

            successful_with_one_submission += 1
            continue


        successful_with_two_submissions += 1


        # ----------------------------------------------------
        # Step 4:
        # Find maximum inactivity gap for this successful draft.
        # ----------------------------------------------------

        max_gap = maximum_submission_gap_days(
            submission_dates
        )


        if max_gap is None:
            continue


        maximum_gaps_days.append(
            max_gap
        )


        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if successful % 500 == 0:

            print(
                f"Successful drafts checked: "
                f"{successful:,}",
                flush=True,
            )


    except Exception as error:

        errors += 1

        print(
            "Skipping",
            draft_document.name,
            "-",
            type(error).__name__,
            error,
        )


# ============================================================
# 8. Validation summary
# ============================================================

print(
    "\nProcessing summary"
)

print(
    "-" * 60
)

print(
    "Draft documents checked:",
    processed
)

print(
    "Successful drafts:",
    successful
)

print(
    "Successful drafts with >= 2 submissions:",
    successful_with_two_submissions
)

print(
    "Successful drafts with < 2 submissions:",
    successful_with_one_submission
)

print(
    "Valid maximum-gap records:",
    len(maximum_gaps_days)
)

print(
    "Errors:",
    errors
)


if not maximum_gaps_days:

    raise RuntimeError(
        "No valid inactivity-gap records found."
    )


# ============================================================
# 9. Calculate percentiles
# ============================================================

median_gap = np.percentile(
    maximum_gaps_days,
    50,
)

p75_gap = np.percentile(
    maximum_gaps_days,
    75,
)

p90_gap = np.percentile(
    maximum_gaps_days,
    90,
)

p95_gap = np.percentile(
    maximum_gaps_days,
    95,
)

p99_gap = np.percentile(
    maximum_gaps_days,
    99,
)


print(
    "\nMaximum inactivity gap among successful drafts"
)

print(
    "-" * 60
)

print(
    f"Median (50%): "
    f"{median_gap:.0f} days "
    f"({median_gap / 365.25:.2f} years)"
)

print(
    f"75th percentile: "
    f"{p75_gap:.0f} days "
    f"({p75_gap / 365.25:.2f} years)"
)

print(
    f"90th percentile: "
    f"{p90_gap:.0f} days "
    f"({p90_gap / 365.25:.2f} years)"
)

print(
    f"95th percentile: "
    f"{p95_gap:.0f} days "
    f"({p95_gap / 365.25:.2f} years)"
)

print(
    f"99th percentile: "
    f"{p99_gap:.0f} days "
    f"({p99_gap / 365.25:.2f} years)"
)


# ============================================================
# 10. Draw distribution
# ============================================================

maximum_gaps_years = [
    days / 365.25
    for days in maximum_gaps_days
]


plt.figure(
    figsize=(10, 6)
)


plt.hist(
    maximum_gaps_years,
    bins=40,
)


plt.axvline(
    median_gap / 365.25,
    linestyle="--",
    label="Median",
)


plt.axvline(
    p95_gap / 365.25,
    linestyle="--",
    label="95th percentile",
)


plt.xlabel(
    "Maximum gap between consecutive submissions (years)"
)

plt.ylabel(
    "Number of successful drafts"
)

plt.title(
    "Maximum Inactivity Gap Among Successful Internet-Drafts"
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
    OUTPUT_FIGURE
)