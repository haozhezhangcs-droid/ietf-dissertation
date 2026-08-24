from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

SUCCESS_INPUT = PROJECT_ROOT / "outputs" / "lineage_success_status.csv"
LINEAGE_INPUT = PROJECT_ROOT / "outputs" / "lineage_dataset.csv"
HISTORY_INPUT = PROJECT_ROOT / "outputs" / "lineage_history_records.csv"

OUTPUT_FILE = PROJECT_ROOT / "outputs" / "lineage_wg_status.csv"
DOCUMENT_AUDIT_FILE = PROJECT_ROOT / "outputs" / "document_wg_audit.csv"

dt = DataTrackerExt(DTBackendArchive(str(DATABASE_PATH)))

input_file = SUCCESS_INPUT if SUCCESS_INPUT.exists() else LINEAGE_INPUT
lineage_df = pd.read_csv(input_file, dtype=str).fillna("")
history_df = pd.read_csv(HISTORY_INPUT, dtype=str).fillna("")
history_df["date_dt"] = pd.to_datetime(history_df["date"], errors="coerce")


def split_members(text: str) -> List[str]:
    return [x.strip() for x in str(text).split(";") if x.strip()]


def filename_tokens(draft_name: str) -> Set[str]:
    return {
        token for token in draft_name.lower().split("-")
        if token and token != "draft"
    }


def resolve_document_group(draft_name: str) -> dict:
    result = {
        "draft_name": draft_name,
        "document_found": 0,
        "recorded_group_name": "",
        "recorded_group_acronym": "",
        "recorded_group_type": "",
        "is_recorded_wg": 0,
        "is_individual_submissions": 0,
    }

    try:
        doc = dt.document_from_draft(draft_name)
    except Exception:
        doc = None

    if doc is None:
        return result

    result["document_found"] = 1

    if doc.group is None:
        return result

    try:
        group = dt.group(doc.group)
    except Exception:
        group = None

    if group is None:
        return result

    group_name = str(getattr(group, "name", "") or "").strip()
    group_acronym = str(getattr(group, "acronym", "") or "").strip()

    result["recorded_group_name"] = group_name
    result["recorded_group_acronym"] = group_acronym

    try:
        group_type = dt.group_type_name(group.type)
        group_type_slug = str(
            getattr(group_type, "slug", "") or ""
        ).strip().lower()
    except Exception:
        group_type_slug = ""

    result["recorded_group_type"] = group_type_slug
    result["is_recorded_wg"] = int(group_type_slug == "wg")

    group_uri = str(getattr(group, "resource_uri", "") or "").strip()

    result["is_individual_submissions"] = int(
        group_name.lower() == "individual submissions"
        or group_uri.endswith("/group/1027/")
    )

    return result


all_draft_names: Set[str] = set()
for text in lineage_df["lineage_members"]:
    all_draft_names.update(split_members(text))

document_group_info: Dict[str, dict] = {}

for index, draft_name in enumerate(sorted(all_draft_names), start=1):
    if index % 1000 == 0:
        print(f"Resolving groups: {index:,}/{len(all_draft_names):,}")

    document_group_info[draft_name] = resolve_document_group(draft_name)


wg_acronym_counts = Counter()

for info in document_group_info.values():
    if info["is_recorded_wg"] == 1:
        acronym = info["recorded_group_acronym"].lower().strip()
        if acronym:
            wg_acronym_counts[acronym] += 1

wg_acronyms = set(wg_acronym_counts)


audit_rows = []

for draft_name in sorted(all_draft_names):
    info = dict(document_group_info[draft_name])
    matches = sorted(filename_tokens(draft_name) & wg_acronyms)
    info["filename_wg_candidates"] = ";".join(matches)
    audit_rows.append(info)

pd.DataFrame(audit_rows).to_csv(DOCUMENT_AUDIT_FILE, index=False)


document_first_dates: Dict[tuple, pd.Timestamp] = {}

for (lineage_id, draft_name), group in history_df.groupby(
    ["lineage_id", "draft_name"]
):
    dates = group["date_dt"].dropna()
    if not dates.empty:
        document_first_dates[(lineage_id, draft_name)] = dates.min()


output_rows = []

