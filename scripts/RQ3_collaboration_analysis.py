from __future__ import annotations

from math import sqrt
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from scipy.stats import (
    mannwhitneyu,
    chi2_contingency,
)


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
    / "rq_analysis_dataset.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "RQ3"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. Load dataset
# ============================================================

df = pd.read_csv(
    INPUT_FILE
)


print(
    "Total lineages:",
    len(df)
)


# ============================================================
# 3. Keep known publication outcomes
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
    "\nKnown-outcome lineages:",
    len(
        analysis_df
    )
)


print(
    analysis_df[
        "publication_outcome"
    ].value_counts()
)


# ============================================================
# RQ3-A
# AUTHOR PARTICIPATION
# ============================================================

print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ3-A: AUTHOR PARTICIPATION"
)

print(
    "=" * 70
)


# ------------------------------------------------------------
# 4. Check missing author information
#
# author_count = 0 means no usable person_reference
# was identified.
# ------------------------------------------------------------

print(
    "\nAuthor count distribution:"
)

print(
    analysis_df[
        "author_count"
    ].describe()
)


zero_author_count = (
    analysis_df[
        "author_count"
    ] == 0
).sum()


print(
    "\nLineages with author_count = 0:",
    zero_author_count
)


# ------------------------------------------------------------
# 5. Use lineages with at least one identified author
# ------------------------------------------------------------

author_df = analysis_df[
    analysis_df[
        "author_count"
    ] > 0
].copy()


# ------------------------------------------------------------
# 6. Descriptive statistics
# ------------------------------------------------------------

author_summary = (
    author_df
    .groupby(
        "publication_outcome"
    )[
        "author_count"
    ]
    .agg(
        [
            "count",
            "mean",
            "median",
            "min",
            "max",
        ]
    )
)


# Add Q1 and Q3

author_q1 = (
    author_df
    .groupby(
        "publication_outcome"
    )[
        "author_count"
    ]
    .quantile(
        0.25
    )
)


author_q3 = (
    author_df
    .groupby(
        "publication_outcome"
    )[
        "author_count"
    ]
    .quantile(
        0.75
    )
)


author_summary[
    "Q1"
] = author_q1


author_summary[
    "Q3"
] = author_q3


# Reorder columns

author_summary = author_summary[
    [
        "count",
        "mean",
        "median",
        "Q1",
        "Q3",
        "min",
        "max",
    ]
]


print(
    "\nAuthor participation summary:"
)

print(
    author_summary
)


# ------------------------------------------------------------
# 7. Mann-Whitney U test
#
# author_count is a count variable and is likely skewed,
# so a non-parametric comparison is appropriate.
# ------------------------------------------------------------

successful_authors = author_df[
    author_df[
        "publication_outcome"
    ] == "Successful"
][
    "author_count"
]


unsuccessful_authors = author_df[
    author_df[
        "publication_outcome"
    ] == "Unsuccessful"
][
    "author_count"
]


u_statistic, author_p_value = (
    mannwhitneyu(
        successful_authors,
        unsuccessful_authors,
        alternative="two-sided",
    )
)


print(
    "\nMann-Whitney U test:"
)

print(
    "U statistic:",
    u_statistic
)

print(
    "p-value:",
    author_p_value
)


# ------------------------------------------------------------
# 8. Author count boxplot
# ------------------------------------------------------------

plt.figure(
    figsize=(7, 5)
)


plt.boxplot(
    [
        successful_authors,
        unsuccessful_authors,
    ],
    tick_labels=[
        "Successful",
        "Unsuccessful",
    ],
    showfliers=False,
)


plt.ylabel(
    "Number of Unique Authors"
)

plt.xlabel(
    "Publication Outcome"
)

plt.title(
    "Author Participation by Internet-Draft Lineage Publication Outcome"
)


plt.tight_layout()


plt.savefig(
    OUTPUT_DIR
    / "rq3_author_count_boxplot.png",
    dpi=300,
)


plt.show()


# ============================================================
# RQ3-B
# ORGANISATIONAL COLLABORATION
# ============================================================

print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ3-B: CROSS-ORGANISATIONAL COLLABORATION"
)

print(
    "=" * 70
)


# ------------------------------------------------------------
# 9. Affiliation data-quality summary
# ------------------------------------------------------------

print(
    "\nAffiliation mapping summary:"
)


print(
    analysis_df[
        [
            "affiliation_mapped_records",
            "affiliation_unresolved_records",
        ]
    ].describe()
)


# ------------------------------------------------------------
# 10. Clean affiliation subset
#
# Requirements:
#
# 1. At least one affiliation was successfully mapped.
# 2. No unresolved affiliation records remain.
#
# This avoids interpreting missing affiliation
# information as evidence of a single organisation.
# ------------------------------------------------------------

organisation_df = analysis_df[
    (
        analysis_df[
            "affiliation_mapped_records"
        ] > 0
    )
    &
    (
        analysis_df[
            "affiliation_unresolved_records"
        ] == 0
    )
].copy()


print(
    "\nKnown-outcome lineages:",
    len(
        analysis_df
    )
)

