from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

RFC_URI = "/api/v1/doc/document/rfc9000/"
BECAME_RFC_RELATIONSHIP = (
    "/api/v1/name/docrelationshipname/became_rfc/"
)


def main() -> None:
    print("Database:", DATABASE_PATH.resolve())
    print("Exists:", DATABASE_PATH.exists())

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(DATABASE_PATH.resolve())

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT
                rd.resource_uri,
                rd.source,
                rd.target,
                rd.relationship,
                source_doc.name AS source_name,
                source_doc.title AS source_title,
                source_doc.rev AS source_rev,
                source_doc.type AS source_type,
                target_doc.name AS target_name,
                target_doc.rfc_number AS target_rfc_number
            FROM ietf_dt_doc_relateddocument AS rd

            LEFT JOIN ietf_dt_doc_document AS source_doc
                ON source_doc.resource_uri = rd.source

            LEFT JOIN ietf_dt_doc_document AS target_doc
                ON target_doc.resource_uri = rd.target

            WHERE rd.target = ?
              AND rd.relationship = ?
            """,
            (
                RFC_URI,
                BECAME_RFC_RELATIONSHIP,
            ),
        ).fetchall()

        print("\nNumber of became_rfc mappings:", len(rows))

        for index, row in enumerate(rows, start=1):
            print("\n" + "=" * 80)
            print(f"MAPPING {index}")
            print("=" * 80)

            for key in row.keys():
                print(f"{key}: {row[key]}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()