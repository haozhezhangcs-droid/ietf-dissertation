from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt, DraftHistory
from ietfdata.dt_backend import DTBackendArchive
from ietfdata.rfcindex import RFCIndex


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
RFC_INDEX_PATH = PROJECT_ROOT / "data" / "rfc-index.xml"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_OUTPUT = OUTPUT_DIR / "lineage_history_records.csv"
RFC_OUTPUT = OUTPUT_DIR / "rfc_history_map.csv"
LINEAGE_OUTPUT = OUTPUT_DIR / "lineage_dataset.csv"


# ============================================================
# 2. Initialise supervisor-provided ietfdata library
# ============================================================

dt = DataTrackerExt(
    DTBackendArchive(str(DATABASE_PATH))
)

ri = RFCIndex(
    rfc_index=str(RFC_INDEX_PATH)
)


# ============================================================
# 3. Union-Find
#
# draft_history() is backwards-looking.
# If one returned history contains A, B, C, those draft documents
# are part of the same connected development lineage.
# Union-Find merges overlapping histories into one component.
# ============================================================

class UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def add(self, item: str) -> None:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0

    def find(self, item: str) -> str:
        self.add(item)

        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])

        return self.parent[item]

    def union(self, a: str, b: str) -> None:
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a

        self.parent[root_b] = root_a

        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1


uf = UnionFind()


# ============================================================
# 4. Helper functions
# ============================================================

def unique_history(history: List[DraftHistory]) -> List[DraftHistory]:
    """
    Keep one record for each distinct (draft_name, revision).

    draft_history() combines revision-event and submission evidence.
    If duplicate observations exist, prefer the one with a Submission.
    """

    records: Dict[Tuple[str, str], DraftHistory] = {}

    for h in history:
        key = (h.draft.name, h.rev)

        if key not in records:
            records[key] = h
            continue

        current = records[key]

        if current.submission is None and h.submission is not None:
            records[key] = h

    # The supervisor library returns history newest-first.
    # For our derived datasets, store it oldest-first.
    return sorted(
        records.values(),
        key=lambda h: (h.date, h.draft.name, h.rev),
    )


def final_draft_name_from_rfc_index(final_draft: str) -> str:
    """
    RFC Index normally stores the final revision, e.g.
        draft-ietf-quic-transport-34
    Convert that to the logical Document name:
        draft-ietf-quic-transport
    """

    if not final_draft:
        return ""

    head, sep, tail = final_draft.rpartition("-")

    if sep and len(tail) == 2 and tail.isdigit():
        return head

    return final_draft


def safe_rfc_date(rfc) -> str:
    """
    Return RFCIndex date as ISO text.
    Historical RFC Index records may only have month precision;
    RFCIndex represents those using day 1.
    """

    try:
        value = rfc.date()
        if value is None:
            return ""
        return value.date().isoformat()
    except Exception:
        return ""


# ============================================================
# 5. Load all Internet-Draft Documents
# ============================================================

draft_type = dt.document_type_from_slug("draft")

draft_documents = list(
    dt.documents(doctype=draft_type)
)

documents_by_name = {
    doc.name: doc
    for doc in draft_documents
}

print()
print("=" * 72)
print("STEP 1: INTERNET-DRAFT DOCUMENTS")
print("=" * 72)
print(f"Documents found: {len(draft_documents):,}")


# ============================================================
# 6. Reconstruct histories for all drafts
#
# IMPORTANT:
# Pass drafts_seen=[] explicitly for every top-level draft_history()
# call. The current supervisor library has a mutable default argument
# in draft_history(); explicitly providing a new list keeps each
# independent query isolated without changing the library source.
# ============================================================

history_cache: Dict[str, List[DraftHistory]] = {}

# Raw observations are held in memory first. We do NOT save
# query_draft in the final history dataset because the same historical
# revision can be returned when querying several descendant drafts.
raw_history_records: List[dict] = []


for index, doc in enumerate(draft_documents, start=1):

    if index % 500 == 0:
        print(
            f"draft_history: {index:,}/{len(draft_documents):,}"
        )

    uf.add(doc.name)

    try:
        history = dt.draft_history(
            doc,
            drafts_seen=[],
        )
    except Exception as exc:
        print(
            f"WARNING: draft_history failed for "
            f"{doc.name}: {exc}"
        )
        history = []

    history = unique_history(history)
    history_cache[doc.name] = history

    members: Set[str] = {doc.name}

    for h in history:
        members.add(h.draft.name)

        raw_history_records.append(
            {
                "query_draft": doc.name,
                "draft_name": h.draft.name,
                "revision": h.rev,
                "date": h.date.isoformat(),
                "has_submission": int(
                    h.submission is not None
                ),
            }
        )

    # Merge all distinct Documents found in this reconstructed history.
    members_sorted = sorted(members)

    if members_sorted:
        base = members_sorted[0]

        for member in members_sorted:
            uf.union(base, member)


