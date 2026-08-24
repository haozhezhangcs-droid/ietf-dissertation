from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

SUCCESS_INPUT = PROJECT_ROOT / "outputs" / "lineage_success_status.csv"
LINEAGE_INPUT = PROJECT_ROOT / "outputs" / "lineage_dataset.csv"

OUTPUT_FILE = PROJECT_ROOT / "outputs" / "lineage_wg_status.csv"
DOCUMENT_AUDIT_FILE = PROJECT_ROOT / "outputs" / "document_wg_audit.csv"


# ============================================================
# 2. Library
# ============================================================

dt = DataTrackerExt(
    DTBackendArchive(str(DATABASE_PATH))
)


# ============================================================
# 3. Load lineage data
# ============================================================

input_file = SUCCESS_INPUT if SUCCESS_INPUT.exists() else LINEAGE_INPUT

lineage_df = pd.read_csv(
    input_file,
    dtype=str,
).fillna("")


# ============================================================
# 4. Helpers
# ============================================================

def split_members(text: str) -> List[str]:
    return [
        x.strip()
        for x in str(text).split(";")
        if x.strip()
    ]


def resolve_document_group(draft_name: str) -> dict:
    """
    Read only Datatracker-recorded evidence for one draft Document.
    """

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

    group_name = str(
        getattr(group, "name", "") or ""
    ).strip()

    group_acronym = str(
        getattr(group, "acronym", "") or ""
    ).strip()

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

    if group_type_slug == "wg":
        result["is_recorded_wg"] = 1

    group_uri = str(
        getattr(group, "resource_uri", "") or ""
    ).strip()

    if (
        group_name.lower() == "individual submissions"
        or group_uri.endswith("/group/1027/")
    ):
        result["is_individual_submissions"] = 1

    return result


def filename_tokens(draft_name: str) -> Set[str]:
    """
    Exact '-' delimited filename tokens.

    Example:
      draft-rtpfolks-quic-rtp-over-quic
      -> {"rtpfolks", "quic", "rtp", "over"}
    """

    return {
        token
        for token in draft_name.lower().split("-")
        if token and token != "draft"
    }


# ============================================================
# 5. Resolve group evidence for all distinct draft Documents
# ============================================================

all_draft_names: Set[str] = set()

for members_text in lineage_df["lineage_members"]:
    all_draft_names.update(
        split_members(members_text)
    )

document_group_info: Dict[str, dict] = {}

for index, draft_name in enumerate(
    sorted(all_draft_names),
    start=1,
):
    if index % 1000 == 0:
        print(
            f"Resolving groups: {index:,}/{len(all_draft_names):,}"
        )

    document_group_info[draft_name] = (
        resolve_document_group(draft_name)
    )


# ============================================================
# 6. Learn actual WG acronyms from Datatracker evidence
# ============================================================

wg_acronym_counts = Counter()

for info in document_group_info.values():
    if info["is_recorded_wg"] != 1:
        continue

    acronym = info[
        "recorded_group_acronym"
    ].lower().strip()

    if acronym:
        wg_acronym_counts[acronym] += 1

wg_acronyms = set(
    wg_acronym_counts.keys()
)


# ============================================================
# 7. Document-level audit
# ============================================================

document_audit_rows = []

for draft_name in sorted(all_draft_names):
    info = dict(
        document_group_info[draft_name]
    )

    matches = sorted(
        filename_tokens(draft_name)
        & wg_acronyms
    )

    info["filename_wg_matches"] = ";".join(matches)

    document_audit_rows.append(info)

pd.DataFrame(
    document_audit_rows
).to_csv(
    DOCUMENT_AUDIT_FILE,
    index=False,
)


# ============================================================
# 8. Lineage-level classification
# ============================================================

output_rows = []

