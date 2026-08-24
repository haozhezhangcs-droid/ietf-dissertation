from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

LINEAGE_INPUT = PROJECT_ROOT / "outputs" / "common" / "lineage_outcomes.csv"
HISTORY_INPUT = PROJECT_ROOT / "outputs" / "common" / "lineage_history_records.csv"

RESOLUTION_DIR = PROJECT_ROOT / "outputs" / "resolution"

PARTICIPANTS_JSON = RESOLUTION_DIR / "participants.json"
ORGANISATIONS_JSON = RESOLUTION_DIR / "organisations.json"
AFFILIATIONS_JSON = RESOLUTION_DIR / "affiliations.json"
CONFLICTS_JSON = RESOLUTION_DIR / "affiliation_conflicts.json"

OUTPUT_DATASET = PROJECT_ROOT / "outputs" / "rq3_collaboration_dataset.csv"
OUTPUT_AUDIT = PROJECT_ROOT / "outputs" / "rq3_author_affiliation_audit.csv"


dt = DataTrackerExt(
    DTBackendArchive(str(DATABASE_PATH))
)

lineage_df = pd.read_csv(
    LINEAGE_INPUT,
    dtype=str,
).fillna("")

history_df = pd.read_csv(
    HISTORY_INPUT,
    dtype=str,
).fillna("")

history_df["date_dt"] = pd.to_datetime(
    history_df["date"],
    errors="coerce",
)


with open(PARTICIPANTS_JSON, "r", encoding="utf-8") as f:
    participants = json.load(f)

with open(ORGANISATIONS_JSON, "r", encoding="utf-8") as f:
    organisations = json.load(f)

with open(AFFILIATIONS_JSON, "r", encoding="utf-8") as f:
    affiliations = json.load(f)

if CONFLICTS_JSON.exists():
    with open(CONFLICTS_JSON, "r", encoding="utf-8") as f:
        affiliation_conflicts = json.load(f)
else:
    affiliation_conflicts = {}


dt_person_to_pid: Dict[str, str] = {}

for pid, record in participants.items():
    for person_uri in record.get("dt_person_uri", []):
        dt_person_to_pid[str(person_uri)] = pid


org_id_to_label: Dict[str, str] = {}

for org_id, record in organisations.items():
    names = [
        str(name).strip()
        for name in record.get("names", [])
        if str(name).strip()
    ]
    org_id_to_label[org_id] = names[0] if names else org_id


conflict_dates_by_pid: Dict[str, Set[str]] = {}

for pid, rows in affiliation_conflicts.items():
    dates: Set[str] = set()

    for conflict in rows:
        if isinstance(conflict, list) and len(conflict) >= 3:
            dates.add(str(conflict[2]))

    conflict_dates_by_pid[pid] = dates


document_first_dates: Dict[Tuple[str, str], pd.Timestamp] = {}

for (lineage_id, draft_name), group in history_df.groupby(
    ["lineage_id", "draft_name"]
):
    dates = group["date_dt"].dropna()

    if not dates.empty:
        document_first_dates[
            (str(lineage_id), str(draft_name))
        ] = dates.min()


def split_members(text: str) -> List[str]:
    return [
        item.strip()
        for item in str(text).split(";")
        if item.strip()
    ]


def affiliation_orgs_on_date(
    pid: str,
    date_value: pd.Timestamp,
) -> Set[str]:

    if pid not in affiliations:
        return set()

    date_string = date_value.date().isoformat()

    result: Set[str] = set()

    for item in affiliations[pid].get("affiliations", []):
        org_id = str(item.get("organisation", "")).strip()
        start_date = str(item.get("start_date", "")).strip()
        end_date = str(item.get("end_date", "")).strip()

        if not org_id or not start_date or not end_date:
            continue

        if start_date <= date_string <= end_date:
            result.add(org_id)

    return result


lineage_rows: List[dict] = []
audit_rows: List[dict] = []