# ============================================================
# 7. Use RFCIndex + DataTrackerExt.draft_history_for_rfc()
#
# This identifies histories with a published RFC.
#
# NOTE:
# draft_history_for_rfc() in the current supervisor library internally
# calls draft_history() without exposing drafts_seen. If your local
# datatracker_ext.py still has:
#
#     drafts_seen: List[Document] = []
#
# change ONLY that implementation detail to a None default, or retain
# the small fix already made locally. Do not change its reconstruction
# algorithm.
# ============================================================

print()
print("=" * 72)
print("STEP 2: RFC HISTORIES")
print("=" * 72)

rfc_records: List[dict] = []


for index, rfc in enumerate(ri.rfcs(), start=1):

    if index % 500 == 0:
        print(f"RFCs processed: {index:,}")

    try:
        history = dt.draft_history_for_rfc(rfc)
    except Exception as exc:
        print(
            f"WARNING: draft_history_for_rfc failed for "
            f"{rfc.doc_id}: {exc}"
        )
        continue

    if not history:
        continue

    history = unique_history(history)

    members = sorted({
        h.draft.name
        for h in history
    })

    if not members:
        continue

    # RFC reconstruction can reveal connections not yet merged above.
    base = members[0]

    for member in members:
        uf.union(base, member)

    final_draft = str(rfc.draft) if rfc.draft is not None else ""
    final_draft_name = final_draft_name_from_rfc_index(final_draft)

    rfc_records.append(
        {
            "rfc_name": str(rfc.doc_id),
            "rfc_date": safe_rfc_date(rfc),
            "rfc_stream": str(rfc.stream) if rfc.stream is not None else "",
            "rfc_wg": str(rfc.wg) if rfc.wg is not None else "",
            "rfc_area": str(rfc.area) if rfc.area is not None else "",

            # Specific final revision recorded in RFC Index, if available.
            "final_draft": final_draft,

            # Logical Document name without -NN revision.
            "final_draft_name": final_draft_name,

            # All distinct draft Documents returned by
            # draft_history_for_rfc().
            "draft_members": ";".join(members),

            # Temporary helper used after lineage IDs are assigned.
            "_anchor_draft": members[0],
        }
    )


# ============================================================
# 8. Build final connected lineage components
# ============================================================

components: Dict[str, Set[str]] = defaultdict(set)

for draft_name in list(uf.parent):
    root = uf.find(draft_name)
    components[root].add(draft_name)


sorted_components = sorted(
    components.values(),
    key=lambda members: sorted(members)[0],
)

lineage_id_for_draft: Dict[str, str] = {}

for number, members in enumerate(
    sorted_components,
    start=1,
):
    # 000001, 000002, ... is only zero-padding for stable sorting.
    lineage_id = f"lineage_{number:06d}"

    for member in members:
        lineage_id_for_draft[member] = lineage_id


print()
print("=" * 72)
print("STEP 3: LINEAGE COMPONENTS")
print("=" * 72)
print(f"Lineages reconstructed: {len(sorted_components):,}")


# ============================================================
# 9. Create the FINAL deduplicated revision-level history dataset
#
# The old design included query_draft, which meant the same historical
# revision could occur several times:
#
#   query B -> A-00
#   query C -> A-00
#
# The formal RQ dataset must contain only one row per:
#
#   (lineage_id, draft_name, revision)
# ============================================================

history_df = pd.DataFrame(raw_history_records)

if history_df.empty:
    history_df = pd.DataFrame(
        columns=[
            "lineage_id",
            "draft_name",
            "revision",
            "date",
            "has_submission",
        ]
    )
else:
    history_df["lineage_id"] = (
        history_df["draft_name"]
        .map(lineage_id_for_draft)
    )

    # Prefer a duplicate record that has an attached Submission.
    history_df = history_df.sort_values(
        [
            "lineage_id",
            "draft_name",
            "revision",
            "has_submission",
            "date",
        ],
        ascending=[
            True,
            True,
            True,
            False,
            True,
        ],
    )

    history_df = history_df.drop_duplicates(
        subset=[
            "lineage_id",
            "draft_name",
            "revision",
        ],
        keep="first",
    )

    # Store histories in chronological order for readability.
    history_df["date_sort"] = pd.to_datetime(
        history_df["date"],
        errors="coerce",
    )

    history_df = history_df.sort_values(
        [
            "lineage_id",
            "date_sort",
            "draft_name",
            "revision",
        ]
    )

    # query_draft deliberately disappears here.
    history_df = history_df[
        [
            "lineage_id",
            "draft_name",
            "revision",
            "date",
            "has_submission",
        ]
    ]


history_df.to_csv(
    HISTORY_OUTPUT,
    index=False,
)


# ============================================================
# 10. Add lineage_id to RFC mapping
# ============================================================

for row in rfc_records:
    anchor = row.pop("_anchor_draft")

    row["lineage_id"] = (
        lineage_id_for_draft.get(
            anchor,
            "",
        )
    )


rfc_df = pd.DataFrame(rfc_records)

