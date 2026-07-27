from __future__ import annotations

from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd


# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
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
    / "figure01_rfc_records_historical_area.csv"
)

OUTPUT_COUNTS_CSV = (
    OUTPUT_DATA_DIR
    / "figure01_rfc_counts_historical_area.csv"
)

OUTPUT_FIGURE_PNG = (
    OUTPUT_FIGURE_DIR
    / "figure01_rfcs_by_historical_area_2001_2025.png"
)


# =============================================================================
# Analysis settings
# =============================================================================

START_YEAR = 2001
END_YEAR = 2025

RFC_DOCUMENT_TYPE = "/api/v1/name/doctypename/rfc/"
IETF_STREAM = "/api/v1/name/streamname/ietf/"

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
    "Other": "#1f77b4",  # blue
    "rtg": "#ff7f0e",    # orange
    "int": "#2ca02c",    # green
    "app": "#d62728",    # red
    "ops": "#9467bd",    # purple
    "sec": "#8c564b",    # brown
    "tsv": "#e377c2",    # pink
    "rai": "#7f7f7f",    # grey
    "art": "#bcbd22",    # yellow/olive
    "wit": "#17becf",    # cyan
}
# =============================================================================
# Helper functions
# =============================================================================

def extract_slug(uri: object) -> str | None:
    """
    Extract the final component of a Datatracker API URI.

    Example:
        /api/v1/name/streamname/ietf/
        becomes:
        ietf
    """

    if uri is None:
        return None

    if pd.isna(uri):
        return None

    text = str(uri).strip()

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


def check_database_tables(
    connection: sqlite3.Connection,
) -> None:
    """Check that the required database tables exist."""

    required_tables = {
        "ietf_dt_doc_document",
        "ietf_dt_doc_docevent",
        "ietf_dt_group_group",
        "ietf_dt_group_grouphistory",
    }

    table_rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    existing_tables = {
        row[0]
        for row in table_rows
    }

    missing_tables = (
        required_tables
        - existing_tables
    )

    if missing_tables:
        raise RuntimeError(
            "The database is missing required tables: "
            f"{sorted(missing_tables)}"
        )


# =============================================================================
# Data extraction
# =============================================================================