print(
    "Clean affiliation lineages:",
    len(
        organisation_df
    )
)


# ------------------------------------------------------------
# 11. Define collaboration category
# ------------------------------------------------------------

organisation_df[
    "collaboration_type"
] = organisation_df[
    "organisation_count"
].apply(
    lambda value:
        (
            "Cross-organisation"
            if value >= 2
            else "Single organisation"
        )
)


print(
    "\nCollaboration type:"
)

print(
    organisation_df[
        "collaboration_type"
    ].value_counts()
)


# ------------------------------------------------------------
# 12. Organisation count descriptive statistics
# ------------------------------------------------------------

organisation_summary = (
    organisation_df
    .groupby(
        "publication_outcome"
    )[
        "organisation_count"
    ]
    .agg(
        [
            "count",
            "mean",
            "median",
            "min",
            "max",
        ]
    )
)


organisation_summary[
    "Q1"
] = (
    organisation_df
    .groupby(
        "publication_outcome"
    )[
        "organisation_count"
    ]
    .quantile(
        0.25
    )
)


organisation_summary[
    "Q3"
] = (
    organisation_df
    .groupby(
        "publication_outcome"
    )[
        "organisation_count"
    ]
    .quantile(
        0.75
    )
)


organisation_summary = (
    organisation_summary[
        [
            "count",
            "mean",
            "median",
            "Q1",
            "Q3",
            "min",
            "max",
        ]
    ]
)


print(
    "\nOrganisation count summary:"
)

print(
    organisation_summary
)


# ============================================================
# 13. Cross-organisation contingency table
# ============================================================

contingency = pd.crosstab(
    organisation_df[
        "collaboration_type"
    ],
    organisation_df[
        "publication_outcome"
    ],
)


contingency = contingency.reindex(
    index=[
        "Cross-organisation",
        "Single organisation",
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
    "CROSS-ORGANISATION CONTINGENCY TABLE"
)

print(
    "=" * 70
)


print(
    contingency
)


# ============================================================
# 14. Success rates
# ============================================================

summary_rows = []


for collaboration_type in [
    "Cross-organisation",
    "Single organisation",
]:

    successful = contingency.loc[
        collaboration_type,
        "Successful",
    ]

    unsuccessful = contingency.loc[
        collaboration_type,
        "Unsuccessful",
    ]

    total = (
        successful
        +
        unsuccessful
    )


    if total > 0:

        success_rate = (
            successful
            /
            total
            *
            100
        )

    else:

        success_rate = None


    summary_rows.append(
        {
            "collaboration_type":
                collaboration_type,

            "successful":
                successful,

            "unsuccessful":
                unsuccessful,

            "known_outcomes":
                total,

            "success_rate_percent":
                success_rate,
        }
    )


collaboration_summary = pd.DataFrame(
    summary_rows
)


print(
    "\nCross-organisation success rates:"
)

print(
    collaboration_summary.to_string(
        index=False
    )
)


# ============================================================
# 15. Chi-square
# ============================================================

chi2, p_value, dof, expected = (
    chi2_contingency(
        contingency.values,
        correction=False,
    )
)


n = contingency.values.sum()


cramers_v = sqrt(
    chi2
    /
    n
)


print(
    "\nChi-square test:"
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

print(
    "Cramer's V:",
    round(
        cramers_v,
        4,
    )
)


# ============================================================
# 16. Odds ratio
#
# Cross-organisation versus single organisation
# ============================================================

a = contingency.loc[
    "Cross-organisation",
    "Successful",
]

b = contingency.loc[
    "Cross-organisation",
    "Unsuccessful",
]

c = contingency.loc[
    "Single organisation",
    "Successful",
]

d = contingency.loc[
    "Single organisation",
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
# 17. Success-rate bar chart
# ============================================================

plot_df = (
    collaboration_summary
    .set_index(
        "collaboration_type"
    )
    .reindex(
        [
            "Cross-organisation",
            "Single organisation",
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
    "Organisational Collaboration"
)

plt.title(
    "RFC Publication Success by Cross-Organisational Collaboration"
)

plt.ylim(
    0,
    100,
)


plt.tight_layout()


plt.savefig(
    OUTPUT_DIR
    / "rq3_cross_organisation_success_rate.png",
    dpi=300,
)


plt.show()


# ============================================================
# 18. Save small result tables only
# ============================================================

author_summary.to_csv(
    OUTPUT_DIR
    / "rq3_author_summary.csv",
    encoding="utf-8-sig",
)


organisation_summary.to_csv(
    OUTPUT_DIR
    / "rq3_organisation_summary.csv",
    encoding="utf-8-sig",
)


collaboration_summary.to_csv(
    OUTPUT_DIR
    / "rq3_collaboration_success_summary.csv",
    index=False,
    encoding="utf-8-sig",
)


contingency.to_csv(
    OUTPUT_DIR
    / "rq3_collaboration_contingency.csv",
    encoding="utf-8-sig",
)


print(
    "\nRQ3 analysis complete."
)

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)