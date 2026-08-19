from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


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
    / "RQ1"
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
    "\nPublication outcomes:"
)

print(
    df[
        "publication_outcome"
    ].value_counts(
        dropna=False
    )
)


# ============================================================
# 3. Keep only known final outcomes
#
# Ongoing and Unknown are NOT treated as unsuccessful.
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
    "\nLineages used in RQ1:",
    len(analysis_df)
)


print(
    analysis_df[
        "publication_outcome"
    ].value_counts()
)


# ============================================================
# 4. Descriptive statistics helper
# ============================================================

def describe_variable(
    data,
    variable,
):

    print(
        "\n"
        +
        "=" * 70
    )

    print(
        variable
    )

    print(
        "=" * 70
    )


    for outcome in [
        "Successful",
        "Unsuccessful",
    ]:

        values = (
            data.loc[
                data[
                    "publication_outcome"
                ] == outcome,
                variable,
            ]
            .dropna()
        )


        print(
            f"\n{outcome}"
        )

        print(
            "N:",
            len(values)
        )

        print(
            "Mean:",
            round(
                values.mean(),
                2,
            )
        )

        print(
            "Median:",
            round(
                values.median(),
                2,
            )
        )

        print(
            "Q1:",
            round(
                values.quantile(
                    0.25
                ),
                2,
            )
        )

        print(
            "Q3:",
            round(
                values.quantile(
                    0.75
                ),
                2,
            )
        )

        print(
            "Min:",
            round(
                values.min(),
                2,
            )
        )

        print(
            "Max:",
            round(
                values.max(),
                2,
            )
        )


# ============================================================
# 5. RQ1 Variable 1:
#    Total revision count across lineage
# ============================================================

revision_df = analysis_df[
    analysis_df[
        "lineage_revision_count"
    ] > 0
].copy()


describe_variable(
    revision_df,
    "lineage_revision_count",
)


# ============================================================
# 6. RQ1 Variable 2:
#    Active development duration
# ============================================================

duration_df = analysis_df[
    analysis_df[
        "lineage_activity_duration_years"
    ].notna()
].copy()


describe_variable(
    duration_df,
    "lineage_activity_duration_years",
)


# ============================================================
# 7. RQ1 Variable 3:
#    Replacement lineage length
# ============================================================

describe_variable(
    analysis_df,
    "lineage_length",
)


# ============================================================
# 8. Boxplot:
#    Revision count
# ============================================================

successful_revision = (
    revision_df.loc[
        revision_df[
            "publication_outcome"
        ] == "Successful",
        "lineage_revision_count",
    ]
)

unsuccessful_revision = (
    revision_df.loc[
        revision_df[
            "publication_outcome"
        ] == "Unsuccessful",
        "lineage_revision_count",
    ]
)


plt.figure(
    figsize=(7, 5)
)

plt.boxplot(
    [
        successful_revision,
        unsuccessful_revision,
    ],
    tick_labels=[
        "Successful",
        "Unsuccessful",
    ],
    showfliers=False,
)

plt.ylabel(
    "Total Revision Count"
)

plt.xlabel(
    "Publication Outcome"
)

plt.title(
    "Revision Count by Internet-Draft Lineage Publication Outcome"
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR
    / "rq1_lineage_revision_count.png",
    dpi=300,
)

plt.show()


# ============================================================
# 9. Boxplot:
#    Activity duration
# ============================================================

successful_duration = (
    duration_df.loc[
        duration_df[
            "publication_outcome"
        ] == "Successful",
        "lineage_activity_duration_years",
    ]
)

unsuccessful_duration = (
    duration_df.loc[
        duration_df[
            "publication_outcome"
        ] == "Unsuccessful",
        "lineage_activity_duration_years",
    ]
)


plt.figure(
    figsize=(7, 5)
)

plt.boxplot(
    [
        successful_duration,
        unsuccessful_duration,
    ],
    tick_labels=[
    "Successful",
    "Unsuccessful",
],
    showfliers=False,
)

plt.ylabel(
    "Active Development Duration (Years)"
)

plt.xlabel(
    "Publication Outcome"
)

plt.title(
    "Development Activity Duration by Internet-Draft Lineage Outcome"
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR
    / "rq1_lineage_activity_duration.png",
    dpi=300,
)

plt.show()


# ============================================================
# 10. Boxplot:
#     Lineage length
# ============================================================

successful_length = (
    analysis_df.loc[
        analysis_df[
            "publication_outcome"
        ] == "Successful",
        "lineage_length",
    ]
)

unsuccessful_length = (
    analysis_df.loc[
        analysis_df[
            "publication_outcome"
        ] == "Unsuccessful",
        "lineage_length",
    ]
)


plt.figure(
    figsize=(7, 5)
)

plt.boxplot(
    [
        successful_length,
        unsuccessful_length,
    ],
    tick_labels=[
    "Successful",
    "Unsuccessful",
],
    showfliers=False,
)

plt.ylabel(
    "Number of Drafts in Lineage"
)

plt.xlabel(
    "Publication Outcome"
)

plt.title(
    "Replacement Lineage Length by Publication Outcome"
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR
    / "rq1_lineage_length.png",
    dpi=300,
)

plt.show()


# ============================================================
# 11. Save RQ1 analysis dataset
# ============================================================

analysis_df.to_csv(
    OUTPUT_DIR
    / "rq1_lineage_analysis_dataset.csv",
    index=False,
    encoding="utf-8-sig",
)


print(
    "\nRQ1 analysis complete."
)

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)