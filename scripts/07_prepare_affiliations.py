from __future__ import annotations

import json
import logging
import textwrap
from pathlib import Path

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive
from ietfdata.rfcindex import RFCIndex
from ietfdata.tools.affiliations import Affiliations, rfc_date

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
RFC_INDEX_PATH = PROJECT_ROOT / "data" / "rfc-index.xml"

RESOLUTION_DIR = PROJECT_ROOT / "outputs" / "resolution"

PARTICIPANTS_JSON = RESOLUTION_DIR / "participants.json"
ORGANISATIONS_JSON = RESOLUTION_DIR / "organisations.json"
OUTPUT_JSON = RESOLUTION_DIR / "affiliations.json"

MISSING_RFC_LOG = RESOLUTION_DIR / "affiliation_missing_rfc_documents.txt"
CONFLICT_LOG = RESOLUTION_DIR / "affiliation_conflicts.json"

logging.basicConfig(level="INFO")
log = logging.getLogger("ietfdata")

with open(PARTICIPANTS_JSON, "r", encoding="utf-8") as infile:
    participants = json.load(infile)

emails: dict[str, str] = {}
for pid, record in participants.items():
    for email in record.get("email", []):
        emails[email] = pid

with open(ORGANISATIONS_JSON, "r", encoding="utf-8") as infile:
    organisations = json.load(infile)

org_names: dict[str, str] = {}
for org_id, record in organisations.items():
    for name in record.get("names", []):
        org_names[name] = org_id

print("=" * 72)
print("AFFILIATION RESOLUTION")
print("=" * 72)
print(f"Participants:      {len(participants):,}")
print(f"Email aliases:     {len(emails):,}")
print(f"Organisations:     {len(organisations):,}")
print(f"Org-name aliases:  {len(org_names):,}")

dt = DataTracker(DTBackendArchive(str(DATABASE_PATH)))
ri = RFCIndex(rfc_index=str(RFC_INDEX_PATH))
af = Affiliations()

missing_rfcs: list[str] = []

print()
print("Finding affiliations of RFC authors")

for rfc in ri.rfcs(since="1995-01"):
    log.info(
        f"{rfc.doc_id}: "
        f"{textwrap.shorten(rfc.title, width=80, placeholder='...')}"
    )

    try:
        dt_document = dt.document_from_rfc(rfc.doc_id)
    except RuntimeError as exc:
        if "Cannot retrieve /api/v1/doc/document/" in str(exc):
            missing_rfcs.append(rfc.doc_id)
            continue
        raise

    if dt_document is None:
        continue

    for dt_author in dt.document_authors(dt_document):
        if dt_author.affiliation == "" or dt_author.email is None:
            continue

        affil = dt_author.affiliation.replace("\n", " ")
        email = dt.email(dt_author.email)

        if email is None:
            continue

        date_ = rfc_date(rfc.year, rfc.month)

        if email.address not in emails or affil not in org_names:
            continue

        af.add(
            date_,
            emails[email.address],
            org_names[affil],
        )

print()
print("Finding affiliations in Internet-Draft submissions")

for index, submission in enumerate(dt.submissions(), start=1):
    if index % 5000 == 0:
        print(f"  submissions processed: {index:,}")

    if (
        str(submission.state)
        != "/api/v1/name/draftsubmissionstatename/posted/"
    ):
        continue

    for author in submission.parse_authors():
        if "affiliation" not in author or "email" not in author:
            continue

        email_address = author["email"]
        affiliation = author["affiliation"]

        if email_address not in emails or affiliation not in org_names:
            continue

        af.add(
            submission.submission_date,
            emails[email_address],
            org_names[affiliation],
        )

print()
print("Finding affiliations in meeting registrations")

for index, registration in enumerate(dt.meeting_registrations(), start=1):
    if index % 5000 == 0:
        print(f"  registrations processed: {index:,}")

    meeting = dt.meeting(registration.meeting)
    if meeting is None:
        continue

    email_address = registration.email
    affiliation = registration.affiliation

    if email_address not in emails or affiliation not in org_names:
        continue

    af.add(
        meeting.date,
        emails[email_address],
        org_names[affiliation],
    )

af.save(str(OUTPUT_JSON))

missing_unique = sorted(set(missing_rfcs))
MISSING_RFC_LOG.write_text(
    "\n".join(missing_unique),
    encoding="utf-8",
)

conflicts = af.get_conflicts()

with open(CONFLICT_LOG, "w", encoding="utf-8") as outfile:
    json.dump(conflicts, outfile, indent=2)

print()
print("=" * 72)
print("AFFILIATION RESOLUTION COMPLETE")
print("=" * 72)
print(f"Saved: {OUTPUT_JSON}")
print(f"Missing RFC Documents skipped: {len(missing_unique)}")
print(
    "Participants with conflicting affiliation evidence:",
    len(conflicts),
)
print(f"Missing-RFC audit: {MISSING_RFC_LOG}")
print(f"Conflict audit:    {CONFLICT_LOG}")