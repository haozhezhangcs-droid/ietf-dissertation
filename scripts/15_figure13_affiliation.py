from __future__ import annotations

from pathlib import Path
import re
import sqlite3
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
OUTPUT_DATA_DIR = PROJECT_ROOT / "output" / "data"
OUTPUT_FIGURE_DIR = PROJECT_ROOT / "output" / "figures"

OUTPUT_RAW_CSV = OUTPUT_DATA_DIR / "figure13_author_affiliations_raw.csv"
OUTPUT_CLASSIFIED_CSV = OUTPUT_DATA_DIR / "figure13_author_affiliations_classified.csv"
OUTPUT_COUNTS_CSV = OUTPUT_DATA_DIR / "figure13_author_affiliations_counts.csv"
OUTPUT_PERCENTAGES_CSV = OUTPUT_DATA_DIR / "figure13_author_affiliations_percentages.csv"
OUTPUT_FIGURE_PNG = OUTPUT_FIGURE_DIR / "figure13_author_affiliations_normalised_2001_2025.png"

START_YEAR = 2001
END_YEAR = 2025
RFC_DOCUMENT_TYPE = "/api/v1/name/doctypename/rfc/"
BECAME_RFC_RELATIONSHIP = "/api/v1/name/docrelationshipname/became_rfc/"

CATEGORY_ORDER = [
    "Cisco", "Huawei", "Ericsson", "Juniper", "Nokia", "Microsoft",
    "Google", "Alcatel", "Oracle", "AT&T", "Academia", "Other",
]

CATEGORY_COLORS = {
    "Cisco": "#1f77b4", "Huawei": "#ff7f0e", "Ericsson": "#2ca02c",
    "Juniper": "#d62728", "Nokia": "#9467bd", "Microsoft": "#8c564b",
    "Google": "#e377c2", "Alcatel": "#7f7f7f", "Oracle": "#bcbd22",
    "AT&T": "#17becf", "Academia": "#c00040", "Other": "#5b8500",
}

ORGANIZATION_PATTERNS = {
    "Cisco": [r"\bcisco\b", r"\bcisco systems\b"],
    "Huawei": [r"\bhuawei\b", r"\bfuturewei\b"],
    "Ericsson": [r"\bericsson\b", r"\btelefonaktiebolaget lm ericsson\b"],
    "Juniper": [r"\bjuniper\b", r"\bjuniper networks\b"],
    "Nokia": [r"\bnokia\b", r"\bnokia bell labs\b", r"\bbell labs\b"],
    "Microsoft": [r"\bmicrosoft\b", r"\bmicrosoft research\b"],
    "Google": [r"\bgoogle\b", r"\bgoogle llc\b", r"\bgoogle inc\b"],
    "Alcatel": [r"\balcatel\b", r"\balcatel lucent\b"],
    "Oracle": [r"\boracle\b", r"\bsun microsystems\b"],
    "AT&T": [r"\bat&t\b", r"\batt\b", r"\bat and t\b"],
}

ACADEMIA_PATTERNS = [
    r"\buniversity\b", r"\buniversit[eé]\b", r"\buniversidad\b",
    r"\buniversita\b", r"\buniversität\b", r"\bcollege\b",
    r"\bpolytechnic\b", r"\btechnion\b", r"\bacademy\b",
    r"\bacademia\b", r"\bschool of\b", r"\binstitute of technology\b",
    r"\bresearch institute\b", r"\bnational institute\b", r"\bcsiro\b",
    r"\binria\b", r"\bcnrs\b", r"\bimec\b", r"\bkaist\b",
    r"\bmit\b", r"\beth zurich\b", r"\bepfl\b", r"\btu delft\b",
]


