from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_RECORDS_CSV = (
    PROJECT_ROOT
    / "output"
    / "data"
    / "figure01_rfc_records_historical_area.csv"
)

OUTPUT_DATA_DIR = (
    PROJECT_ROOT
    / "output"
    / "data"
)

OUTPUT_FIGURE_DIR = (
    PROJECT_ROOT
    / "output"
    / "figures"
)

OUTPUT_RECORDS_CSV = (
    OUTPUT_DATA_DIR
    / "figure02_publishing_group_records.csv"
)

OUTPUT_COUNTS_CSV = (
    OUTPUT_DATA_DIR
    / "figure02_publishing_groups_by_area.csv"
)

OUTPUT_FIGURE_PNG = (
    OUTPUT_FIGURE_DIR
    / "figure02_publishing_groups_by_area_2001_2025.png"
)


# =============================================================================
# Analysis settings
# =============================================================================

START_YEAR = 2001
END_YEAR = 2025

MAIN_AREAS = {
    "app",
    "rai",
    "art",
    "int",
    "ops",
    "rtg",
    "sec",
    "tsv",
    "wit",
}

AREA_ORDER = [
    "Other",
    "rtg",
    "int",
    "app",
    "ops",
    "sec",
    "tsv",
    "rai",
    "art",
    "wit",
]
AREA_COLORS = {
    "Other": "#1f77b4",   # blue
    "rtg":   "#ff7f0e",   # orange
    "int":   "#2ca02c",   # green
    "app":   "#d62728",   # red
    "ops":   "#9467bd",   # purple
    "sec":   "#8c564b",   # brown
    "tsv":   "#e377c2",   # pink
    "rai":   "#7f7f7f",   # grey
    "art":   "#bcbd22",   # yellow
    "wit":   "#17becf",   # cyan
}

# =============================================================================
# Helper functions
# =============================================================================

def extract_slug(value: object) -> str | None:
    """
    Extract the final component from a Datatracker URI.

    Example:
        /api/v1/name/grouptypename/wg/
        becomes:
        wg
    """

    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    parts = [
        part
        for part in text.split("/")
        if part
    ]

    if not parts:
        return None

    return parts[-1].lower()


def normalise_text(value: object) -> str | None:
    """Return a cleaned lowercase string or None."""

    if value is None or pd.isna(value):
        return None

    text = str(value).strip().lower()

    return text if text else None


# =============================================================================
# Loading and validation
# =============================================================================

