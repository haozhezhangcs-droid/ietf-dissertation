from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Use the same formal outcome file as the other analysis scripts.
INPUT_FILE = (
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

FIGURE_DIR = (
    OUTPUT_DIR
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FIGURE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 2. Load data
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    dtype=str,
).fillna("")

print(
    f"Using lineage file: {INPUT_FILE}"
)


# ============================================================
# 3. Helpers
# ============================================================

def find_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
) -> str:
    """
    Return the first matching column name.
    """

    for column in candidates:
        if column in dataframe.columns:
            return column

    raise KeyError(
        "Could not find any of these columns: "
        + ", ".join(candidates)
    )


def numeric_series(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    """
    Convert a column to numeric and remove missing values.
    """

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    ).dropna()


def iqr(series: pd.Series) -> float:
    """
    Interquartile range:
    75th percentile - 25th percentile.
    """

    return (
        series.quantile(0.75)
        - series.quantile(0.25)
    )


def format_p_value(
    p_value: float,
) -> str:

    if p_value < 0.001:
        return "< 0.001"

    return f"{p_value:.4f}"


def rank_biserial_from_u(
    u_statistic: float,
    n_success: int,
    n_unsuccess: int,
) -> float:
    """
    Rank-biserial correlation derived from Mann-Whitney U.

    Positive value here means the Successful group tends
    to have larger values than the Unsuccessful group.
    """

    denominator = (
        n_success
        * n_unsuccess
    )

    if denominator == 0:
        return float("nan")

    return (
        (2 * u_statistic)
        / denominator
        - 1
    )


def effect_label(
    value: float,
) -> str:
    """
    Rough descriptive labels for absolute rank-biserial effect size.
    """

    abs_value = abs(value)

    if abs_value < 0.10:
        return "negligible"
    elif abs_value < 0.30:
        return "small"
    elif abs_value < 0.50:
        return "medium"
    else:
        return "large"


# ============================================================
# 4. Identify required columns
# ============================================================

outcome_col = find_column(
    df,
    [
        "publication_outcome",
        "outcome",
    ],
)


revision_col = find_column(
    df,
    [
        "lineage_revision_count",
        "revision_count",
        "total_revision_count",
    ],
)


lineage_length_col = find_column(
    df,
    [
        "lineage_length",
        "draft_count",
        "lineage_document_count",
    ],
)


# Development duration may already exist.
# If not, calculate it from first/last history dates.
duration_candidates = [
    "development_duration_days",
    "lineage_duration_days",
    "duration_days",
]

duration_col = ""

for candidate in duration_candidates:
    if candidate in df.columns:
        duration_col = candidate
        break


if not duration_col:

    first_date_col = find_column(
        df,
        [
            "first_history_date",
            "lineage_first_date",
            "first_date",
        ],
    )

    last_date_col = find_column(
        df,
        [
            "last_history_date",
            "lineage_last_date",
            "last_date",
        ],
    )

    first_dates = pd.to_datetime(
        df[first_date_col],
        errors="coerce",
    )

    last_dates = pd.to_datetime(
        df[last_date_col],
        errors="coerce",
    )

    df["development_duration_days"] = (
        last_dates
        - first_dates
    ).dt.days

    duration_col = (
        "development_duration_days"
    )


# ============================================================
# 5. Primary Successful / Unsuccessful sample
# ============================================================

primary_df = df[
    df[outcome_col].isin(
        [
            "Successful",
            "Unsuccessful",
        ]
    )
].copy()


print()
print("=" * 72)
print("RQ1 ANALYSIS")
print("=" * 72)

print()
print(
    "Primary Successful/Unsuccessful sample:"
)

print(
    f"  n={len(primary_df):,}"
)


# ============================================================
# 6. Analyse one numerical variable
# ============================================================

summary_rows = []
statistics_rows = []


