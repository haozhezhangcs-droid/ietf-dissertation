from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2_contingency


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def find_output_file(filename: str) -> Path:
    candidates = [
        PROJECT_ROOT / "outputs" / filename,
        PROJECT_ROOT / "outputs" / "common" / filename,
        PROJECT_ROOT / "outputs" / "intermediate" / filename,
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Cannot find {filename}. Checked:\n"
        + "\n".join(str(path) for path in candidates)
    )


INPUT_FILE = find_output_file(
    "lineage_outcomes.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "rq2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FIGURE_DIR = OUTPUT_DIR / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

RQ2A_TABLE_CSV = (
    OUTPUT_DIR
    / "rq2_recorded_wg_table.csv"
)

RQ2A_STATS_CSV = (
    OUTPUT_DIR
    / "rq2_recorded_wg_statistics.csv"
)

RQ2B_TABLE_CSV = (
    OUTPUT_DIR
    / "rq2_individual_to_wg_table.csv"
)

RQ2B_STATS_CSV = (
    OUTPUT_DIR
    / "rq2_individual_to_wg_statistics.csv"
)

RQ2_EXCLUSIONS_CSV = (
    OUTPUT_DIR
    / "rq2_individual_transition_exclusions.csv"
)


# ============================================================
# 2. Load data
# ============================================================

print(
    f"Using lineage file: {INPUT_FILE}"
)

df = pd.read_csv(
    INPUT_FILE,
    dtype=str,
).fillna("")


required_columns = [
    "publication_outcome",
    "has_recorded_wg",
    "has_individual_submissions",
    "individual_to_wg",
]

missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise KeyError(
        "Missing required columns in lineage_outcomes.csv: "
        + ", ".join(missing_columns)
    )


for col in [
    "has_recorded_wg",
    "has_individual_submissions",
    "individual_to_wg",
]:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce",
    )


# Primary inferential sample:
# only lineages with a resolved terminal publication outcome.
analysis_df = df[
    df["publication_outcome"].isin(
        [
            "Successful",
            "Unsuccessful",
        ]
    )
].copy()


# ============================================================
# 3. Statistical helpers
# ============================================================

def effect_label_cramers_v(
    value: float,
) -> str:
    """
    Conventional descriptive interpretation for a 2x2 table.
    Keep the numerical V in the dissertation even if labels are used.
    """

    if pd.isna(value):
        return ""

    if value < 0.10:
        return "negligible"
    if value < 0.30:
        return "small"
    if value < 0.50:
        return "medium"
    return "large"


