from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "outputs" / "rq3_collaboration_dataset.csv"

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "rq3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FIGURE_DIR = OUTPUT_DIR / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

AUTHOR_SUMMARY_CSV = OUTPUT_DIR / "rq3_author_count_summary.csv"
AUTHOR_STATS_CSV = OUTPUT_DIR / "rq3_author_count_statistics.csv"
CROSSORG_TABLE_CSV = OUTPUT_DIR / "rq3_cross_organisation_table.csv"
CROSSORG_STATS_CSV = OUTPUT_DIR / "rq3_cross_organisation_statistics.csv"
SENSITIVITY_CSV = OUTPUT_DIR / "rq3_sensitivity_analysis.csv"


df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")

for col in [
    "lineage_author_count",
    "cross_organisation",
    "complete_affiliation_coverage",
    "has_affiliation_conflict",
]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

analysis_df = df[
    df["publication_outcome"].isin(["Successful", "Unsuccessful"])
].copy()


def rank_biserial(u: float, n1: int, n2: int) -> float:
    if n1 == 0 or n2 == 0:
        return float("nan")
    return 2.0 * u / (n1 * n2) - 1.0


def effect_label(value: float) -> str:
    x = abs(value)
    if x < 0.10:
        return "negligible"
    if x < 0.30:
        return "small"
    if x < 0.50:
        return "medium"
    return "large"


def cross_org_stats(data: pd.DataFrame, sample_name: str) -> dict:
    sample = data[
        data["publication_outcome"].isin(["Successful", "Unsuccessful"])
        & data["cross_organisation"].isin([0, 1])
    ].copy()

    table = pd.crosstab(
        sample["cross_organisation"],
        sample["publication_outcome"],
    )

    table = table.reindex(
        index=[1, 0],
        columns=["Successful", "Unsuccessful"],
        fill_value=0,
    )

    a = int(table.loc[1, "Successful"])
    b = int(table.loc[1, "Unsuccessful"])
    c = int(table.loc[0, "Successful"])
    d = int(table.loc[0, "Unsuccessful"])

    chi2, p, dof, _ = chi2_contingency(table, correction=False)

    n = a + b + c + d
    cramers_v = (chi2 / n) ** 0.5 if n else float("nan")

    aa, bb, cc, dd = map(float, [a, b, c, d])
    if 0 in {aa, bb, cc, dd}:
        aa += 0.5
        bb += 0.5
        cc += 0.5
        dd += 0.5

    odds_ratio = (aa * dd) / (bb * cc)

    cross_rate = a / (a + b) if (a + b) else float("nan")
    not_cross_rate = c / (c + d) if (c + d) else float("nan")

    return {
        "sample": sample_name,
        "n": len(sample),
        "cross_successful": a,
        "cross_unsuccessful": b,
        "cross_success_rate": cross_rate,
        "not_cross_successful": c,
        "not_cross_unsuccessful": d,
        "not_cross_success_rate": not_cross_rate,
        "success_rate_difference": cross_rate - not_cross_rate,
        "chi_square": float(chi2),
        "degrees_of_freedom": int(dof),
        "p_value": float(p),
        "cramers_v": float(cramers_v),
        "odds_ratio_cross_vs_not": float(odds_ratio),
    }


# ============================================================
# RQ3a: author participation
# ============================================================

author_summary_rows = []

for outcome in ["Successful", "Unsuccessful"]:
    values = analysis_df.loc[
        analysis_df["publication_outcome"] == outcome,
        "lineage_author_count",
    ].dropna()

    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))

    author_summary_rows.append(
        {
            "outcome": outcome,
            "n": len(values),
            "mean": float(values.mean()),
            "median": float(values.median()),
            "q1": q1,
            "q3": q3,
            "iqr": q3 - q1,
            "min": float(values.min()),
            "max": float(values.max()),
        }
    )

author_summary_df = pd.DataFrame(author_summary_rows)
author_summary_df.to_csv(AUTHOR_SUMMARY_CSV, index=False)

successful_authors = analysis_df.loc[
    analysis_df["publication_outcome"] == "Successful",
    "lineage_author_count",
].dropna()

unsuccessful_authors = analysis_df.loc[
    analysis_df["publication_outcome"] == "Unsuccessful",
    "lineage_author_count",
].dropna()

test = mannwhitneyu(
    successful_authors,
    unsuccessful_authors,
    alternative="two-sided",
    method="asymptotic",
)

u = float(test.statistic)
p = float(test.pvalue)
r_rb = rank_biserial(
    u,
    len(successful_authors),
    len(unsuccessful_authors),
)

author_stats_df = pd.DataFrame(
    [
        {
            "successful_n": len(successful_authors),
            "unsuccessful_n": len(unsuccessful_authors),
            "successful_median": float(successful_authors.median()),
            "unsuccessful_median": float(unsuccessful_authors.median()),
            "mann_whitney_u_successful": u,
            "p_value": p,
            "rank_biserial_correlation": r_rb,
            "effect_size_magnitude": effect_label(r_rb),
            "direction": (
                "Successful higher"
                if r_rb > 0
                else "Successful lower"
                if r_rb < 0
                else "No directional difference"
            ),
        }
    ]
)

author_stats_df.to_csv(AUTHOR_STATS_CSV, index=False)