def analyse_variable(
    variable_name: str,
    column_name: str,
):

    successful = numeric_series(
        primary_df[
            primary_df[outcome_col]
            == "Successful"
        ],
        column_name,
    )

    unsuccessful = numeric_series(
        primary_df[
            primary_df[outcome_col]
            == "Unsuccessful"
        ],
        column_name,
    )


    successful_n = len(
        successful
    )

    unsuccessful_n = len(
        unsuccessful
    )


    successful_median = (
        successful.median()
    )

    successful_iqr = iqr(
        successful
    )


    unsuccessful_median = (
        unsuccessful.median()
    )

    unsuccessful_iqr = iqr(
        unsuccessful
    )


    u_statistic, p_value = (
        mannwhitneyu(
            successful,
            unsuccessful,
            alternative="two-sided",
        )
    )


    rank_biserial = (
        rank_biserial_from_u(
            u_statistic,
            successful_n,
            unsuccessful_n,
        )
    )


    effect = effect_label(
        rank_biserial
    )


    print()
    print(variable_name)

    print(
        f"  Successful: "
        f"n={successful_n:,}, "
        f"median={successful_median:.3f}, "
        f"IQR={successful_iqr:.3f}"
    )

    print(
        f"  Unsuccessful: "
        f"n={unsuccessful_n:,}, "
        f"median={unsuccessful_median:.3f}, "
        f"IQR={unsuccessful_iqr:.3f}"
    )

    print(
        "  Mann-Whitney U:",
        f"{u_statistic:.3f}",
    )

    print(
        "  p-value:",
        format_p_value(
            p_value
        ),
    )

    print(
        "  Rank-biserial correlation:",
        f"{rank_biserial:.4f} "
        f"({effect})",
    )


    summary_rows.extend(
        [
            {
                "variable":
                    variable_name,

                "outcome":
                    "Successful",

                "n":
                    successful_n,

                "median":
                    successful_median,

                "iqr":
                    successful_iqr,
            },
            {
                "variable":
                    variable_name,

                "outcome":
                    "Unsuccessful",

                "n":
                    unsuccessful_n,

                "median":
                    unsuccessful_median,

                "iqr":
                    unsuccessful_iqr,
            },
        ]
    )


    statistics_rows.append(
        {
            "variable":
                variable_name,

            "successful_n":
                successful_n,

            "unsuccessful_n":
                unsuccessful_n,

            "mann_whitney_u":
                u_statistic,

            "p_value":
                p_value,

            "rank_biserial":
                rank_biserial,

            "effect_size_label":
                effect,
        }
    )


    # --------------------------------------------------------
    # Plot
    # --------------------------------------------------------

    plot_df = pd.DataFrame(
        {
            "Successful":
                successful.reset_index(
                    drop=True
                ),

            "Unsuccessful":
                unsuccessful.reset_index(
                    drop=True
                ),
        }
    )


    fig, ax = plt.subplots(
        figsize=(7, 5)
    )

    ax.boxplot(
        [
            successful,
            unsuccessful,
        ],
        tick_labels=[
            "Successful",
            "Unsuccessful",
        ],
        showfliers=False,
    )

    ax.set_title(
        variable_name
    )

    ax.set_ylabel(
        variable_name
    )

    fig.tight_layout()


    safe_name = (
        variable_name
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
    )

    figure_file = (
        FIGURE_DIR
        / f"{safe_name}.png"
    )

    fig.savefig(
        figure_file,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )


# ============================================================
# 7. RQ1 variables
# ============================================================

analyse_variable(
    "Revision count",
    revision_col,
)


analyse_variable(
    "Development duration (days)",
    duration_col,
)


analyse_variable(
    "Lineage length",
    lineage_length_col,
)


# ============================================================
# 8. Save results
# ============================================================

summary_df = pd.DataFrame(
    summary_rows
)

statistics_df = pd.DataFrame(
    statistics_rows
)


summary_file = (
    OUTPUT_DIR
    / "rq1_summary.csv"
)

statistics_file = (
    OUTPUT_DIR
    / "rq1_statistics.csv"
)


summary_df.to_csv(
    summary_file,
    index=False,
)

statistics_df.to_csv(
    statistics_file,
    index=False,
)


# ============================================================
# 9. Final output
# ============================================================

print()
print("=" * 72)
print("SAVED OUTPUTS")
print("=" * 72)

print(
    f"Summary: {summary_file}"
)

print(
    f"Statistics: {statistics_file}"
)

print(
    f"Figures: {FIGURE_DIR}"
)