for row_index, lineage_row in lineage_df.iterrows():

    if (row_index + 1) % 500 == 0:
        print(
            f"Processing RQ3 lineages: "
            f"{row_index + 1:,}/{len(lineage_df):,}"
        )

    lineage_id = str(lineage_row["lineage_id"])
    members = split_members(lineage_row["lineage_members"])

    unique_pids: Set[str] = set()
    authors_with_resolved_affiliation: Set[str] = set()
    lineage_org_ids: Set[str] = set()
    conflicted_pids: Set[str] = set()
    unresolved_person_uris: Set[str] = set()

    documents_with_cross_org = 0
    documents_with_resolved_affiliation = 0
    author_document_records = 0

    for draft_name in members:

        try:
            document = dt.document_from_draft(draft_name)
        except Exception:
            document = None

        if document is None:
            continue

        document_date = document_first_dates.get(
            (lineage_id, draft_name)
        )

        try:
            document_authors = list(
                dt.document_authors(document)
            )
        except Exception:
            document_authors = []

        document_org_ids: Set[str] = set()

        for document_author in document_authors:

            author_document_records += 1

            person_uri = str(document_author.person).strip()
            pid = dt_person_to_pid.get(person_uri, "")

            try:
                person = dt.person(document_author.person)
            except Exception:
                person = None

            person_name = (
                str(getattr(person, "name", "") or "").strip()
                if person is not None
                else ""
            )

            if not pid:
                if person_uri:
                    unresolved_person_uris.add(person_uri)

                audit_rows.append(
                    {
                        "lineage_id": lineage_id,
                        "draft_name": draft_name,
                        "document_date": (
                            document_date.date().isoformat()
                            if document_date is not None
                            else ""
                        ),
                        "person_uri": person_uri,
                        "pid": "",
                        "person_name": person_name,
                        "resolved_org_id": "",
                        "resolved_org_label": "",
                        "resolution_status": "Participant PID unresolved",
                        "has_conflict": 0,
                    }
                )
                continue

            unique_pids.add(pid)

            if document_date is None:
                audit_rows.append(
                    {
                        "lineage_id": lineage_id,
                        "draft_name": draft_name,
                        "document_date": "",
                        "person_uri": person_uri,
                        "pid": pid,
                        "person_name": person_name,
                        "resolved_org_id": "",
                        "resolved_org_label": "",
                        "resolution_status": "Document date unavailable",
                        "has_conflict": 0,
                    }
                )
                continue

            date_string = document_date.date().isoformat()

            org_candidates = affiliation_orgs_on_date(
                pid,
                document_date,
            )

            exact_conflict = (
                date_string
                in conflict_dates_by_pid.get(pid, set())
            )

            if exact_conflict:
                conflicted_pids.add(pid)
                resolution_status = "Affiliation conflict"
                resolved_org_id = ""

            elif len(org_candidates) > 1:
                conflicted_pids.add(pid)
                resolution_status = "Multiple affiliation candidates"
                resolved_org_id = ""

            elif len(org_candidates) == 1:
                resolved_org_id = next(iter(org_candidates))
                resolution_status = "Resolved"

                authors_with_resolved_affiliation.add(pid)
                lineage_org_ids.add(resolved_org_id)
                document_org_ids.add(resolved_org_id)

            else:
                resolved_org_id = ""
                resolution_status = "No affiliation on document date"

            audit_rows.append(
                {
                    "lineage_id": lineage_id,
                    "draft_name": draft_name,
                    "document_date": date_string,
                    "person_uri": person_uri,
                    "pid": pid,
                    "person_name": person_name,
                    "resolved_org_id": resolved_org_id,
                    "resolved_org_label": (
                        org_id_to_label.get(resolved_org_id, "")
                        if resolved_org_id
                        else ""
                    ),
                    "resolution_status": resolution_status,
                    "has_conflict": int(
                        resolution_status
                        in {
                            "Affiliation conflict",
                            "Multiple affiliation candidates",
                        }
                    ),
                }
            )

        if document_org_ids:
            documents_with_resolved_affiliation += 1

        if len(document_org_ids) >= 2:
            documents_with_cross_org += 1

    author_count = len(unique_pids)
    resolved_author_count = len(authors_with_resolved_affiliation)

    affiliation_coverage = (
        resolved_author_count / author_count
        if author_count > 0
        else None
    )

    lineage_organisation_count = len(lineage_org_ids)

    output_row = lineage_row.to_dict()

    output_row.update(
        {
            "lineage_author_count": author_count,
            "authors_with_resolved_affiliation": resolved_author_count,
            "affiliation_coverage": affiliation_coverage,
            "complete_affiliation_coverage": int(
                author_count > 0
                and resolved_author_count == author_count
            ),
            "lineage_organisation_count": lineage_organisation_count,
            "lineage_organisation_ids": ";".join(
                sorted(lineage_org_ids)
            ),
            "lineage_organisation_labels": ";".join(
                sorted(
                    {
                        org_id_to_label.get(org_id, org_id)
                        for org_id in lineage_org_ids
                    }
                )
            ),
            "multi_organisation_history": int(
                lineage_organisation_count >= 2
            ),
            "cross_organisation": int(
                documents_with_cross_org >= 1
            ),
            "cross_organisation_document_count": documents_with_cross_org,
            "documents_with_resolved_affiliation":
                documents_with_resolved_affiliation,
            "has_affiliation_conflict": int(
                len(conflicted_pids) > 0
            ),
            "conflicted_author_count": len(conflicted_pids),
            "unresolved_participant_count": len(
                unresolved_person_uris
            ),
            "author_document_records": author_document_records,
        }
    )

    lineage_rows.append(output_row)


rq3_df = pd.DataFrame(lineage_rows)
audit_df = pd.DataFrame(audit_rows)

rq3_df.to_csv(
    OUTPUT_DATASET,
    index=False,
)

audit_df.to_csv(
    OUTPUT_AUDIT,
    index=False,
)


print()
print("=" * 72)
print("RQ3 COLLABORATION DATASET")
print("=" * 72)

print("Lineages:", f"{len(rq3_df):,}")

print(
    "Lineages with >=1 resolved author:",
    f"{int((pd.to_numeric(rq3_df['lineage_author_count']) > 0).sum()):,}",
)

print(
    "Lineages with >=1 resolved organisation:",
    f"{int((pd.to_numeric(rq3_df['lineage_organisation_count']) > 0).sum()):,}",
)

print(
    "Lineages with multi-organisation history:",
    f"{int((pd.to_numeric(rq3_df['multi_organisation_history']) == 1).sum()):,}",
)

print(
    "Cross-organisation co-authorship lineages:",
    f"{int((pd.to_numeric(rq3_df['cross_organisation']) == 1).sum()):,}",
)

print(
    "Lineages with complete affiliation coverage:",
    f"{int((pd.to_numeric(rq3_df['complete_affiliation_coverage']) == 1).sum()):,}",
)

print(
    "Lineages containing affiliation conflict:",
    f"{int((pd.to_numeric(rq3_df['has_affiliation_conflict']) == 1).sum()):,}",
)

print(
    "Lineages with unresolved participant identity:",
    f"{int((pd.to_numeric(rq3_df['unresolved_participant_count']) > 0).sum()):,}",
)

print()
print(f"Saved: {OUTPUT_DATASET}")
print(f"Audit: {OUTPUT_AUDIT}")