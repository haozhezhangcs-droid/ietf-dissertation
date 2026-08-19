from __future__ import annotations

from pathlib import Path
from math import sqrt

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2_contingency


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
)

INPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "CSV"
    / "lineage_dataset.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "RQ2"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. Load lineage dataset
# ============================================================

df = pd.read_csv(
    INPUT_FILE
)


print(
    "Total lineages:",
    len(df)
)


print(
    "\nOriginal WG status:"
)

print(
    df[
        "wg_status"
    ].value_counts(
        dropna=False
    )
)


# ============================================================
# 3. Define recorded WG assignment
#
# RQ2 is binary:
#
# wg_count = 0
#     -> No recorded WG
#
# wg_count >= 1
#     -> Recorded WG
#
# Multiple-WG lineages are therefore still included
# in the "Recorded WG" category.
# ============================================================

df[
    "wg_assignment"
] = df[
    "wg_count"
].apply(
    lambda value:
        "Recorded WG"
        if value >= 1
        else "No recorded WG"
)


print(
    "\nWG assignment:"
)

print(
    df[
        "wg_assignment"
    ].value_counts()
)


# ============================================================
# 4. Keep only known publication outcomes
#
# Ongoing and Unknown are not treated as failures.
# ============================================================

analysis_df = df[
    df[
        "publication_outcome"
    ].isin(
        [
            "Successful",
            "Unsuccessful",
        ]
    )
].copy()


print(
    "\nLineages used in RQ2:",
    len(
        analysis_df
    )
)


print(
    "\nPublication outcomes used:"
)

print(
    analysis_df[
        "publication_outcome"
    ].value_counts()
)


# ============================================================
# 5. Contingency table
# ============================================================

contingency = pd.crosstab(
    analysis_df[
        "wg_assignment"
    ],
    analysis_df[
        "publication_outcome"
    ],
)


# Ensure a fixed order.

contingency = contingency.reindex(
    index=[
        "Recorded WG",
        "No recorded WG",
    ],
    columns=[
        "Successful",
        "Unsuccessful",
    ],
    fill_value=0,
)


print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ2 CONTINGENCY TABLE"
)

print(
    "=" * 70
)

print(
    contingency
)


# ============================================================
# 6. Success rates
#
# Success rate =
#
# Successful
# -----------------------------
# Successful + Unsuccessful
#
# Ongoing and Unknown are excluded.
# ============================================================

summary_rows = []


for wg_assignment in [
    "Recorded WG",
    "No recorded WG",
]:

    successful = contingency.loc[
        wg_assignment,
        "Successful",
    ]

    unsuccessful = contingency.loc[
        wg_assignment,
        "Unsuccessful",
    ]

    total_known = (
        successful
        +
        unsuccessful
    )


    if total_known > 0:

        success_rate = (
            successful
            /
            total_known
            *
            100
        )

    else:

        success_rate = None


    summary_rows.append(
        {
            "wg_assignment":
                wg_assignment,

            "successful":
                successful,

            "unsuccessful":
                unsuccessful,

            "known_outcomes":
                total_known,

            "success_rate_percent":
                success_rate,
        }
    )


summary_df = pd.DataFrame(
    summary_rows
)


print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ2 SUCCESS RATES"
)

print(
    "=" * 70
)

print(
    summary_df.to_string(
        index=False
    )
)


# ============================================================
# 7. Chi-square test
#
# Tests whether WG assignment and publication outcome
# are statistically associated.
# ============================================================

chi2, p_value, dof, expected = (
    chi2_contingency(
        contingency.values,
        correction=False,
    )
)


print(
    "\n"
    +
    "=" * 70
)

print(
    "CHI-SQUARE TEST"
)

print(
    "=" * 70
)


print(
    "Chi-square:",
    round(
        chi2,
        4,
    )
)

print(
    "Degrees of freedom:",
    dof
)

print(
    "p-value:",
    p_value
)


# ============================================================
# 8. Cramer's V
#
# Effect-size measure for the relationship between
# two categorical variables.
#
# For a 2 x 2 table:
#
# V = sqrt(chi-square / N)
# ============================================================

n = contingency.values.sum()


cramers_v = sqrt(
    chi2
    /
    n
)


print(
    "Cramer's V:",
    round(
        cramers_v,
        4,
    )
)


# ============================================================
# 9. Odds ratio
#
# Compare odds of success:
#
# Recorded WG
# vs
# No recorded WG
# ============================================================

a = contingency.loc[
    "Recorded WG",
    "Successful",
]

b = contingency.loc[
    "Recorded WG",
    "Unsuccessful",
]

c = contingency.loc[
    "No recorded WG",
    "Successful",
]

d = contingency.loc[
    "No recorded WG",
    "Unsuccessful",
]


if (
    a > 0
    and
    b > 0
    and
    c > 0
    and
    d > 0
):

    odds_ratio = (
        a * d
    ) / (
        b * c
    )

else:

    odds_ratio = None


print(
    "Odds ratio:",
    (
        round(
            odds_ratio,
            4,
        )
        if odds_ratio is not None
        else "Not available"
    )
)


# ============================================================
# 10. Success-rate bar chart
# ============================================================

plot_df = (
    summary_df
    .set_index(
        "wg_assignment"
    )
    .reindex(
        [
            "Recorded WG",
            "No recorded WG",
        ]
    )
)


plt.figure(
    figsize=(7, 5)
)


plt.bar(
    plot_df.index,
    plot_df[
        "success_rate_percent"
    ],
)


plt.ylabel(
    "RFC Publication Success Rate (%)"
)

plt.xlabel(
    "Recorded Working Group Assignment"
)

plt.title(
    "RFC Publication Success by Recorded IETF Working Group Assignment"
)

plt.ylim(
    0,
    100,
)


plt.tight_layout()


plt.savefig(
    OUTPUT_DIR
    / "rq2_wg_success_rate.png",
    dpi=300,
)


plt.show()


# ============================================================
# 11. Save results
# ============================================================

summary_df.to_csv(
    OUTPUT_DIR
    / "rq2_wg_success_summary.csv",
    index=False,
    encoding="utf-8-sig",
)


contingency.to_csv(
    OUTPUT_DIR
    / "rq2_wg_contingency_table.csv",
    encoding="utf-8-sig",
)


analysis_df.to_csv(
    OUTPUT_DIR
    / "rq2_analysis_dataset.csv",
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 12. Additional diagnostic:
#     Single vs multiple WG
# ============================================================

print(
    "\n"
    +
    "=" * 70
)

print(
    "WG STATUS AMONG KNOWN OUTCOMES"
)

print(
    "=" * 70
)


print(
    pd.crosstab(
        analysis_df[
            "wg_status"
        ],
        analysis_df[
            "publication_outcome"
        ],
    )
)


print(
    "\nRQ2 analysis complete."
)

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)