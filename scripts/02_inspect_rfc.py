from pathlib import Path

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


DATABASE_PATH = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation\data\ietfdata-dt.sqlite")


def main() -> None:
    dt = DataTracker(DTBackendArchive(str(DATABASE_PATH)))
    rfc = dt.document_from_rfc("RFC9000")

    if rfc is None:
        raise RuntimeError("RFC9000 was not found.")

    print("RFC object type:")
    print(type(rfc))

    print("\nAvailable attributes:")
    for name in sorted(dir(rfc)):
        if not name.startswith("_"):
            try:
                value = getattr(rfc, name)
            except Exception as exc:
                value = f"<error: {exc}>"

            if not callable(value):
                print(f"{name}: {value}")


if __name__ == "__main__":
    main()