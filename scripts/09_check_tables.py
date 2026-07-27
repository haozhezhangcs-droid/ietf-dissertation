import sqlite3

db = r"C:\Users\ZHZ\Desktop\ietf-dissertation\data\ietfdata-dt.sqlite"

conn = sqlite3.connect(db)
cur = conn.cursor()

print("=" * 80)
print("RFC9000 became_rfc")
print("=" * 80)

cur.execute("""
SELECT
    source,
    target
FROM ietf_dt_doc_relateddocument
WHERE relationship='/api/v1/name/docrelationshipname/became_rfc/'
AND target LIKE '%9000%';
""")

rows = cur.fetchall()

for r in rows:
    print(r)

print("\n")

print("=" * 80)
print("QUIC replaces")
print("=" * 80)

cur.execute("""
SELECT
    source,
    target
FROM ietf_dt_doc_relateddocument
WHERE relationship='/api/v1/name/docrelationshipname/replaces/'
AND (
source LIKE '%quic%'
OR target LIKE '%quic%'
)
ORDER BY source;
""")

rows = cur.fetchall()

for r in rows:
    print(r)

conn.close()