# ============================================================
# RQ3b: cross-organisational collaboration
# ============================================================

primary = cross_org_stats(analysis_df, "Primary")

cross_table = pd.DataFrame(
    {
        "Successful": [
            primary["cross_successful"],
            primary["not_cross_successful"],
        ],
        "Unsuccessful": [
            primary["cross_unsuccessful"],
            primary["not_cross_unsuccessful"],
        ],
    },
    index=[
        "Cross-organisation",
        "Not cross-organisation",
    ],
)

cross_table.to_csv(CROSSORG_TABLE_CSV)

pd.DataFrame([primary]).to_csv(
    CROSSORG_STATS_CSV,
    index=False,
)


# ============================================================
# Sensitivity analyses
# ============================================================

sensitivity_rows = [primary]

sensitivity_rows.append(
    cross_org_stats(
        analysis_df[
            analysis_df["complete_affiliation_coverage"] == 1
        ],
        "Complete affiliation coverage",
    )
)

sensitivity_rows.append(
    cross_org_stats(
        analysis_df[
            analysis_df["has_affiliation_conflict"] == 0
        ],
        "No affiliation conflict",
    )
)

sensitivity_rows.append(
    cross_org_stats(
        analysis_df[
            (analysis_df["complete_affiliation_coverage"] == 1)
            & (analysis_df["has_affiliation_conflict"] == 0)
        ],
        "Complete coverage + no conflict",
    )
)

sensitivity_df = pd.DataFrame(sensitivity_rows)
sensitivity_df.to_csv(SENSITIVITY_CSV, index=False)


# ============================================================
# Figures
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5))

ax.boxplot(
    [
        unsuccessful_authors,
        successful_authors,
    ],
    tick_labels=[
        "Unsuccessful",
        "Successful",
    ],
    showfliers=False,
)

ax.set_title(
    "Lineage author count: Successful vs Unsuccessful"
)
ax.set_ylabel("Unique resolved authors per lineage")
ax.set_xlabel("Publication outcome")

fig.tight_layout()

fig.savefig(
    FIGURE_DIR / "rq3_author_count.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)


fig, ax = plt.subplots(figsize=(8, 5))

ax.bar(
    [
        "Not cross-organisation",
        "Cross-organisation",
    ],
    [
        primary["not_cross_success_rate"],
        primary["cross_success_rate"],
    ],
)

ax.set_title(
    "RFC publication success rate by cross-organisational co-authorship"
)
ax.set_ylabel("RFC publication success rate")
ax.set_xlabel("Collaboration category")
ax.set_ylim(0, 1)

fig.tight_layout()

fig.savefig(
    FIGURE_DIR / "rq3_cross_organisation_success_rate.png",
    dpi=300,
    bbox_inches="tight",
)

plt.close(fig)


# ============================================================
# Console summary
# ============================================================

print()
print("=" * 72)
print("RQ3 ANALYSIS")
print("=" * 72)

print()
print("RQ3a — Author participation")

for _, row in author_summary_df.iterrows():
    print(
        f"  {row['outcome']}: "
        f"n={int(row['n']):,}, "
        f"median={row['median']:.3f}, "
        f"IQR={row['iqr']:.3f}"
    )

print(f"  Mann-Whitney U: {u:.3f}")
print("  p-value:", "< 0.001" if p < 0.001 else f"{p:.6f}")
print(
    f"  Rank-biserial correlation: "
    f"{r_rb:.4f} ({effect_label(r_rb)})"
)

print()
print("RQ3b — Cross-organisational collaboration")

print(
    f"  Cross-organisation: "
    f"{primary['cross_successful']:,} successful, "
    f"{primary['cross_unsuccessful']:,} unsuccessful, "
    f"success rate={primary['cross_success_rate']:.3%}"
)

print(
    f"  Not cross-organisation: "
    f"{primary['not_cross_successful']:,} successful, "
    f"{primary['not_cross_unsuccessful']:,} unsuccessful, "
    f"success rate={primary['not_cross_success_rate']:.3%}"
)

print(f"  Chi-square: {primary['chi_square']:.3f}")
print(
    "  p-value:",
    "< 0.001"
    if primary["p_value"] < 0.001
    else f"{primary['p_value']:.6f}",
)
print(f"  Cramer's V: {primary['cramers_v']:.4f}")
print(
    f"  Odds ratio: "
    f"{primary['odds_ratio_cross_vs_not']:.4f}"
)

print()
print("Sensitivity analyses")

for _, row in sensitivity_df.iterrows():
    print(
        f"  {row['sample']}: "
        f"n={int(row['n']):,}, "
        f"cross success={row['cross_success_rate']:.3%}, "
        f"not-cross success={row['not_cross_success_rate']:.3%}, "
        f"OR={row['odds_ratio_cross_vs_not']:.3f}, "
        f"V={row['cramers_v']:.3f}"
    )

print()
print(f"Saved: {AUTHOR_SUMMARY_CSV}")
print(f"Saved: {AUTHOR_STATS_CSV}")
print(f"Saved: {CROSSORG_TABLE_CSV}")
print(f"Saved: {CROSSORG_STATS_CSV}")
print(f"Saved: {SENSITIVITY_CSV}")
print(f"Figures: {FIGURE_DIR}")