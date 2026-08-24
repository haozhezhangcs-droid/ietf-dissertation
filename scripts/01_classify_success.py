from __future__ import annotations

from pathlib import Path
import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive
from ietfdata.rfcindex import RFCIndex


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
RFC_INDEX_PATH = PROJECT_ROOT / "data" / "rfc-index.xml"

INPUT_LINEAGES = PROJECT_ROOT / "outputs" / "lineage_dataset.csv"
OUTPUT_CLASSIFIED = PROJECT_ROOT / "outputs" / "lineage_success_status.csv"


# ============================================================
# 2. Initialise supervisor-provided library
# ============================================================

dt = DataTrackerExt(
    DTBackendArchive(str(DATABASE_PATH))
)

ri = RFCIndex(
    rfc_index=str(RFC_INDEX_PATH)
)


# ============================================================
# 3. Load reconstructed lineage dataset
# ============================================================

lineage_df = pd.read_csv(
    INPUT_LINEAGES,
    dtype=str
)

# Convert selected numeric fields back to numbers where needed.
if "has_rfc" in lineage_df.columns:
    lineage_df["has_rfc"] = pd.to_numeric(
        lineage_df["has_rfc"],
        errors="coerce"
    ).fillna(0).astype(int)


# ============================================================
# 4. Build authoritative RFC -> lineage evidence
#
# Successful means:
#   at least one published RFC can be mapped to this reconstructed
#   lineage using RFCIndex + DataTrackerExt.draft_history_for_rfc().
#
# This does NOT classify no-RFC lineages as Unsuccessful.
# ============================================================

successful_lineage_ids = set()
success_evidence = {}


# We can use the already-generated rfc_history_map.csv if available.
RFC_MAP = PROJECT_ROOT / "outputs" / "rfc_history_map.csv"

if RFC_MAP.exists():
    rfc_map_df = pd.read_csv(
        RFC_MAP,
        dtype=str
    )

    for _, row in rfc_map_df.iterrows():
        lineage_id = str(row.get("lineage_id", "")).strip()
        rfc_name = str(row.get("rfc_name", "")).strip()
        final_draft = str(row.get("final_draft", "")).strip()

        if not lineage_id:
            continue

        successful_lineage_ids.add(lineage_id)

        success_evidence.setdefault(
            lineage_id,
            {
                "rfc_names": [],
                "final_drafts": [],
            }
        )

        if rfc_name:
            success_evidence[lineage_id]["rfc_names"].append(rfc_name)

        if final_draft:
            success_evidence[lineage_id]["final_drafts"].append(final_draft)

else:
    # Fallback: reconstruct directly from RFCIndex + draft_history_for_rfc().
    # This is slower but uses the supervisor library directly.
    member_to_lineage = {}

    for _, row in lineage_df.iterrows():
        lineage_id = str(row["lineage_id"]).strip()

        members = [
            x.strip()
            for x in str(row["lineage_members"]).split(";")
            if x.strip()
        ]

        for member in members:
            member_to_lineage[member] = lineage_id

    for index, rfc in enumerate(ri.rfcs(), start=1):

        if index % 500 == 0:
            print(f"RFCs processed: {index:,}")

        try:
            history = dt.draft_history_for_rfc(rfc)
        except Exception as exc:
            print(
                f"WARNING: could not reconstruct {rfc.doc_id}: {exc}"
            )
            continue

        if not history:
            continue

        history_members = {
            h.draft.name
            for h in history
        }

        matched_lineage_ids = {
            member_to_lineage[name]
            for name in history_members
            if name in member_to_lineage
        }

        for lineage_id in matched_lineage_ids:
            successful_lineage_ids.add(lineage_id)

            success_evidence.setdefault(
                lineage_id,
                {
                    "rfc_names": [],
                    "final_drafts": [],
                }
            )

            success_evidence[lineage_id]["rfc_names"].append(
                str(rfc.doc_id)
            )

            if rfc.draft:
                success_evidence[lineage_id]["final_drafts"].append(
                    str(rfc.draft)
                )


# ============================================================
# 5. Classify ONLY success status
#
# Important:
#   Successful   = RFC evidence exists
#   Not published = no RFC evidence found
#
# "Not published" is deliberately NOT called "Unsuccessful".
# A no-RFC lineage may still be ongoing, withdrawn, expired,
# ambiguous, etc. That requires a separate outcome-classification step.
# ============================================================

rows = []

for _, row in lineage_df.iterrows():
    lineage_id = str(row["lineage_id"]).strip()

    evidence = success_evidence.get(
        lineage_id,
        {
            "rfc_names": [],
            "final_drafts": [],
        }
    )

    rfc_names = sorted(set(evidence["rfc_names"]))
    final_drafts = sorted(set(evidence["final_drafts"]))

    if lineage_id in successful_lineage_ids:
        publication_status = "Successful"
        publication_success = 1
        success_reason = (
            "RFCIndex + DataTrackerExt.draft_history_for_rfc"
        )
    else:
        publication_status = "Not published"
        publication_success = 0
        success_reason = "No mapped published RFC"

    output_row = row.to_dict()

    output_row.update(
        {
            "publication_success": publication_success,
            "publication_status": publication_status,
            "success_reason": success_reason,
            "success_rfc_names": ";".join(rfc_names),
            "success_final_drafts": ";".join(final_drafts),
        }
    )

    rows.append(output_row)


result_df = pd.DataFrame(rows)

result_df.to_csv(
    OUTPUT_CLASSIFIED,
    index=False
)


# ============================================================
# 6. Summary
# ============================================================

successful_n = int(
    (result_df["publication_success"] == 1).sum()
)

not_published_n = int(
    (result_df["publication_success"] == 0).sum()
)

print()
print("=" * 72)
print("PUBLICATION SUCCESS SUMMARY")
print("=" * 72)

print(f"Successful lineages:   {successful_n:,}")
print(f"Not published:         {not_published_n:,}")

print()
print(f"Saved: {OUTPUT_CLASSIFIED}")

print()
print(
    "NOTE: 'Not published' is not yet equivalent to 'Unsuccessful'."
)
print(
    "Unsuccessful/Ongoing/Unknown will be classified separately."
)