def load_historical_rfc_data(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    """
    Load RFC publication information and restore the Working Group and
    parent Area information that existed at publication time.

    The query performs the following steps:

    1. Find the first published_rfc event for every RFC.
    2. Obtain the RFC's Working Group.
    3. Select the latest Working Group history record on or before the
       RFC publication date.
    4. Resolve the Working Group's historical parent Area.
    5. Select the latest parent Area history record on or before the
       RFC publication date.
    6. Use current group data only when historical data is unavailable.
    """

    query = """
    WITH publication_events AS (
        SELECT
            doc,
            MIN(time) AS publication_time
        FROM ietf_dt_doc_docevent
        WHERE type = 'published_rfc'
        GROUP BY doc
    ),

    rfc_base AS (
        SELECT
            d.resource_uri,
            d.rfc_number,
            d.name AS rfc_name,
            d.title,
            d.pages,
            d.words,
            d.stream,
            d."group" AS group_uri,
            publication_events.publication_time,

            current_wg.acronym AS current_group_acronym,
            current_wg.name AS current_group_name,
            current_wg.parent AS current_parent_uri,
            current_wg.type AS current_group_type

        FROM ietf_dt_doc_document AS d

        INNER JOIN publication_events
            ON publication_events.doc = d.resource_uri

        LEFT JOIN ietf_dt_group_group AS current_wg
            ON current_wg.resource_uri = d."group"

        WHERE
            d.type = ?
            AND d.rfc_number IS NOT NULL
    ),

    wg_history_candidates AS (
        SELECT
            rfc_base.*,

            wg_history.time AS wg_history_time,
            wg_history.acronym AS historical_group_acronym,
            wg_history.name AS historical_group_name,
            wg_history.parent AS historical_parent_uri,
            wg_history.type AS historical_group_type,

            ROW_NUMBER() OVER (
                PARTITION BY rfc_base.resource_uri
                ORDER BY wg_history.time DESC
            ) AS wg_history_rank

        FROM rfc_base

        LEFT JOIN ietf_dt_group_grouphistory AS wg_history
            ON wg_history."group" = rfc_base.group_uri
            AND wg_history.time <= rfc_base.publication_time
    ),

    wg_resolved AS (
        SELECT
            resource_uri,
            rfc_number,
            rfc_name,
            title,
            pages,
            words,
            stream,
            group_uri,
            publication_time,

            current_group_acronym,
            current_group_name,
            current_parent_uri,
            current_group_type,

            wg_history_time,
            historical_group_acronym,
            historical_group_name,
            historical_parent_uri,
            historical_group_type,

            COALESCE(
                historical_group_acronym,
                current_group_acronym
            ) AS resolved_group_acronym,

            COALESCE(
                historical_group_name,
                current_group_name
            ) AS resolved_group_name,

            COALESCE(
                historical_parent_uri,
                current_parent_uri
            ) AS resolved_parent_uri,

            COALESCE(
                historical_group_type,
                current_group_type
            ) AS resolved_group_type,

            CASE
                WHEN wg_history_time IS NOT NULL
                    THEN 'historical'
                ELSE 'current_fallback'
            END AS working_group_mapping_source

        FROM wg_history_candidates

        WHERE wg_history_rank = 1
    ),

    area_history_candidates AS (
        SELECT
            wg_resolved.*,

            area_history.time AS area_history_time,
            area_history.acronym AS historical_area_acronym,
            area_history.name AS historical_area_name,
            area_history.type AS historical_area_type,

            current_area.acronym AS current_area_acronym,
            current_area.name AS current_area_name,
            current_area.type AS current_area_type,

            ROW_NUMBER() OVER (
                PARTITION BY wg_resolved.resource_uri
                ORDER BY area_history.time DESC
            ) AS area_history_rank

        FROM wg_resolved

        LEFT JOIN ietf_dt_group_grouphistory AS area_history
            ON area_history."group" =
               wg_resolved.resolved_parent_uri
            AND area_history.time <=
                wg_resolved.publication_time

        LEFT JOIN ietf_dt_group_group AS current_area
            ON current_area.resource_uri =
               wg_resolved.resolved_parent_uri
    )

    SELECT
        resource_uri,
        rfc_number,
        rfc_name,
        title,
        pages,
        words,
        stream,
        group_uri,
        publication_time,

        current_group_acronym,
        current_group_name,
        current_parent_uri,
        current_group_type,

        wg_history_time,
        historical_group_acronym,
        historical_group_name,
        historical_parent_uri,
        historical_group_type,

        resolved_group_acronym,
        resolved_group_name,
        resolved_parent_uri,
        resolved_group_type,
        working_group_mapping_source,

        area_history_time,
        historical_area_acronym,
        historical_area_name,
        historical_area_type,

        current_area_acronym,
        current_area_name,
        current_area_type,

        COALESCE(
            historical_area_acronym,
            current_area_acronym
        ) AS resolved_area_acronym,

        COALESCE(
            historical_area_name,
            current_area_name
        ) AS resolved_area_name,

        COALESCE(
            historical_area_type,
            current_area_type
        ) AS resolved_area_type,

        CASE
            WHEN area_history_time IS NOT NULL
                THEN 'historical'
            ELSE 'current_fallback'
        END AS area_mapping_source

    FROM area_history_candidates

    WHERE area_history_rank = 1

    ORDER BY
        publication_time,
        rfc_number
    """

    print(
        "Loading RFC records and matching historical groups...",
        flush=True,
    )

    dataframe = pd.read_sql_query(
        query,
        connection,
        params=(RFC_DOCUMENT_TYPE,),
    )

    print(
        f"Loaded {len(dataframe):,} RFC records.",
        flush=True,
    )

    if dataframe.empty:
        raise RuntimeError(
            "No RFC records were returned."
        )

    return dataframe


# =============================================================================
# Data preparation
# =============================================================================

def classify_area(row: pd.Series) -> str:
    """
    Assign an RFC to a recognised IETF technical Area.

    Non-IETF streams and unrecognised organisational groups are placed
    in Other.
    """

    stream_slug = row["stream_slug"]

    if stream_slug != "ietf":
        return "Other"

    area_acronym = row["resolved_area_acronym"]

    if pd.notna(area_acronym):
        area_slug = str(
            area_acronym
        ).strip().lower()

        if area_slug in MAIN_AREAS:
            return area_slug

    # Some RFC records may point directly to an Area.
    group_type_slug = row[
        "resolved_group_type_slug"
    ]

    group_acronym = row[
        "resolved_group_acronym"
    ]

    if (
        group_type_slug == "area"
        and pd.notna(group_acronym)
    ):
        group_slug = str(
            group_acronym
        ).strip().lower()

        if group_slug in MAIN_AREAS:
            return group_slug

    return "Other"


def prepare_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Prepare dates, URI slugs and Area classifications."""

    dataframe = dataframe.copy()

    dataframe["publication_time"] = pd.to_datetime(
        dataframe["publication_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["wg_history_time"] = pd.to_datetime(
        dataframe["wg_history_time"],
        utc=True,
        errors="coerce",
    )

    dataframe["area_history_time"] = pd.to_datetime(
        dataframe["area_history_time"],
        utc=True,
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=["publication_time"]
    ).copy()

    dataframe["publication_year"] = (
        dataframe["publication_time"].dt.year
    )

    dataframe["stream_slug"] = (
        dataframe["stream"].apply(
            extract_slug
        )
    )

    dataframe["resolved_group_type_slug"] = (
        dataframe["resolved_group_type"].apply(
            extract_slug
        )
    )

    dataframe["resolved_area_type_slug"] = (
        dataframe["resolved_area_type"].apply(
            extract_slug
        )
    )

    dataframe["area_category"] = dataframe.apply(
        classify_area,
        axis=1,
    )

    return dataframe


# =============================================================================
# Aggregation
# =============================================================================

def create_counts(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Count RFCs by publication year and historical Area."""

    plot_dataframe = dataframe[
        dataframe["publication_year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    counts = (
        plot_dataframe
        .groupby(
            [
                "publication_year",
                "area_category",
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

    remaining_columns = [
        area
        for area in counts.columns
        if area not in ordered_columns
    ]

    counts = counts[
        ordered_columns
        + sorted(remaining_columns)
    ]

    counts.index.name = "publication_year"

    return counts


# =============================================================================
# Plotting
# =============================================================================

def create_figure(
    counts: pd.DataFrame,
) -> None:
    """Create and save the stacked area chart."""

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
        "RFCs Published by IETF Area, 2001–2025"
    )

    axis.set_xlabel(
        "Publication year"
    )

    axis.set_ylabel(
        "Number of RFCs published"
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
            "Area assignments use the latest available group-history "
            "record at or before each RFC publication date."
        ),
        ha="center",
        fontsize=9,
    )

    figure.tight_layout(
        rect=[0, 0.04, 1, 1]
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
    dataframe: pd.DataFrame,
    counts: pd.DataFrame,
) -> None:
    """Print summary statistics and validation information."""

    print("\n" + "=" * 80)
    print("FIGURE 1 — HISTORICAL AREA SUMMARY")
    print("=" * 80)

    print(
        f"\nRFC records: "
        f"{len(dataframe):,}"
    )

    print(
        "\nPublication years:",
        int(
            dataframe["publication_year"].min()
        ),
        "to",
        int(
            dataframe["publication_year"].max()
        ),
    )

    print("\nArea categories:")
    print(
        dataframe["area_category"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nWorking Group mapping source:")
    print(
        dataframe[
            "working_group_mapping_source"
        ]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nArea mapping source:")
    print(
        dataframe[
            "area_mapping_source"
        ]
        .value_counts(dropna=False)
        .to_string()
    )

    print("\nRFC counts by year, 2012–2025:")

    yearly_counts = counts.sum(
        axis=1
    )

    print(
        yearly_counts.loc[
            yearly_counts.index >= 2012
        ].to_string()
    )

    print("\nRFC 9000 validation:")

    rfc9000 = dataframe[
        dataframe["rfc_number"] == 9000
    ]

    if rfc9000.empty:
        print(
            "RFC 9000 was not found."
        )

    else:
        validation_columns = [
            "rfc_number",
            "publication_time",
            "resolved_group_acronym",
            "historical_parent_uri",
            "resolved_parent_uri",
            "historical_area_acronym",
            "current_area_acronym",
            "resolved_area_acronym",
            "area_category",
            "working_group_mapping_source",
            "area_mapping_source",
        ]

        print(
            rfc9000[
                validation_columns
            ].to_string(
                index=False
            )
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    print(
        "Database:",
        DATABASE_PATH.resolve(),
    )

    print(
        "Exists:",
        DATABASE_PATH.exists(),
    )

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: "
            f"{DATABASE_PATH.resolve()}"
        )

    OUTPUT_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FIGURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:
        check_database_tables(
            connection
        )

        dataframe = load_historical_rfc_data(
            connection
        )

    finally:
        connection.close()

    print(
        "Preparing RFC classifications...",
        flush=True,
    )

    dataframe = prepare_dataframe(
        dataframe
    )

    counts = create_counts(
        dataframe
    )

    dataframe.to_csv(
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
        dataframe,
        counts,
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