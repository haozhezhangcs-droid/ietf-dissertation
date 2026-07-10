import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation")
DB_PATH = BASE_DIR / "data" / "ietfdata-dt.sqlite"
OUTPUT_PATH = BASE_DIR / "outputs" / "csv" / "documents_basic.csv"

conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    d.name AS document_name,
    d.title,
    d.time,
    d.type,
    d."group" AS group_uri,
    s.name AS state_name
FROM ietf_dt_doc_document d
LEFT JOIN ietf_dt_doc_document_states ds
    ON d.resource_uri = ds._parent
LEFT JOIN ietf_dt_doc_state s
    ON ds.states = s.resource_uri
WHERE d.type LIKE '%draft%';
"""

df = pd.read_sql_query(query, conn)

df["year"] = pd.to_datetime(df["time"], errors="coerce").dt.year
df["is_rfc"] = df["state_name"].isin(["RFC", "RFC Published"])

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(df.head())
print("Total rows:", len(df))
print("Saved to:", OUTPUT_PATH)