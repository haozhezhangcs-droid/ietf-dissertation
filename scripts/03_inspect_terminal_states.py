from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import List, Set

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"

WG_INPUT = PROJECT_ROOT / "outputs" / "lineage_wg_status.csv"
SUCCESS_INPUT = PROJECT_ROOT / "outputs" / "lineage_success_status.csv"
LINEAGE_INPUT = PROJECT_ROOT / "outputs" / "lineage_dataset.csv"

OUTPUT_LINEAGES = PROJECT_ROOT / "outputs" / "lineage_terminal_states.csv"
OUTPUT_STATES = PROJECT_ROOT / "outputs" / "draft_state_summary.csv"
OUTPUT_TERMINALS = PROJECT_ROOT / "outputs" / "terminal_draft_audit.csv"

dt = DataTrackerExt(DTBackendArchive(str(DATABASE_PATH)))

if WG_INPUT.exists():
    input_file = WG_INPUT
elif SUCCESS_INPUT.exists():
    input_file = SUCCESS_INPUT
else:
    input_file = LINEAGE_INPUT

lineage_df = pd.read_csv(input_file, dtype=str).fillna("")


def split_members(text: str) -> List[str]:
    return [x.strip() for x in str(text).split(";") if x.strip()]


def get_document(draft_name: str):
    try:
        return dt.document_from_draft(draft_name)
    except Exception:
        return None


def get_draft_states(doc) -> List[dict]:
    rows = []

    if doc is None:
        return rows

    for state_uri in doc.states:
        try:
            state = dt.document_state(state_uri)
        except Exception:
            continue

        if state is None:
            continue

        try:
            state_type = dt.document_state_type(state.type)
        except Exception:
            state_type = None

        state_type_slug = str(
            getattr(state_type, "slug", "") or ""
        ).strip()

        if state_type_slug != "draft":
            continue

        rows.append(
            {
                "slug": str(getattr(state, "slug", "") or "").strip(),
                "name": str(getattr(state, "name", "") or "").strip(),
                "uri": str(
                    getattr(state, "resource_uri", "") or ""
                ).strip(),
            }
        )

    return rows


def related_successors_within_lineage(
    draft_name: str,
    lineage_members: Set[str],
) -> Set[str]:
    doc = get_document(draft_name)

    if doc is None:
        return set()

    successors: Set[str] = set()

    try:
        relations = dt.related_documents(
            target=doc,
            relationship_type_slug="replaces",
        )
    except Exception:
        return successors

    for rel in relations:
        try:
            newer_doc = dt.document(rel.source)
        except Exception:
            newer_doc = None

        if newer_doc is not None and newer_doc.name in lineage_members:
            successors.add(newer_doc.name)

    return successors


state_definition_rows = []

try:
    draft_state_type = dt.document_state_type_from_slug("draft")

    for state in dt.document_states(state_type=draft_state_type):
        state_definition_rows.append(
            {
                "state_slug": str(
                    getattr(state, "slug", "") or ""
                ).strip(),
                "state_name": str(
                    getattr(state, "name", "") or ""
                ).strip(),
                "state_uri": str(
                    getattr(state, "resource_uri", "") or ""
                ).strip(),
            }
        )
except Exception as exc:
    print(
        f"WARNING: could not enumerate draft state definitions: {exc}"
    )

pd.DataFrame(state_definition_rows).to_csv(
    OUTPUT_STATES,
    index=False,
)


terminal_audit_rows = []
lineage_output_rows = []
terminal_state_counts = Counter()