def normalise_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = text.replace("&amp;", "&").replace("’", "'")
    text = re.sub(r"[.,;:()\[\]{}\"']", " ", text)
    text = re.sub(r"[/\\|_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_affiliation(affiliation, email):
    affiliation_text = (
        ""
        if pd.isna(affiliation)
        else str(affiliation).strip().lower()
    )

    email_text = (
        ""
        if pd.isna(email)
        else str(email).strip().lower()
    )

    # Company matching
    if "cisco" in affiliation_text:
        return "Cisco"

    if (
        "huawei" in affiliation_text
        or "futurewei" in affiliation_text
    ):
        return "Huawei"

    if "ericsson" in affiliation_text:
        return "Ericsson"

    if "juniper" in affiliation_text:
        return "Juniper"

    if (
        "nokia" in affiliation_text
        or "bell labs" in affiliation_text
    ):
        return "Nokia"

    if "microsoft" in affiliation_text:
        return "Microsoft"

    if "google" in affiliation_text:
        return "Google"

    if "alcatel" in affiliation_text:
        return "Alcatel"

    if (
        "oracle" in affiliation_text
        or "sun microsystems" in affiliation_text
    ):
        return "Oracle"

    if (
        "at&t" in affiliation_text
        or "at and t" in affiliation_text
        or affiliation_text == "att"
    ):
        return "AT&T"

    # Academia matching
    academic_keywords = [
        "university",
        "université",
        "universidad",
        "universita",
        "universität",
        "college",
        "polytechnic",
        "institute of technology",
        "research institute",
        "academy",
        "school of",
        "technion",
        "inria",
        "cnrs",
        "kaist",
        "epfl",
        "eth zurich",
        "tu delft",
    ]

    for keyword in academic_keywords:
        if keyword in affiliation_text:
            return "Academia"

    # Use email only when affiliation is empty
    if affiliation_text == "":
        email_domains = {
            "cisco.com": "Cisco",
            "huawei.com": "Huawei",
            "futurewei.com": "Huawei",
            "ericsson.com": "Ericsson",
            "juniper.net": "Juniper",
            "nokia.com": "Nokia",
            "microsoft.com": "Microsoft",
            "google.com": "Google",
            "oracle.com": "Oracle",
            "att.com": "AT&T",
        }

        for domain, category in email_domains.items():
            if domain in email_text:
                return category

        return None

    return "Other"


def check_required_tables(connection: sqlite3.Connection) -> None:
    required = {
        "ietf_dt_doc_document", "ietf_dt_doc_docevent",
        "ietf_dt_doc_relateddocument", "ietf_dt_doc_documentauthor",
        "ietf_dt_person_person", "ietf_dt_person_email",
    }
    existing = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = required - existing
    if missing:
        raise RuntimeError(f"Missing required tables: {sorted(missing)}")


def load_author_affiliations(connection: sqlite3.Connection) -> pd.DataFrame:
    query = """
    WITH publication_events AS (
        SELECT doc, MIN(time) AS publication_time
        FROM ietf_dt_doc_docevent
        WHERE type = 'published_rfc'
        GROUP BY doc
    ),
    rfc_base AS (
        SELECT rfc.resource_uri AS rfc_uri, rfc.rfc_number,
               rfc.name AS rfc_name, rfc.title AS rfc_title,
               pe.publication_time
        FROM ietf_dt_doc_document AS rfc
        JOIN publication_events AS pe ON pe.doc = rfc.resource_uri
        WHERE rfc.type = ? AND rfc.rfc_number IS NOT NULL
    ),
    source_drafts AS (
        SELECT DISTINCT target AS rfc_uri, source AS draft_uri
        FROM ietf_dt_doc_relateddocument
        WHERE relationship = ?
    ),
    draft_authors AS (
        SELECT rb.*, sd.draft_uri AS author_document_uri,
               'source_draft' AS author_source,
               da."order" AS author_order, da.person AS person_uri,
               p.name AS person_name, da.email AS email_uri,
               e.address AS email_address, da.affiliation, da.country
        FROM rfc_base AS rb
        JOIN source_drafts AS sd ON sd.rfc_uri = rb.rfc_uri
        JOIN ietf_dt_doc_documentauthor AS da ON da.document = sd.draft_uri
        LEFT JOIN ietf_dt_person_person AS p ON p.resource_uri = da.person
        LEFT JOIN ietf_dt_person_email AS e ON e.resource_uri = da.email
    ),
    rfcs_with_draft_authors AS (
        SELECT DISTINCT rfc_uri FROM draft_authors
    ),
    direct_rfc_authors AS (
        SELECT rb.*, rb.rfc_uri AS author_document_uri,
               'rfc_fallback' AS author_source,
               da."order" AS author_order, da.person AS person_uri,
               p.name AS person_name, da.email AS email_uri,
               e.address AS email_address, da.affiliation, da.country
        FROM rfc_base AS rb
        JOIN ietf_dt_doc_documentauthor AS da ON da.document = rb.rfc_uri
        LEFT JOIN ietf_dt_person_person AS p ON p.resource_uri = da.person
        LEFT JOIN ietf_dt_person_email AS e ON e.resource_uri = da.email
        WHERE rb.rfc_uri NOT IN (SELECT rfc_uri FROM rfcs_with_draft_authors)
    )
    SELECT * FROM draft_authors
    UNION ALL
    SELECT * FROM direct_rfc_authors
    ORDER BY publication_time, rfc_number, author_order
    """
    print("Loading RFC author affiliation records...", flush=True)
    df = pd.read_sql_query(
        query, connection,
        params=(RFC_DOCUMENT_TYPE, BECAME_RFC_RELATIONSHIP),
    )
    print(f"Loaded {len(df):,} raw author records.", flush=True)
    if df.empty:
        raise RuntimeError("No RFC author records were found.")
    return df


def prepare_records(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["publication_time"] = pd.to_datetime(df["publication_time"], utc=True, errors="coerce")
    df["publication_year"] = df["publication_time"].dt.year
    df = df.dropna(subset=["publication_year"]).copy()
    df["publication_year"] = df["publication_year"].astype(int)
    df = df[df["publication_year"].between(START_YEAR, END_YEAR)].copy()
    df["affiliation_raw"] = df["affiliation"].fillna("").astype(str).str.strip()
    df["category"] = df.apply(
        lambda row: classify_affiliation(row["affiliation_raw"], row["email_address"]),
        axis=1,
    )
    df["has_affiliation"] = df["affiliation_raw"] != ""

    df["author_id"] = df["person_uri"].fillna("").astype(str).str.strip()
    mask = df["author_id"] == ""
    df.loc[mask, "author_id"] = (
        df.loc[mask, "email_address"].fillna("").astype(str).str.lower().str.strip()
    )
    mask = df["author_id"] == ""
    df.loc[mask, "author_id"] = (
        df.loc[mask, "person_name"].fillna("").astype(str).str.lower().str.strip()
    )
    return df[df["author_id"] != ""].copy()


def create_classified_records(df: pd.DataFrame) -> pd.DataFrame:
    out = df.dropna(subset=["category"]).copy()
    out = out.sort_values([
        "publication_year", "author_id", "category", "publication_time", "rfc_number"
    ])
    return out.drop_duplicates(
        subset=["publication_year", "author_id", "category"], keep="first"
    ).reset_index(drop=True)


def create_counts(classified: pd.DataFrame) -> pd.DataFrame:
    counts = classified.groupby(["publication_year", "category"]).size().unstack(fill_value=0)
    counts = counts.reindex(range(START_YEAR, END_YEAR + 1), fill_value=0)
    counts = counts.reindex(columns=CATEGORY_ORDER, fill_value=0)
    counts.index.name = "publication_year"
    return counts


def create_percentages(counts: pd.DataFrame) -> pd.DataFrame:
    totals = counts.sum(axis=1)
    return counts.div(totals.replace(0, pd.NA), axis=0).mul(100).fillna(0.0)


def create_figure(percentages: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.stackplot(
        percentages.index,
        *[percentages[c] for c in CATEGORY_ORDER],
        labels=CATEGORY_ORDER,
        colors=[CATEGORY_COLORS[c] for c in CATEGORY_ORDER],
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Percentage of authors")
    ax.set_xlim(START_YEAR - 0.5, END_YEAR + 0.5)
    ax.set_ylim(0, 105)
    ax.set_xticks(range(START_YEAR, END_YEAR + 1))
    ax.tick_params(axis="x", labelrotation=90)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="both", alpha=0.35)
    ax.legend(loc="upper left", ncol=3, framealpha=0.85)
    fig.tight_layout()
    fig.savefig(OUTPUT_FIGURE_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_diagnostics(raw, classified, counts, percentages) -> None:
    print("\n" + "=" * 80)
    print("FIGURE 13 — AUTHORSHIP AFFILIATIONS")
    print("=" * 80)
    print(f"\nRaw author records: {len(raw):,}")
    print(f"Explicit non-empty affiliations: {raw['has_affiliation'].sum():,}")
    print(f"Records assigned to a category: {raw['category'].notna().sum():,}")
    print(f"Unique author-year-category records: {len(classified):,}")
    print("\nAuthor source:")
    print(raw["author_source"].value_counts(dropna=False).to_string())
    print("\nUnique classified authors by year:")
    print(counts.sum(axis=1).to_string())
    print("\nPercentage totals by year:")
    print(percentages.sum(axis=1).round(4).to_string())
    print("\nRFC 9000 validation:")
    check = raw[raw["rfc_number"] == 9000][
        ["rfc_number", "person_name", "affiliation_raw", "category", "author_source"]
    ]
    print("RFC 9000 not found." if check.empty else check.to_string(index=False))
    print("\nMost frequent raw affiliations:")
    print(raw.loc[raw["affiliation_raw"] != "", "affiliation_raw"].value_counts().head(40).to_string())
    print("\nCategory totals:")
    print(counts.sum(axis=0).sort_values(ascending=False).to_string())


def main() -> None:
    print("Database:", DATABASE_PATH.resolve())
    print("Exists:", DATABASE_PATH.exists())
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(DATABASE_PATH.resolve())

    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA cache_size=-500000")
        check_required_tables(connection)
        raw = load_author_affiliations(connection)
    finally:
        connection.close()

    raw = prepare_records(raw)
    classified = create_classified_records(raw)
    counts = create_counts(classified)
    percentages = create_percentages(counts)

    raw.to_csv(OUTPUT_RAW_CSV, index=False, encoding="utf-8-sig")
    classified.to_csv(OUTPUT_CLASSIFIED_CSV, index=False, encoding="utf-8-sig")
    counts.to_csv(OUTPUT_COUNTS_CSV, encoding="utf-8-sig")
    percentages.to_csv(OUTPUT_PERCENTAGES_CSV, encoding="utf-8-sig")
    create_figure(percentages)
    print_diagnostics(raw, classified, counts, percentages)

    print("\nCreated files:")
    print(OUTPUT_RAW_CSV)
    print(OUTPUT_CLASSIFIED_CSV)
    print(OUTPUT_COUNTS_CSV)
    print(OUTPUT_PERCENTAGES_CSV)
    print(OUTPUT_FIGURE_PNG)


if __name__ == "__main__":
    main()