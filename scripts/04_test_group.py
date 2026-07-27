from pathlib import Path

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

dt = DataTracker(DTBackendArchive(str(DATABASE_PATH)))

rfc = dt.document_from_rfc("RFC9000")

if rfc is None:
    raise RuntimeError("RFC9000 was not found.")

print("RFC group URI:")
print(rfc.group)

group = dt.group(rfc.group)

print("\nWORKING GROUP:")
print("Acronym:", group.acronym)
print("Name:", group.name)
print("Parent:", group.parent)

if group.parent is not None:
    area = dt.group(group.parent)

    print("\nAREA:")
    print("Acronym:", area.acronym)
    print("Name:", area.name)
    print("Type:", area.type)