def analyse_2x2(
    data: pd.DataFrame,
    group_column: str,
    positive_value,
    negative_value,
    positive_label: str,
    negative_label: str,
    analysis_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    sample = data[
        data[group_column].isin(
            [
                positive_value,
                negative_value,
            ]
        )
    ].copy()

    table = pd.crosstab(
        sample[group_column],
        sample["publication_outcome"],
    )

    table = table.reindex(
        index=[
            positive_value,
            negative_value,
        ],
        columns=[
            "Successful",
            "Unsuccessful",
        ],
        fill_value=0,
    )

    table.index = [
        positive_label,
        negative_label,
    ]

    a = int(
        table.loc[
            positive_label,
            "Successful",
        ]
    )
    b = int(
        table.loc[
            positive_label,
            "Unsuccessful",
        ]
    )
    c = int(
        table.loc[
            negative_label,
            "Successful",
        ]
    )
    d = int(
        table.loc[
            negative_label,
            "Unsuccessful",
        ]
    )

    chi2, p_value, dof, _ = (
        chi2_contingency(
            table,
            correction=False,
        )
    )

    n = a + b + c + d

    cramers_v = (
        (chi2 / n) ** 0.5
        if n > 0
        else float("nan")
    )

    # Haldane-Anscombe correction only if a zero cell occurs.
    aa, bb, cc, dd = map(
        float,
        [a, b, c, d],
    )

    zero_cell_correction = 0

    if 0 in {
        aa,
        bb,
        cc,
        dd,
    }:
        aa += 0.5
        bb += 0.5
        cc += 0.5
        dd += 0.5
        zero_cell_correction = 1

    odds_ratio = (
        aa * dd
    ) / (
        bb * cc
    )

    positive_total = a + b
    negative_total = c + d

    positive_success_rate = (
        a / positive_total
        if positive_total > 0
        else float("nan")
    )

    negative_success_rate = (
        c / negative_total
        if negative_total > 0
        else float("nan")
    )

    stats = pd.DataFrame(
        [
            {
                "analysis":
                    analysis_name,

                "n":
                    n,

                "positive_group":
                    positive_label,

                "negative_group":
                    negative_label,

                "positive_successful":
                    a,

                "positive_unsuccessful":
                    b,

                "positive_success_rate":
                    positive_success_rate,

                "negative_successful":
                    c,

                "negative_unsuccessful":
                    d,

                "negative_success_rate":
                    negative_success_rate,

                "success_rate_difference":
                    (
                        positive_success_rate
                        - negative_success_rate
                    ),

                "chi_square":
                    float(chi2),

                "degrees_of_freedom":
                    int(dof),

                "p_value":
                    float(p_value),

                "cramers_v":
                    float(cramers_v),

                "effect_size_magnitude":
                    effect_label_cramers_v(
                        cramers_v
                    ),

                "odds_ratio_positive_vs_negative":
                    float(odds_ratio),

                "zero_cell_correction_used":
                    zero_cell_correction,
            }
        ]
    )

    return (
        table,
        stats,
    )


# ============================================================
# 4. RQ2a
#
# Recorded WG association:
#
#   has_recorded_wg = 1
#       versus
#   has_recorded_wg = 0
#
# IMPORTANT:
# "No recorded WG" means no WG association recorded in the
# Datatracker data used here. It does NOT prove the draft was
# never discussed by or related to a WG.
# ============================================================

rq2a_table, rq2a_stats = analyse_2x2(
    data=analysis_df,
    group_column="has_recorded_wg",
    positive_value=1,
    negative_value=0,
    positive_label="Recorded WG",
    negative_label="No recorded WG",
    analysis_name="RQ2a: Recorded WG association",
)

rq2a_table.to_csv(
    RQ2A_TABLE_CSV
)

rq2a_stats.to_csv(
    RQ2A_STATS_CSV,
    index=False,
)


# ============================================================
# 5. RQ2b
#
# Development trajectory among lineages containing an
# Individual Submission.
#
# Positive group:
#   has_individual_submissions = 1
#   AND individual_to_wg = 1
#
# Comparison group:
#   has_individual_submissions = 1
#   AND has_recorded_wg = 0
#
# Excluded:
#   Individual-containing lineages that have a recorded WG but
#   are NOT classified as Individual -> Recorded WG.
#
# Why exclude them?
# Their chronology does not establish the trajectory being tested,
# so merging them into either comparison group would blur RQ2b.
# ============================================================

individual_df = analysis_df[
    analysis_df[
        "has_individual_submissions"
    ]
    == 1
].copy()


def classify_individual_trajectory(
    row: pd.Series,
) -> str:

    if (
        row["individual_to_wg"]
        == 1
    ):
        return "Individual -> Recorded WG"

    if (
        row["has_recorded_wg"]
        == 0
    ):
        return "Individual, no recorded WG"

    return "Excluded ambiguous chronology"


individual_df[
    "rq2b_group"
] = individual_df.apply(
    classify_individual_trajectory,
    axis=1,
)


rq2b_exclusions = individual_df[
    individual_df["rq2b_group"]
    == "Excluded ambiguous chronology"
].copy()

rq2b_exclusions.to_csv(
    RQ2_EXCLUSIONS_CSV,
    index=False,
)


rq2b_sample = individual_df[
    individual_df["rq2b_group"].isin(
        [
            "Individual -> Recorded WG",
            "Individual, no recorded WG",
        ]
    )
].copy()


rq2b_table, rq2b_stats = analyse_2x2(
    data=rq2b_sample,
    group_column="rq2b_group",
    positive_value="Individual -> Recorded WG",
    negative_value="Individual, no recorded WG",
    positive_label="Individual -> Recorded WG",
    negative_label="Individual, no recorded WG",
    analysis_name=(
        "RQ2b: Individual -> Recorded WG trajectory"
    ),
)

rq2b_table.to_csv(
    RQ2B_TABLE_CSV
)

rq2b_stats.to_csv(
    RQ2B_STATS_CSV,
    index=False,
)


# ============================================================
# 6. Figures
# ============================================================

rq2a_row = rq2a_stats.iloc[0]

fig, ax = plt.subplots(
    figsize=(8, 5)
)

ax.bar(
    [
        "No recorded WG",
        "Recorded WG",
    ],
    [
        rq2a_row[
            "negative_success_rate"
        ],
        rq2a_row[
            "positive_success_rate"
        ],
    ],
)

ax.set_title(
    "RFC publication success rate by recorded WG association"
)

ax.set_ylabel(
    "RFC publication success rate"
)

ax.set_xlabel(
    "Datatracker WG association"
)

ax.set_ylim(
    0,
    1,
)

fig.tight_layout()

fig.savefig(
    FIGURE_DIR
    / "rq2_recorded_wg_success_rate.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)


rq2b_row = rq2b_stats.iloc[0]

fig, ax = plt.subplots(
    figsize=(8, 5)
)

ax.bar(
    [
        "Individual,\nno recorded WG",
        "Individual ->\nRecorded WG",
    ],
    [
        rq2b_row[
            "negative_success_rate"
        ],
        rq2b_row[
            "positive_success_rate"
        ],
    ],
)

ax.set_title(
    "RFC publication success rate for Individual Submission trajectories"
)

ax.set_ylabel(
    "RFC publication success rate"
)

ax.set_xlabel(
    "Development trajectory"
)

ax.set_ylim(
    0,
    1,
)

fig.tight_layout()

fig.savefig(
    FIGURE_DIR
    / "rq2_individual_to_wg_success_rate.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)


# ============================================================
# 7. Console summary
# ============================================================

print()
print("=" * 72)
print("RQ2 ANALYSIS")
print("=" * 72)

print()
print("Primary Successful/Unsuccessful sample:")
print(
    f"  n={len(analysis_df):,}"
)


print()
print(
    "RQ2a — Recorded WG association"
)

print(
    "  Recorded WG:",
    f"{int(rq2a_row['positive_successful']):,} successful,",
    f"{int(rq2a_row['positive_unsuccessful']):,} unsuccessful,",
    f"success rate={rq2a_row['positive_success_rate']:.3%}",
)

print(
    "  No recorded WG:",
    f"{int(rq2a_row['negative_successful']):,} successful,",
    f"{int(rq2a_row['negative_unsuccessful']):,} unsuccessful,",
    f"success rate={rq2a_row['negative_success_rate']:.3%}",
)

print(
    f"  Chi-square: "
    f"{rq2a_row['chi_square']:.3f}"
)

print(
    "  p-value:",
    (
        "< 0.001"
        if rq2a_row[
            "p_value"
        ] < 0.001
        else
        f"{rq2a_row['p_value']:.6f}"
    ),
)

print(
    f"  Cramer's V: "
    f"{rq2a_row['cramers_v']:.4f} "
    f"({rq2a_row['effect_size_magnitude']})"
)

print(
    f"  Odds ratio: "
    f"{rq2a_row['odds_ratio_positive_vs_negative']:.4f}"
)


print()
print(
    "RQ2b — Individual -> Recorded WG trajectory"
)

print(
    "  Individual -> Recorded WG:",
    f"{int(rq2b_row['positive_successful']):,} successful,",
    f"{int(rq2b_row['positive_unsuccessful']):,} unsuccessful,",
    f"success rate={rq2b_row['positive_success_rate']:.3%}",
)

print(
    "  Individual, no recorded WG:",
    f"{int(rq2b_row['negative_successful']):,} successful,",
    f"{int(rq2b_row['negative_unsuccessful']):,} unsuccessful,",
    f"success rate={rq2b_row['negative_success_rate']:.3%}",
)

print(
    f"  Chi-square: "
    f"{rq2b_row['chi_square']:.3f}"
)

print(
    "  p-value:",
    (
        "< 0.001"
        if rq2b_row[
            "p_value"
        ] < 0.001
        else
        f"{rq2b_row['p_value']:.6f}"
    ),
)

print(
    f"  Cramer's V: "
    f"{rq2b_row['cramers_v']:.4f} "
    f"({rq2b_row['effect_size_magnitude']})"
)

print(
    f"  Odds ratio: "
    f"{rq2b_row['odds_ratio_positive_vs_negative']:.4f}"
)

print()
print(
    "RQ2b excluded ambiguous chronology lineages:",
    f"{len(rq2b_exclusions):,}",
)

print()
print(
    "Interpretation note:"
)
print(
    '  "No recorded WG" means no WG association recorded in '
    "Datatracker; it does not prove absence of actual WG involvement."
)

print()
print(f"Saved: {RQ2A_TABLE_CSV}")
print(f"Saved: {RQ2A_STATS_CSV}")
print(f"Saved: {RQ2B_TABLE_CSV}")
print(f"Saved: {RQ2B_STATS_CSV}")
print(f"Excluded audit: {RQ2_EXCLUSIONS_CSV}")
print(f"Figures: {FIGURE_DIR}")