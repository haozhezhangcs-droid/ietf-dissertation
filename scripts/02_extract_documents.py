"""
02_extract_documents.py

Current stage:
1. Extract basic Internet-Draft metadata.
2. Perform simple cleaning.
3. Export one CSV file.

Later stages are listed as comments at the end of this script.
"""

import sqlite3
from pathlib import Path

import pandas as pd


# ============================================================
# Step 1: Define project paths
# ============================================================

BASE_DIR = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation")
DB_PATH = BASE_DIR / "data" / "ietfdata-dt.sqlite"
OUTPUT_PATH = BASE_DIR / "outputs" / "csv" / "documents_basic.csv"

# Create the output folder if it does not already exist.
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# Step 2: Connect to the local Datatracker database
# ============================================================

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database file not found: {DB_PATH}"
    )

conn = sqlite3.connect(DB_PATH)


# ============================================================
# Step 3: Extract basic Internet-Draft metadata
# ============================================================

query = """
SELECT
    d.id AS document_id,
    d.name AS document_name,
    d.title,
    d.time AS created_at,
    d.type AS document_type,
    d."group" AS group_uri,
    d.rfc_number
FROM ietf_dt_doc_document AS d
WHERE d.type LIKE '%draft%';
"""

df = pd.read_sql_query(query, conn)

conn.close()


# ============================================================
# Step 4: Perform simple data cleaning
# ============================================================

# Remove exact duplicate rows.
df = df.drop_duplicates()

# Remove unnecessary spaces from text columns.
text_columns = [
    "document_name",
    "title",
    "document_type",
    "group_uri",
]

for column in text_columns:
    df[column] = df[column].astype("string").str.strip()

# Convert the date field into a standard datetime format.
df["created_at"] = pd.to_datetime(
    df["created_at"],
    errors="coerce",
    utc=True,
)

# Extract the year for later time-trend analysis.
df["year"] = df["created_at"].dt.year.astype("Int64")

# Create a simple RFC indicator.
df["is_rfc"] = df["rfc_number"].notna()

# Record missing values rather than deleting them immediately.
df["missing_title"] = df["title"].isna()
df["missing_group"] = df["group_uri"].isna()
df["missing_date"] = df["created_at"].isna()


# ============================================================
# Step 5: Save the cleaned dataset
# ============================================================

df.to_csv(
    OUTPUT_PATH,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# Step 6: Display a simple summary
# ============================================================

print("\n=== Basic document dataset ===")
print(df.head())

print("\nSummary:")
print("Total rows:", len(df))
print("Unique drafts:", df["document_name"].nunique())
print("Drafts with RFC number:", int(df["is_rfc"].sum()))
print("Missing titles:", int(df["missing_title"].sum()))
print("Missing groups:", int(df["missing_group"].sum()))
print("Missing dates:", int(df["missing_date"].sum()))

print("\nSaved to:")
print(OUTPUT_PATH)


# ============================================================
# Planned later stages — not implemented yet
# ============================================================

# TODO 1:
# Extract document states and determine whether each
# Internet-Draft was eventually published as an RFC.

# TODO 2:
# Extract author information for each Internet-Draft.

# TODO 3:
# Clean and standardise organisation names and affiliations.

# TODO 4:
# Link organisations to documents and calculate participation.

# TODO 5:
# Calculate Draft-to-RFC success rates by organisation.

# TODO 6:
# Analyse differences by IETF area, working group, and country.

# TODO 7:
# Analyse how participation and success have changed over time.

# TODO 8:
# Add mailing-list data in a later stage of the project.