for _, row in lineage_df.iterrows():

    lineage_id = row["lineage_id"]
    members = split_members(
        row["lineage_members"]
    )

    recorded_wgs: Set[str] = set()
    recorded_groups: Set[str] = set()

    individual_members: List[str] = []
    no_recorded_group_members: List[str] = []

    for draft_name in members:

        info = document_group_info[
            draft_name
        ]

        group_name = info[
            "recorded_group_name"
        ]

        group_acronym = info[
            "recorded_group_acronym"
        ].lower().strip()

        if group_name:
            recorded_groups.add(group_name)

        if info["is_recorded_wg"] == 1:
            if group_acronym:
                recorded_wgs.add(
                    group_acronym
                )

        elif info[
            "is_individual_submissions"
        ] == 1:
            individual_members.append(
                draft_name
            )

        else:
            no_recorded_group_members.append(
                draft_name
            )

    has_recorded_wg = int(
        len(recorded_wgs) > 0
    )

    has_individual = int(
        len(individual_members) > 0
    )

    # Same reconstructed lineage contains both an individual document
    # and at least one document directly recorded under a WG.
    individual_and_wg_history = int(
        has_individual == 1
        and has_recorded_wg == 1
    )

    # --------------------------------------------------------
    # Inference source 1: same-lineage history
    # --------------------------------------------------------

    inferred_wgs: Set[str] = set()
    inference_sources: Set[str] = set()

    if len(recorded_wgs) == 1:
        if individual_members or no_recorded_group_members:
            inferred_wgs.add(
                next(iter(recorded_wgs))
            )
            inference_sources.add(
                "lineage_history"
            )

    # --------------------------------------------------------
    # Inference source 2: filename
    #
    # Only used if the lineage has no directly recorded WG.
    # Exact filename tokens are matched against WG acronyms that
    # actually occur in the Datatracker snapshot.
    # --------------------------------------------------------

    filename_matches: Set[str] = set()

    if not recorded_wgs:

        for draft_name in members:
            filename_matches.update(
                filename_tokens(draft_name)
                & wg_acronyms
            )

        if len(filename_matches) == 1:
            inferred_wgs.update(
                filename_matches
            )
            inference_sources.add(
                "filename"
            )

    # --------------------------------------------------------
    # Final descriptive category
    # --------------------------------------------------------

    if recorded_wgs:
        wg_classification = "Recorded WG"

    elif len(filename_matches) > 1:
        wg_classification = "Ambiguous inferred WG"

    elif inferred_wgs:
        wg_classification = "Inferred WG"

    elif individual_members:
        wg_classification = "Individual only"

    else:
        wg_classification = "No identified WG"

    out = row.to_dict()

    out.update(
        {
            "recorded_groups":
                ";".join(sorted(recorded_groups)),

            "recorded_wgs":
                ";".join(sorted(recorded_wgs)),

            "recorded_wg_count":
                len(recorded_wgs),

            "has_recorded_wg":
                has_recorded_wg,

            "has_individual_submissions":
                has_individual,

            "individual_members":
                ";".join(
                    sorted(individual_members)
                ),

            "no_recorded_group_members":
                ";".join(
                    sorted(no_recorded_group_members)
                ),

            "individual_and_wg_history":
                individual_and_wg_history,

            "inferred_wgs":
                ";".join(sorted(inferred_wgs)),

            "filename_wg_matches":
                ";".join(
                    sorted(filename_matches)
                ),

            "wg_inference_source":
                ";".join(
                    sorted(inference_sources)
                ),

            "wg_classification":
                wg_classification,
        }
    )

    output_rows.append(out)


result_df = pd.DataFrame(
    output_rows
)

result_df.to_csv(
    OUTPUT_FILE,
    index=False,
)


# ============================================================
# 9. Summary
# ============================================================

print()
print("=" * 72)
print("WG CLASSIFICATION SUMMARY")
print("=" * 72)

print(
    result_df[
        "wg_classification"
    ].value_counts(
        dropna=False
    )
)

print()
print(
    "Individual + recorded WG histories:",
    int(
        (
            pd.to_numeric(
                result_df[
                    "individual_and_wg_history"
                ],
                errors="coerce",
            ).fillna(0)
            == 1
        ).sum()
    ),
)

print()
print(f"Saved: {OUTPUT_FILE}")
print(f"Audit: {DOCUMENT_AUDIT_FILE}")

print()
print(
    "Recorded WG = direct Datatracker evidence."
)
print(
    "Inferred WG = kept separate, with inference source recorded."
)
print(
    "Individual Submissions is NOT treated as proof of no WG involvement."
)