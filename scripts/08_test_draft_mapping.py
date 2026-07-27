import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

conn = sqlite3.connect(DATABASE_PATH)

rows = conn.execute("""
SELECT DISTINCT relationship
FROM ietf_dt_doc_relateddocument
ORDER BY relationship
""").fetchall()

for r in rows:
    print(r[0])

conn.close()
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

conn = sqlite3.connect(DATABASE_PATH)

rows = conn.execute("""
SELECT DISTINCT relationship
FROM ietf_dt_doc_relateddocument
ORDER BY relationship
""").fetchall()

for r in rows:
    print(r[0])

conn.close()