def load_figure01_records() -> pd.DataFrame:
    """
    Load the historical-Area RFC records created for Figure 1.
    """

    print(
        "Input:",
        INPUT_RECORDS_CSV.resolve(),
    )

    print(
        "Exists:",
        INPUT_RECORDS_CSV.exists(),
    )

    if not INPUT_RECORDS_CSV.is_file():
        raise FileNotFoundError(
            "Figure 1 historical record file was not found:\n"
            f"{INPUT_RECORDS_CSV.resolve()}\n\n"
            "Run 06_figure01_rfcs_by_area.py first."
        )

    dataframe = pd.read_csv(
        INPUT_RECORDS_CSV,
        low_memory=False,
    )

    required_columns = {
        "resource_uri",
        "rfc_number",
        "publication_time",
        "publication_year",
        "stream",
        "group_uri",
        "resolved_group_acronym",
        "resolved_group_name",
        "resolved_group_type",
        "resolved_parent_uri",
        "resolved_area_acronym",
        "area_category",
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "The Figure 1 CSV is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    return dataframe


# =============================================================================
# Publishing-unit classification
# =============================================================================

def determine_publishing_unit(row: pd.Series) -> str | None:
    stream_slug = row["stream_slug"]
    group_uri = normalise_text(row["group_uri"])
    group_type_slug = row["resolved_group_type_slug"]

    # IETF Working Groups: count each WG once per year.
    if (
        stream_slug == "ietf"
        and group_type_slug == "wg"
        and group_uri
    ):
        return f"wg:{group_uri}"

    # IRTF Research Groups: count each RG once per year,
    # but classify them under Other.
    if (
        stream_slug == "irtf"
        and group_type_slug == "rg"
        and group_uri
    ):
        return f"rg:{group_uri}"

    # Other RFC streams: count each stream once per year.
    if stream_slug in {
        "legacy",
        "iab",
        "ise",
        "editorial",
    }:
        return f"stream:{stream_slug}"

    # IETF-stream RFCs not associated with a WG are one
    # general IETF activity per year, not one per group.
    if stream_slug == "ietf":
        return "stream:ietf-other"

    # Remaining streams use one stream-level unit.
    if stream_slug:
        return f"stream:{stream_slug}"

    return None


def determine_figure_area(row: pd.Series) -> str:
    stream_slug = row["stream_slug"]
    group_type_slug = row["resolved_group_type_slug"]
    area_category = normalise_text(row["area_category"])

    if (
        stream_slug == "ietf"
        and group_type_slug == "wg"
        and area_category in MAIN_AREAS
    ):
        return area_category

    return "Other"


def prepare_publishing_units(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare one RFC-level table containing its publishing unit.
    """

    dataframe = dataframe.copy()

    dataframe["publication_time"] = pd.to_datetime(
        dataframe["publication_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["publication_year"] = pd.to_numeric(
        dataframe["publication_year"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "publication_time",
            "publication_year",
        ]
    ).copy()

    dataframe["publication_year"] = (
        dataframe["publication_year"]
        .astype(int)
    )

    dataframe["stream_slug"] = (
        dataframe["stream"]
        .apply(extract_slug)
    )

    dataframe["resolved_group_type_slug"] = (
        dataframe["resolved_group_type"]
        .apply(extract_slug)
    )

    dataframe["publishing_unit_id"] = (
        dataframe.apply(
            determine_publishing_unit,
            axis=1,
        )
    )

    dataframe = dataframe.dropna(
    subset=["publishing_unit_id"]
    ).copy()

    dataframe["figure_area"] = (
        dataframe.apply(
            determine_figure_area,
            axis=1,
        )
    )

    return dataframe


# =============================================================================
# Deduplication and aggregation
# =============================================================================

def create_unique_publishing_units(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reduce RFC-level data to one row per year and publishing unit.

    If a unit somehow appears with multiple Area labels in the same year,
    the label associated with the largest number of RFCs is selected.
    """

    analysis_data = dataframe[
        dataframe["publication_year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    unit_area_counts = (
        analysis_data
        .groupby(
            [
                "publication_year",
                "publishing_unit_id",
                "figure_area",
            ],
            dropna=False,
        )
        .agg(
            rfc_count=("rfc_number", "nunique"),
            group_acronym=(
                "resolved_group_acronym",
                "first",
            ),
            group_name=(
                "resolved_group_name",
                "first",
            ),
            stream_slug=(
                "stream_slug",
                "first",
            ),
            group_type_slug=(
                "resolved_group_type_slug",
                "first",
            ),
        )
        .reset_index()
    )

    # Select the dominant Area assignment for each unit/year.
    unit_area_counts = unit_area_counts.sort_values(
        [
            "publication_year",
            "publishing_unit_id",
            "rfc_count",
            "figure_area",
        ],
        ascending=[
            True,
            True,
            False,
            True,
        ],
    )

    unique_units = (
        unit_area_counts
        .drop_duplicates(
            subset=[
                "publication_year",
                "publishing_unit_id",
            ],
            keep="first",
        )
        .sort_values(
            [
                "publication_year",
                "figure_area",
                "publishing_unit_id",
            ]
        )
        .reset_index(drop=True)
    )

    return unique_units


def create_counts(
    unique_units: pd.DataFrame,
) -> pd.DataFrame:
    """
    Count distinct RFC-publishing groups or streams by year and Area.
    """

    counts = (
        unique_units
        .groupby(
            [
                "publication_year",
                "figure_area",
            ]
        )
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )

    counts = counts.reindex(
        range(
            START_YEAR,
            END_YEAR + 1,
        ),
        fill_value=0,
    )

    ordered_columns = [
        area
        for area in AREA_ORDER
        if area in counts.columns
    ]

    remaining_columns = sorted(
        area
        for area in counts.columns
        if area not in ordered_columns
    )

    counts = counts[
        ordered_columns
        + remaining_columns
    ]

    counts.index.name = "publication_year"

    return counts


# =============================================================================
# Plotting
# =============================================================================

def create_figure(
    counts: pd.DataFrame,
) -> None:
    """
    Create Figure 2 as a stacked area chart.
    """

    figure, axis = plt.subplots(
        figsize=(14, 7),
    )

    plot_colors = [
    AREA_COLORS[area]
    for area in counts.columns
]

    counts.plot.area(
        ax=axis,
        linewidth=0.25,
        color=plot_colors,
    )

    axis.set_title(
        "RFC-Publishing Working Groups or Streams, 2001–2025"
    )

    axis.set_xlabel(
        "Publication year"
    )

    axis.set_ylabel(
        "RFC-publishing WGs or streams"
    )

    axis.set_xlim(
        START_YEAR,
        END_YEAR,
    )

    axis.set_xticks(
        list(
            range(
                START_YEAR,
                END_YEAR + 1,
                2,
            )
        )
        + [END_YEAR]
    )

    axis.legend(
        title="Area",
        loc="upper left",
        ncol=2,
        frameon=True,
    )

    axis.grid(
        axis="y",
        linestyle=":",
        alpha=0.4,
    )

    figure.text(
        0.5,
        0.01,
        (
            "Each Working Group or other publication activity is "
            "counted once per year, regardless of the number of RFCs "
            "it published. Other includes IRTF research groups, legacy "
            "RFCs and non-IETF streams."
        ),
        ha="center",
        fontsize=9,
    )

    figure.tight_layout(
        rect=[0, 0.05, 1, 1]
    )

    figure.savefig(
        OUTPUT_FIGURE_PNG,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)


# =============================================================================
# Validation
# =============================================================================

def print_summary(
    rfc_records: pd.DataFrame,
    unique_units: pd.DataFrame,
    counts: pd.DataFrame,
) -> None:
    """
    Print checks needed to validate Figure 2.
    """

    print("\n" + "=" * 80)
    print("FIGURE 2 — PUBLISHING GROUP SUMMARY")
    print("=" * 80)

    print(
        f"\nRFC-level records loaded: "
        f"{len(rfc_records):,}"
    )

    print(
        f"Unique year–publishing-unit records: "
        f"{len(unique_units):,}"
    )

    print("\nPublishing units by category:")
    print(
        unique_units["figure_area"]
        .value_counts(dropna=False)
        .to_string()
    )

    yearly_totals = counts.sum(
        axis=1
    )

    print("\nPublishing groups or streams by year:")
    print(
        yearly_totals.to_string()
    )

    peak_year = int(
        yearly_totals.idxmax()
    )

    peak_value = int(
        yearly_totals.max()
    )

    print(
        f"\nPeak year: {peak_year}"
    )

    print(
        f"Peak publishing groups/streams: "
        f"{peak_value}"
    )

    print("\nRecent years:")
    print(
        yearly_totals.loc[
            yearly_totals.index >= 2018
        ].to_string()
    )

    print("\n2021 sample — QUIC:")
    quic_sample = unique_units[
        (
            unique_units[
                "publication_year"
            ] == 2021
        )
        & (
            unique_units[
                "group_acronym"
            ]
            .astype("string")
            .str.lower()
            .eq("quic")
        )
    ]

    if quic_sample.empty:
        print(
            "No QUIC publishing-unit record found for 2021."
        )
    else:
        print(
            quic_sample[
                [
                    "publication_year",
                    "publishing_unit_id",
                    "group_acronym",
                    "group_name",
                    "stream_slug",
                    "group_type_slug",
                    "figure_area",
                    "rfc_count",
                ]
            ].to_string(
                index=False
            )
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    OUTPUT_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FIGURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe = load_figure01_records()

    print(
        "Preparing publishing-unit classifications...",
        flush=True,
    )

    dataframe = prepare_publishing_units(
        dataframe
    )

    unique_units = create_unique_publishing_units(
        dataframe
    )

    counts = create_counts(
        unique_units
    )

    unique_units.to_csv(
        OUTPUT_RECORDS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    counts.to_csv(
        OUTPUT_COUNTS_CSV,
        encoding="utf-8-sig",
    )

    create_figure(
        counts
    )

    print_summary(
        rfc_records=dataframe,
        unique_units=unique_units,
        counts=counts,
    )

    print("\n" + "=" * 80)
    print("CREATED FILES")
    print("=" * 80)

    print(
        OUTPUT_RECORDS_CSV
    )

    print(
        OUTPUT_COUNTS_CSV
    )

    print(
        OUTPUT_FIGURE_PNG
    )


if __name__ == "__main__":
    main()