if not rfc_df.empty:
    rfc_df = rfc_df[
        [
            "rfc_name",
            "rfc_date",
            "rfc_stream",
            "rfc_wg",
            "rfc_area",
            "lineage_id",
            "final_draft",
            "final_draft_name",
            "draft_members",
        ]
    ]

    rfc_df = rfc_df.sort_values(
        [
            "lineage_id",
            "rfc_name",
        ]
    )


rfc_df.to_csv(
    RFC_OUTPUT,
    index=False,
)


# ============================================================
# 11. Build one-row-per-lineage dataset
#
# This replaces the old lineage_membership.csv as the main lineage
# table. It combines membership + RQ1 development characteristics
# + RFC evidence.
#
# We deliberately do NOT label non-RFC lineages "Unsuccessful" yet.
# That classification will be handled separately after the outcome
# definition is redesigned.
# ============================================================

history_groups = {
    lineage_id: group.copy()
    for lineage_id, group in history_df.groupby(
        "lineage_id",
        dropna=False,
    )
}

rfc_groups = {}

if not rfc_df.empty:
    rfc_groups = {
        lineage_id: group.copy()
        for lineage_id, group in rfc_df.groupby(
            "lineage_id",
            dropna=False,
        )
    }


lineage_rows: List[dict] = []


for number, members_set in enumerate(
    sorted_components,
    start=1,
):
    lineage_id = f"lineage_{number:06d}"
    members = sorted(members_set)

    history_group = history_groups.get(lineage_id)

    if history_group is not None and not history_group.empty:
        dates = pd.to_datetime(
            history_group["date"],
            errors="coerce",
        ).dropna()

        revision_count = len(history_group)

        if not dates.empty:
            first_date = dates.min()
            last_date = dates.max()

            development_duration_days = (
                last_date - first_date
            ).days

            first_history_date = (
                first_date.date().isoformat()
            )

            last_history_date = (
                last_date.date().isoformat()
            )

            development_duration_years = (
                development_duration_days
                / 365.25
            )
        else:
            first_history_date = ""
            last_history_date = ""
            development_duration_days = None
            development_duration_years = None
    else:
        revision_count = 0
        first_history_date = ""
        last_history_date = ""
        development_duration_days = None
        development_duration_years = None

    rfc_group = rfc_groups.get(lineage_id)

    if rfc_group is not None and not rfc_group.empty:

        rfc_names = sorted({
            value
            for value in rfc_group["rfc_name"].astype(str)
            if value
        })

        final_drafts = sorted({
            value
            for value in rfc_group["final_draft"].astype(str)
            if value
        })

        final_draft_names = sorted({
            value
            for value in rfc_group["final_draft_name"].astype(str)
            if value
        })

        has_rfc = 1
        rfc_count = len(rfc_names)

    else:
        rfc_names = []
        final_drafts = []
        final_draft_names = []
        has_rfc = 0
        rfc_count = 0

    lineage_rows.append(
        {
            "lineage_id": lineage_id,

            # All distinct Documents in the connected history.
            "lineage_members": ";".join(members),

            # Number of distinct draft Document names.
            "lineage_length": len(members),

            # Number of unique (draft_name, revision) records.
            "lineage_revision_count": revision_count,

            "first_history_date": first_history_date,
            "last_history_date": last_history_date,

            # Development characteristic only.
            # NOT used here as a failure threshold.
            "development_duration_days": development_duration_days,
            "development_duration_years": development_duration_years,

            # Published-RFC evidence.
            "has_rfc": has_rfc,
            "rfc_count": rfc_count,
            "rfc_names": ";".join(rfc_names),

            # Can be multiple if one connected lineage/component maps
            # to more than one RFC.
            "final_drafts": ";".join(final_drafts),
            "final_draft_names": ";".join(final_draft_names),
        }
    )


lineage_df = pd.DataFrame(lineage_rows)

lineage_df = lineage_df.sort_values(
    "lineage_id"
)

lineage_df.to_csv(
    LINEAGE_OUTPUT,
    index=False,
)


# ============================================================
# 12. Validation summary
# ============================================================

print()
print("=" * 72)
print("OUTPUT")
print("=" * 72)

print(f"Saved: {HISTORY_OUTPUT}")
print(f"  unique revision records: {len(history_df):,}")

print(f"Saved: {RFC_OUTPUT}")
print(f"  RFC histories: {len(rfc_df):,}")

print(f"Saved: {LINEAGE_OUTPUT}")
print(f"  lineages: {len(lineage_df):,}")

print()
print("=" * 72)
print("RQ1 PREPARATION SUMMARY")
print("=" * 72)

print(
    "Lineages with >= 1 RFC:",
    f"{int(lineage_df['has_rfc'].sum()):,}",
)

print(
    "Lineages without RFC:",
    f"{int((lineage_df['has_rfc'] == 0).sum()):,}",
)

print(
    "Lineages with >1 draft Document:",
    f"{int((lineage_df['lineage_length'] > 1).sum()):,}",
)

print()
print("IMPORTANT:")
print(
    "No-RFC lineages are NOT labelled Unsuccessful in this script."
)
print(
    "Outcome classification will be handled in a separate step."
)