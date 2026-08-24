from __future__ import annotations

from pathlib import Path
from ietfdata.datatracker import DataTracker
from ietfdata.tools.organisations import OrganisationMatcher

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
RFC_INDEX_PATH = PROJECT_ROOT / "data" / "rfc-index.xml"

RESOLUTION_DIR = PROJECT_ROOT / "outputs" / "resolution"
RESOLUTION_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = RESOLUTION_DIR / "organisations.json"
MISSING_RFC_LOG = RESOLUTION_DIR / "organisation_missing_rfc_documents.txt"

_original_document_from_rfc = DataTracker.document_from_rfc
missing_rfcs: list[str] = []

def safe_document_from_rfc(self: DataTracker, rfc: str):
    try:
        return _original_document_from_rfc(self, rfc)
    except RuntimeError as exc:
        if "Cannot retrieve /api/v1/doc/document/" in str(exc):
            missing_rfcs.append(str(rfc))
            return None
        raise

print("=" * 72)
print("ORGANISATION ENTITY RESOLUTION")
print("=" * 72)

DataTracker.document_from_rfc = safe_document_from_rfc

try:
    matcher = OrganisationMatcher()
    matcher.find_organisations_ietf(
        str(DATABASE_PATH),
        str(RFC_INDEX_PATH),
    )
    matcher.consolidate_organisations()
    matcher.dump(OUTPUT_JSON)
finally:
    DataTracker.document_from_rfc = _original_document_from_rfc

missing_unique = sorted(set(missing_rfcs))
MISSING_RFC_LOG.write_text(
    "\n".join(missing_unique),
    encoding="utf-8",
)

print()
print(f"Saved: {OUTPUT_JSON}")
print(
    "RFC Index entries absent from Datatracker archive:",
    len(missing_unique),
)
print(f"Audit: {MISSING_RFC_LOG}")