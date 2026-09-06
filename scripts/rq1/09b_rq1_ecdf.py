from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTCOME_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "common"
    / "lineage_outcomes.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "rq1"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. Load dataset
# ============================================================

df = pd.read_csv(
    OUTCOME_FILE
)

print("=" * 72)
print("RQ1 ECDF FIGURES")
print("=" * 72)

print(
    f"Rows loaded: "
    f"{len(df):,}"
)


# ============================================================
# 3. Keep primary Successful / Unsuccessful sample
# ============================================================

required_columns = [
    "publication_outcome",
    "lineage_revision_count",
    "development_duration_days",
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise KeyError(
        f"Missing required columns: {missing}"
    )


analysis_df = df[
    df["publication_outcome"].isin(
        [
            "Successful",
            "Unsuccessful",
        ]
    )
].copy()


print(
    f"Primary sample: "
    f"{len(analysis_df):,}"
)

print(
    analysis_df[
        "publication_outcome"
    ].value_counts()
)


# ============================================================
# 4. Convert numerical columns
# ============================================================

for column in [
    "lineage_revision_count",
    "development_duration_days",
]:

    analysis_df[column] = pd.to_numeric(
        analysis_df[column],
        errors="coerce",
    )


# ============================================================
# 5. ECDF helper
# ============================================================

def ecdf(values):

    values = (
        pd.Series(values)
        .dropna()
        .to_numpy()
    )

    values = np.sort(
        values
    )

    n = len(values)

    if n == 0:
        return (
            np.array([]),
            np.array([]),
        )

    y = np.arange(
        1,
        n + 1,
    ) / n

    return values, y


# ============================================================
# 6. Generic ECDF plotting function
# ============================================================

def plot_ecdf(
    column,
    xlabel,
    title,
    filename,
):

    plt.figure(
        figsize=(8, 5.5)
    )

    for outcome in [
        "Successful",
        "Unsuccessful",
    ]:

        values = analysis_df.loc[
            analysis_df[
                "publication_outcome"
            ] == outcome,
            column,
        ]

        x, y = ecdf(
            values
        )

        plt.step(
            x,
            y,
            where="post",
            label=outcome,
        )

    plt.xlabel(
        xlabel
    )

    plt.ylabel(
        "Cumulative proportion"
    )

    plt.title(
        title
    )

    plt.ylim(
        0,
        1.01,
    )

    plt.grid(
        alpha=0.25
    )

    plt.legend()

    plt.tight_layout()

    output_path = (
        OUTPUT_DIR
        / filename
    )

    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close()

    print(
        f"Saved: {output_path}"
    )


# ============================================================
# 7. Revision count ECDF
# ============================================================

plot_ecdf(
    column="lineage_revision_count",
    xlabel="Revision count",
    title=(
        "Empirical Cumulative Distribution "
        "of Revision Count"
    ),
    filename="rq1_revision_count_ecdf.png",
)


# ============================================================
# 8. Development duration ECDF
# ============================================================

plot_ecdf(
    column="development_duration_days",
    xlabel="Development duration (days)",
    title=(
        "Empirical Cumulative Distribution "
        "of Development Duration"
    ),
    filename="rq1_duration_ecdf.png",
)


print()
print("=" * 72)
print("RQ1 ECDF COMPLETE")
print("=" * 72)