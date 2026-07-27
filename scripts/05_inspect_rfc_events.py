from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"


def print_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> None:
    print("\n" + "=" * 80)
    print(f"TABLE: {table_name}")
    print("=" * 80)

    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for row in rows:
        cid, name, data_type, not_null, default_value, primary_key = row

        print(
            f"{cid:3}  "
            f"{name:30} "
            f"{data_type:15} "
            f"notnull={not_null} "
            f"pk={primary_key}"
        )


def main() -> None:
    print("Database:", DATABASE_PATH.resolve())
    print("Exists:", DATABASE_PATH.exists())

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH.resolve()}"
        )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        print_table_columns(
            connection,
            "ietf_dt_doc_document",
        )

        print_table_columns(
            connection,
            "ietf_dt_doc_docevent",
        )

        print("\n" + "=" * 80)
        print("RFC 9000 DOCUMENT RECORD")
        print("=" * 80)

        document = connection.execute(
            """
            SELECT *
            FROM ietf_dt_doc_document
            WHERE name = ?
            """,
            ("rfc9000",),
        ).fetchone()

        if document is None:
            print("RFC 9000 was not found.")
            return

        for key in document.keys():
            print(f"{key}: {document[key]}")

        print("\n" + "=" * 80)
        print("RFC 9000 DOCUMENT EVENTS")
        print("=" * 80)

        events = connection.execute(
            """
            SELECT *
            FROM ietf_dt_doc_docevent
            WHERE doc = ?
            ORDER BY time
            """,
            (document["resource_uri"],),
        ).fetchall()

        print("Document URI:", document["resource_uri"])
        print("Number of events:", len(events))

        for index, event in enumerate(events, start=1):
            print("\n" + "-" * 80)
            print(f"EVENT {index}")
            print("-" * 80)

            for key in event.keys():
                print(f"{key}: {event[key]}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()