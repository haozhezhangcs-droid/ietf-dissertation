from pathlib import Path
from itertools import islice

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"


def print_object_fields(obj) -> None:
    """Print all non-private, non-callable attributes of an object."""

    for name in sorted(dir(obj)):
        if name.startswith("_"):
            continue

        try:
            value = getattr(obj, name)
        except Exception as exc:
            value = f"<error: {exc}>"

        if not callable(value):
            print(f"{name}: {value}")


def main() -> None:
    print("Database:", DATABASE_PATH.resolve())
    print("Exists:", DATABASE_PATH.exists())
    print("Is file:", DATABASE_PATH.is_file())

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH.resolve()}"
        )

    dt = DataTracker(DTBackendArchive(str(DATABASE_PATH)))

    rfc_type = dt.document_type_from_slug("rfc")

    if rfc_type is None:
        raise RuntimeError("RFC document type was not found.")

    print("\nRFC document type:")
    print(rfc_type)

    print("\nRequesting RFC documents...")

    rfcs = dt.documents(doctype=rfc_type)
    first_rfcs = list(islice(rfcs, 3))

    print(f"\nNumber inspected: {len(first_rfcs)}")

    if not first_rfcs:
        print(
            "\nNo RFC documents were returned.\n"
            "This may mean that RFCs are stored as another document type "
            "or that the database snapshot is incomplete."
        )
        return

    for index, rfc in enumerate(first_rfcs, start=1):
        print("\n" + "=" * 80)
        print(f"RFC DOCUMENT {index}")
        print("=" * 80)

        print("Python object type:", type(rfc))
        print_object_fields(rfc)

    print("\nGROUP METHODS")

    for name in dir(dt):
        if "group" in name.lower():
            print(name)

    print("\nSTREAM METHODS")

    for name in dir(dt):
        if "stream" in name.lower():
            print(name)


if __name__ == "__main__":
    main()