for _, row in lineage_df.iterrows():
    lineage_id = row["lineage_id"]
    members = split_members(row["lineage_members"])

    recorded_wgs: Set[str] = set()
    recorded_groups: Set[str] = set()
    individual_members: List[str] = []
    no_recorded_group_members: List[str] = []

    recorded_wg_dates: List[pd.Timestamp] = []
    individual_dates: List[pd.Timestamp] = []
    wg_dates_by_acronym: Dict[str, List[pd.Timestamp]] = {}

    for draft_name in members:
        info = document_group_info[draft_name]
        group_name = info["recorded_group_name"]
        group_acronym = info["recorded_group_acronym"].lower().strip()
        first_date = document_first_dates.get((lineage_id, draft_name))

        if group_name:
            recorded_groups.add(group_name)

        if info["is_recorded_wg"] == 1:
            if group_acronym:
                recorded_wgs.add(group_acronym)

            if first_date is not None:
                recorded_wg_dates.append(first_date)
                if group_acronym:
                    wg_dates_by_acronym.setdefault(
                        group_acronym, []
                    ).append(first_date)

        elif info["is_individual_submissions"] == 1:
            individual_members.append(draft_name)
            if first_date is not None:
                individual_dates.append(first_date)

        else:
            no_recorded_group_members.append(draft_name)

    has_recorded_wg = int(bool(recorded_wgs))
    has_individual = int(bool(individual_members))

    first_individual_date = min(individual_dates) if individual_dates else None
    first_recorded_wg_date = (
        min(recorded_wg_dates) if recorded_wg_dates else None
    )

    first_recorded_wgs = []

    if first_recorded_wg_date is not None:
        for acronym, dates in wg_dates_by_acronym.items():
            if min(dates) == first_recorded_wg_date:
                first_recorded_wgs.append(acronym)

    individual_to_wg = 0
    time_to_wg_days = None

    if (
        first_individual_date is not None
        and first_recorded_wg_date is not None
        and first_individual_date < first_recorded_wg_date
    ):
        individual_to_wg = 1
        time_to_wg_days = (
            first_recorded_wg_date - first_individual_date
        ).days

    filename_candidates: Set[str] = set()

    if not recorded_wgs:
        for draft_name in members:
            filename_candidates.update(
                filename_tokens(draft_name) & wg_acronyms
            )

    if len(filename_candidates) == 0:
        filename_candidate_status = "None"
    elif len(filename_candidates) == 1:
        filename_candidate_status = "Single candidate"
    else:
        filename_candidate_status = "Ambiguous candidates"

    if individual_to_wg == 1:
        wg_classification = "Individual to Recorded WG"
    elif has_recorded_wg == 1:
        wg_classification = "Recorded WG"
    elif has_individual == 1:
        wg_classification = "Individual / no recorded WG"
    else:
        wg_classification = "No recorded WG"

    out = row.to_dict()

    out.update(
        {
            "recorded_groups": ";".join(sorted(recorded_groups)),
            "recorded_wgs": ";".join(sorted(recorded_wgs)),
            "recorded_wg_count": len(recorded_wgs),
            "has_recorded_wg": has_recorded_wg,
            "has_individual_submissions": has_individual,
            "individual_members": ";".join(sorted(individual_members)),
            "no_recorded_group_members": ";".join(
                sorted(no_recorded_group_members)
            ),
            "first_individual_date": (
                first_individual_date.date().isoformat()
                if first_individual_date is not None else ""
            ),
            "first_recorded_wg_date": (
                first_recorded_wg_date.date().isoformat()
                if first_recorded_wg_date is not None else ""
            ),
            "first_recorded_wgs": ";".join(sorted(first_recorded_wgs)),
            "individual_to_wg": individual_to_wg,
            "time_to_wg_days": time_to_wg_days,
            "filename_wg_candidates": ";".join(
                sorted(filename_candidates)
            ),
            "filename_candidate_count": len(filename_candidates),
            "filename_candidate_status": filename_candidate_status,
            "wg_classification": wg_classification,
        }
    )

    output_rows.append(out)


result_df = pd.DataFrame(output_rows)
result_df.to_csv(OUTPUT_FILE, index=False)

print()
print("=" * 72)
print("WG CLASSIFICATION SUMMARY")
print("=" * 72)
print(result_df["wg_classification"].value_counts(dropna=False))
print()
print(
    "Confirmed Individual -> Recorded WG transitions:",
    int(pd.to_numeric(
        result_df["individual_to_wg"],
        errors="coerce"
    ).fillna(0).sum())
)
print(
    "Single filename WG candidates:",
    int((result_df["filename_candidate_status"] == "Single candidate").sum())
)
print(
    "Ambiguous filename WG candidates:",
    int((result_df["filename_candidate_status"] == "Ambiguous candidates").sum())
)
print()
print(f"Saved: {OUTPUT_FILE}")
print(f"Audit: {DOCUMENT_AUDIT_FILE}")