for index, row in lineage_df.iterrows():

    if (index + 1) % 500 == 0:
        print(
            f"Inspecting terminal states: "
            f"{index + 1:,}/{len(lineage_df):,}"
        )

    lineage_id = row["lineage_id"]
    members_list = split_members(row["lineage_members"])
    members = set(members_list)

    terminal_drafts: List[str] = []

    for draft_name in members_list:
        successors = related_successors_within_lineage(
            draft_name,
            members,
        )

        if not successors:
            terminal_drafts.append(draft_name)

    terminal_resolution = "Structural replaces relation"

    if not terminal_drafts:
        terminal_drafts = members_list.copy()
        terminal_resolution = "Unresolved - no structural terminal found"

    lineage_state_slugs: Set[str] = set()
    lineage_state_names: Set[str] = set()

    for terminal_draft in sorted(terminal_drafts):
        doc = get_document(terminal_draft)
        states = get_draft_states(doc)

        state_slugs = sorted({
            s["slug"] for s in states if s["slug"]
        })

        state_names = sorted({
            s["name"] for s in states if s["name"]
        })

        for slug in state_slugs:
            terminal_state_counts[slug] += 1
            lineage_state_slugs.add(slug)

        for name in state_names:
            lineage_state_names.add(name)

        changed_state_events = []

        if doc is not None:
            try:
                for event in dt.document_events(
                    doc=doc,
                    event_type="changed_state",
                ):
                    changed_state_events.append(
                        (
                            event.time.isoformat(),
                            str(event.desc or ""),
                        )
                    )
            except Exception:
                pass

        changed_state_events.sort(key=lambda x: x[0])

        last_state_event_time = ""
        last_state_event_desc = ""

        if changed_state_events:
            last_state_event_time, last_state_event_desc = (
                changed_state_events[-1]
            )

        terminal_audit_rows.append(
            {
                "lineage_id": lineage_id,
                "terminal_draft": terminal_draft,
                "terminal_state_slugs": ";".join(state_slugs),
                "terminal_state_names": ";".join(state_names),
                "last_changed_state_time": last_state_event_time,
                "last_changed_state_desc": last_state_event_desc,
                "terminal_resolution": terminal_resolution,
            }
        )

    publication_success = str(
        row.get("publication_success", "")
    ).strip()

    has_rfc = str(
        row.get("has_rfc", "")
    ).strip()

    if publication_success == "1" or has_rfc == "1":
        provisional_outcome = "Successful"
        provisional_reason = "Mapped published RFC"
    else:
        provisional_outcome = "Not published - inspect terminal state"
        provisional_reason = (
            "No RFC; terminal state retained for classification"
        )

    out = row.to_dict()

    out.update(
        {
            "terminal_drafts": ";".join(sorted(terminal_drafts)),
            "terminal_draft_count": len(terminal_drafts),
            "terminal_state_slugs": ";".join(
                sorted(lineage_state_slugs)
            ),
            "terminal_state_names": ";".join(
                sorted(lineage_state_names)
            ),
            "terminal_resolution": terminal_resolution,
            "provisional_outcome": provisional_outcome,
            "provisional_outcome_reason": provisional_reason,
        }
    )

    lineage_output_rows.append(out)


pd.DataFrame(terminal_audit_rows).to_csv(
    OUTPUT_TERMINALS,
    index=False,
)

result_df = pd.DataFrame(lineage_output_rows)
result_df.to_csv(OUTPUT_LINEAGES, index=False)

print()
print("=" * 72)
print("TERMINAL DRAFT STATE SUMMARY")
print("=" * 72)

for slug, count in terminal_state_counts.most_common():
    print(f"{slug:25} {count:8,}")

print()
print(
    "Lineages with multiple terminal drafts:",
    int(
        (
            pd.to_numeric(
                result_df["terminal_draft_count"],
                errors="coerce",
            ).fillna(0)
            > 1
        ).sum()
    ),
)

print()
print(f"Saved state definitions: {OUTPUT_STATES}")
print(f"Saved terminal audit:    {OUTPUT_TERMINALS}")
print(f"Saved lineage states:    {OUTPUT_LINEAGES}")
print()
print(
    "IMPORTANT: No-RFC lineages are not automatically labelled "
    "Unsuccessful. Use the actual terminal-state vocabulary printed "
    "above to define the final rule."
)