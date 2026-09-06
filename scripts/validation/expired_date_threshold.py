from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "expired_then_reactivated.csv"
SUMMARY_CSV = OUTPUT_DIR / "expiry_reactivation_summary.csv"
THRESHOLD_CSV = OUTPUT_DIR / "expiry_threshold_candidates.csv"
FIGURE_FILE = OUTPUT_DIR / "expiry_reactivation_distribution.png"

EXPIRY_MONTHS = 6


# ============================================================
# 2. Datatracker
# ============================================================

dt = DataTracker(
    DTBackendArchive(str(DB_PATH))
)

draft_type = dt.document_type_from_slug("draft")


# ============================================================
# 3. Find expired -> reactivated cases
# ============================================================

rows = []

documents_examined = 0
documents_with_reactivation = set()


for doc in dt.documents(doctype=draft_type):

    documents_examined += 1

    events = list(
        dt.document_events(
            doc=doc,
            event_type="new_revision"
        )
    )

    if len(events) < 2:
        continue

    events = sorted(
        [e for e in events if e.time is not None],
        key=lambda e: e.time
    )

    if len(events) < 2:
        continue

    for previous_event, next_event in zip(
        events[:-1],
        events[1:]
    ):

        previous_date = previous_event.time.date()
        next_date = next_event.time.date()

        estimated_expiry_date = (
            previous_date
            + relativedelta(months=EXPIRY_MONTHS)
        )

        # If next revision came after expiry,
        # then this draft expired and later returned.
        if next_date <= estimated_expiry_date:
            continue

        delay_days = (
            next_date - estimated_expiry_date
        ).days

        revision_gap_days = (
            next_date - previous_date
        ).days

        rows.append(
            {
                "draft_name": doc.name,

                "previous_revision":
                    previous_event.rev,

                "previous_revision_date":
                    previous_date,

                "estimated_expiry_date":
                    estimated_expiry_date,

                "next_revision":
                    next_event.rev,

                "next_revision_date":
                    next_date,

                "revision_gap_days":
                    revision_gap_days,

                "post_expiry_delay_days":
                    delay_days,

                "post_expiry_delay_months":
                    delay_days / 30.4375,
            }
        )

        documents_with_reactivation.add(doc.name)


# ============================================================
# 4. Save raw cases
# ============================================================

df = pd.DataFrame(rows)

df.to_csv(
    OUTPUT_CSV,
    index=False
)


print()
print("============================================")
print("Expired -> Reactivated Analysis")
print("============================================")
print(
    f"Draft documents examined: "
    f"{documents_examined:,}"
)
print(
    f"Drafts with >=1 reactivation: "
    f"{len(documents_with_reactivation):,}"
)
print(
    f"Total reactivation episodes: "
    f"{len(df):,}"
)


# ============================================================
# 5. Summary statistics
# ============================================================

if df.empty:
    raise RuntimeError(
        "No expired -> reactivated cases found."
    )


delays = df["post_expiry_delay_days"]

summary = {
    "reactivation_episodes":
        len(df),

    "unique_drafts":
        df["draft_name"].nunique(),

    "median_days":
        delays.median(),

    "p75_days":
        delays.quantile(0.75),

    "p90_days":
        delays.quantile(0.90),

    "p95_days":
        delays.quantile(0.95),

    "p99_days":
        delays.quantile(0.99),

    "maximum_days":
        delays.max(),
}


summary_df = pd.DataFrame([summary])

summary_df.to_csv(
    SUMMARY_CSV,
    index=False
)


print()
print("Reactivation delay distribution")
print("--------------------------------------------")

for name in [
    "median_days",
    "p75_days",
    "p90_days",
    "p95_days",
    "p99_days",
    "maximum_days",
]:
    days = summary[name]

    print(
        f"{name:15s}: "
        f"{days:8.1f} days "
        f"({days / 30.4375:6.2f} months)"
    )


# ============================================================
# 6. Candidate thresholds
# ============================================================

candidate_months = [
    1,
    3,
    6,
    9,
    12,
    18,
    24,
    36,
]

threshold_rows = []

for months in candidate_months:

    threshold_days = (
        months * 30.4375
    )

    after_threshold = (
        df["post_expiry_delay_days"]
        > threshold_days
    )

    count_after = int(
        after_threshold.sum()
    )

    proportion_after = (
        count_after / len(df)
    )

    threshold_rows.append(
        {
            "threshold_months":
                months,

            "reactivations_after_threshold":
                count_after,

            "total_reactivations":
                len(df),

            "proportion_after_threshold":
                proportion_after,
        }
    )


threshold_df = pd.DataFrame(
    threshold_rows
)

threshold_df.to_csv(
    THRESHOLD_CSV,
    index=False
)


print()
print("Candidate thresholds")
print("--------------------------------------------")

for _, row in threshold_df.iterrows():

    print(
        f"{int(row['threshold_months']):2d} months -> "
        f"{int(row['reactivations_after_threshold']):6,d} "
        f"later reactivations "
        f"({row['proportion_after_threshold']:.2%})"
    )


# ============================================================
# 7. Longest reactivations
# ============================================================

print()
print("Longest post-expiry reactivations")
print("--------------------------------------------")

longest = (
    df.sort_values(
        "post_expiry_delay_days",
        ascending=False
    )
    .head(20)
)

print(
    longest[
        [
            "draft_name",
            "previous_revision",
            "estimated_expiry_date",
            "next_revision",
            "next_revision_date",
            "post_expiry_delay_days",
            "post_expiry_delay_months",
        ]
    ].to_string(index=False)
)


# ============================================================
# 8. Plot
# ============================================================

plt.figure(
    figsize=(8, 5)
)

plt.hist(
    df["post_expiry_delay_months"],
    bins=60
)

plt.xlabel(
    "Months after expiry before next revision"
)

plt.ylabel(
    "Number of reactivation episodes"
)

plt.title(
    "Internet-Draft Reactivation After Expiry"
)

plt.tight_layout()

plt.savefig(
    FIGURE_FILE,
    dpi=300
)

plt.close()


print()
print("Saved:")
print(OUTPUT_CSV)
print(SUMMARY_CSV)
print(THRESHOLD_CSV)
print(FIGURE_FILE)