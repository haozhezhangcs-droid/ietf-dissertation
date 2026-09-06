from __future__ import annotations

import logging
import os
from pathlib import Path

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive
from ietfdata.tools.participants import ParticipantDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

RESOLUTION_DIR = PROJECT_ROOT / "outputs" / "resolution"
RESOLUTION_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = RESOLUTION_DIR / "participants.json"

logging.basicConfig(
    level=os.environ.get("IETFDATA_LOGLEVEL", "INFO")
)
log = logging.getLogger("ietfdata")

pdb = ParticipantDB()

ignore = {
    "noreply@ietf.org",
    "noreply@github.com",
    "noreply=40github.com@dmarc.ietf.org",
    "notifications@github.com",
    "noreply@icloud.com",
    "noname@noname.com",
    "messenger@webex.com",
    "tracker-forces@mip4.org",
    "tracker-forces@MIP4.ORG",
    "tracker-mip6@mip4.org",
    "tracker-mip4@mip4.org",
    "tracker-mip4@levkowetz.com",
    "3761bis@frobbit.se",
    "ietf-action@ietf.org",
    "ctp_issues@danforsberg.info",
}

dt = DataTrackerExt(
    DTBackendArchive(str(DATABASE_PATH))
)

print("=" * 72)
print("DATATRACKER-ONLY PARTICIPANT ENTITY RESOLUTION")
print("=" * 72)

print("Finding participants in IETF Datatracker: names")

person_count = 0

for dt_person in dt.people():
    person_count += 1
    person_uri = str(dt_person.resource_uri)

    pdb.person_with_identifier(
        "dt_person_uri",
        person_uri,
    )

    candidate_names = [
        dt_person.name,
        dt_person.name_from_draft,
        dt_person.ascii,
        dt_person.ascii_short,
        dt_person.plain,
    ]

    for name in candidate_names:
        if name is None:
            continue

        name = str(name).strip()

        if not name:
            continue

        pdb.person_with_name(
            "dt_person_uri",
            person_uri,
            name,
        )

print(f"Datatracker Person records processed: {person_count:,}")

print()
print("Finding participants in IETF Datatracker: emails")

email_count = 0
ignored_email_count = 0

for msg in dt.emails():
    address = str(msg.address).strip()

    if not address:
        continue

    if address in ignore:
        ignored_email_count += 1
        continue

    email_count += 1

    person_uri = str(msg.person)

    pdb.person_with_identifier(
        "email",
        address,
    )

    pdb.identifies_same_person(
        "email",
        address,
        "dt_person_uri",
        person_uri,
    )

    lowercase_address = address.lower()

    if lowercase_address != address:
        pdb.person_with_identifier(
            "email",
            lowercase_address,
        )

        pdb.identifies_same_person(
            "email",
            lowercase_address,
            "email",
            address,
        )

print(f"Datatracker email records processed: {email_count:,}")
print(f"Ignored automated/problem email records: {ignored_email_count:,}")

print()
print("Finding participants in IETF Datatracker: external resources")

resource_count = 0

for resource in dt.person_ext_resources():
    resource_count += 1

    person_uri = str(resource.person)
    resource_name = str(resource.name)
    resource_value = str(resource.value).strip()

    if not resource_value:
        continue

    if resource_name == "/api/v1/name/extresourcename/webpage/":
        pdb.identifies_same_person(
            "dt_person_uri",
            person_uri,
            "webpage",
            resource_value,
        )

    elif resource_name == "/api/v1/name/extresourcename/github_username/":
        pdb.identifies_same_person(
            "dt_person_uri",
            person_uri,
            "github_username",
            resource_value,
        )

    elif resource_name == "/api/v1/name/extresourcename/gitlab_username/":
        pdb.identifies_same_person(
            "dt_person_uri",
            person_uri,
            "gitlab_username",
            resource_value,
        )

    elif resource_name == "/api/v1/name/extresourcename/orcid/":
        pdb.identifies_same_person(
            "dt_person_uri",
            person_uri,
            "orcid",
            resource_value,
        )

print(f"External resource records processed: {resource_count:,}")

print()
print(f"Saving {OUTPUT_JSON}")

pdb.save(OUTPUT_JSON)

print()
print("=" * 72)
print("PARTICIPANT RESOLUTION COMPLETE")
print("=" * 72)
print("MailArchive used: NO")
print("Resolution evidence used:")
print("  - Datatracker Person URI")
print("  - Datatracker names")
print("  - Datatracker email -> Person links")
print("  - Datatracker webpage/GitHub/GitLab/ORCID links")
print()
print(f"Saved: {OUTPUT_JSON}")