from pathlib import Path

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


DATABASE_PATH = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation\data\ietfdata-dt.sqlite")


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH.resolve()}\n"
            "Please update DATABASE_PATH to the SQLite snapshot provided by Colin."
        )

    dt = DataTracker(DTBackendArchive(str(DATABASE_PATH)))

    rfc = dt.document_from_rfc("RFC9000")

    if rfc is None:
        raise RuntimeError("RFC9000 could not be found in the database.")

    print("Name:", rfc.name)
    print("Title:", rfc.title)
    print("Group:", rfc.group)
    print("RFC number:", rfc.rfc_number)
    print("Time:", rfc.time)


if __name__ == "__main__":
    main()