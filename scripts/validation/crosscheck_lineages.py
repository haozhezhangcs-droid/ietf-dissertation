from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import pandas as pd

from ietfdata.datatracker_ext import DataTrackerExt
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = PROJECT_ROOT / "data" / "ietfdata-dt.sqlite"
LINEAGE_FILE = PROJECT_ROOT / "outputs" / "intermediate" / "lineage_dataset.csv"
HISTORY_FILE = PROJECT_ROOT / "outputs" / "common" / "lineage_history_records.csv"

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "validation" / "lineage_crosscheck_simple"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NAME_CANDIDATE_FILE = OUTPUT_DIR / "01_exact_name_candidates.csv"
CHRONOLOGY_FILE = OUTPUT_DIR / "02_chronology_candidates.csv"
AUTHOR_SUPPORTED_FILE = OUTPUT_DIR / "03_author_supported_candidates.csv"
SUMMARY_FILE = OUTPUT_DIR / "crosscheck_summary.csv"
ALL_EXACT_MATCHES_FILE = OUTPUT_DIR / "00_all_exact_matches_audit.csv"


# ============================================================
# 2. Initialise ietfdata
# ============================================================

print()
print("=" * 72)
print("INITIALISING IETFDATA")
print("=" * 72)

dt = DataTrackerExt(DTBackendArchive(str(DATABASE_PATH)))
print(f"Datatracker snapshot: {DATABASE_PATH}")


# ============================================================
# 3. Load data
# ============================================================

lineage_df = pd.read_csv(LINEAGE_FILE, dtype=str).fillna("")
history_df = pd.read_csv(HISTORY_FILE, dtype=str).fillna("")

print(f"Lineages: {len(lineage_df):,}")
print(f"History records: {len(history_df):,}")


# ============================================================
# 4. Helper functions
# ============================================================

def is_wg_style_draft(draft_name: str) -> bool:
    return draft_name.startswith("draft-ietf-")


def parse_wg_draft(draft_name: str) -> tuple[str, str] | None:
    if not is_wg_style_draft(draft_name):
        return None

    parts = draft_name.split("-")
    if len(parts) < 4:
        return None

    wg = parts[2].lower().strip()
    topic = "-".join(parts[3:]).lower().strip()

    if not wg or not topic:
        return None

    return wg, topic


def individual_topic_after_first_component(draft_name: str) -> str:
    if not draft_name.startswith("draft-") or is_wg_style_draft(draft_name):
        return ""

    parts = draft_name.split("-")
    if len(parts) < 3:
        return ""

    return "-".join(parts[2:]).lower().strip()


def structural_individual_keys(
    draft_name: str,
    known_wgs: Set[str],
) -> Set[tuple[str, str]]:
    if not draft_name.startswith("draft-") or is_wg_style_draft(draft_name):
        return set()

    body_tokens = draft_name[len("draft-"):].lower().split("-")
    results: Set[tuple[str, str]] = set()

    for index in range(1, len(body_tokens) - 1):
        possible_wg = body_tokens[index]

        if possible_wg not in known_wgs:
            continue

        topic = "-".join(body_tokens[index + 1:]).strip()

        if topic:
            results.add((possible_wg, topic))

    return results


def revision_number(value) -> int | None:
    text = str(value).strip()

    if not text:
        return None

    if text.startswith("-"):
        text = text[1:]

    if text.isdigit():
        return int(text)

    return None


def uri_text(value) -> str:
    if value is None:
        return ""

    uri = getattr(value, "uri", None)
    if uri:
        return str(uri)

    return str(value)


def person_id_from_author(author) -> str:
    person_text = uri_text(getattr(author, "person", None))

    if person_text:
        return person_text

    return uri_text(getattr(author, "email", None))


# ============================================================
# 5. Build draft -> lineage mapping
# ============================================================

draft_to_lineage: Dict[str, str] = {}

for _, row in history_df.iterrows():
    draft_name = row["draft_name"]
    lineage_id = row["lineage_id"]

    if draft_name:
        draft_to_lineage[draft_name] = lineage_id

all_drafts = sorted(draft_to_lineage)

individual_drafts = [
    name for name in all_drafts
    if not is_wg_style_draft(name)
]

wg_drafts = [
    name for name in all_drafts
    if is_wg_style_draft(name)
]

print(f"Draft documents: {len(all_drafts):,}")
print(f"Individual/non-WG-style drafts: {len(individual_drafts):,}")
print(f"WG-style drafts: {len(wg_drafts):,}")


# ============================================================
# 6. Build first/last dates and WG revision 00 dates
# ============================================================

history_df["date_parsed"] = pd.to_datetime(
    history_df["date"],
    errors="coerce",
    utc=True,
)

history_df["revision_number"] = history_df["revision"].map(revision_number)

valid_history = history_df.dropna(subset=["date_parsed"]).copy()

draft_first_date = (
    valid_history
    .groupby("draft_name")["date_parsed"]
    .min()
    .to_dict()
)

draft_last_date = (
    valid_history
    .groupby("draft_name")["date_parsed"]
    .max()
    .to_dict()
)

last_revision_rows = (
    valid_history
    .sort_values(["draft_name", "date_parsed", "revision_number"])
    .groupby("draft_name", as_index=False)
    .tail(1)
)

draft_last_revision = dict(
    zip(
        last_revision_rows["draft_name"],
        last_revision_rows["revision"],
    )
)

wg00_rows = valid_history[
    valid_history["revision_number"] == 0
]

wg_revision_00_date = (
    wg00_rows
    .groupby("draft_name")["date_parsed"]
    .min()
    .to_dict()
)


# ============================================================
# 7. Build exact WG-name indexes
# ============================================================

wg_by_wg_topic: Dict[tuple[str, str], List[str]] = defaultdict(list)
wg_by_topic: Dict[str, List[str]] = defaultdict(list)

known_wgs: Set[str] = set()
wg_topic_lookup: Dict[str, tuple[str, str]] = {}

for wg_name in wg_drafts:
    parsed = parse_wg_draft(wg_name)

    if parsed is None:
        continue

    wg, topic = parsed

    known_wgs.add(wg)
    wg_topic_lookup[wg_name] = (wg, topic)
    wg_by_wg_topic[(wg, topic)].append(wg_name)
    wg_by_topic[topic].append(wg_name)

print(f"Distinct WG slugs: {len(known_wgs):,}")
print(f"Distinct WG/topic keys: {len(wg_by_wg_topic):,}")
print(f"Distinct topic suffixes: {len(wg_by_topic):,}")


# ============================================================
# 8. Stage 1: exact name matching only
# ============================================================

print()
print("=" * 72)
print("STAGE 1: EXACT NAME MATCHING")
print("=" * 72)

pair_rules: Dict[tuple[str, str], Set[str]] = defaultdict(set)
pair_topics: Dict[tuple[str, str], Set[str]] = defaultdict(set)
pair_wgs: Dict[tuple[str, str], Set[str]] = defaultdict(set)

for individual_name in individual_drafts:

    # Rule A:
    # draft-<author>-<wg>-<topic>
    # draft-ietf-<wg>-<topic>
    for wg, topic in structural_individual_keys(
        individual_name,
        known_wgs,
    ):
        for wg_name in wg_by_wg_topic.get((wg, topic), []):
            pair = (individual_name, wg_name)

            pair_rules[pair].add("exact_author_wg_topic")
            pair_topics[pair].add(topic)
            pair_wgs[pair].add(wg)

    # Rule B:
    # draft-<author>-<topic>
    # draft-ietf-<wg>-<topic>
    topic = individual_topic_after_first_component(individual_name)

    if topic:
        for wg_name in wg_by_topic.get(topic, []):
            wg, wg_topic = wg_topic_lookup[wg_name]

            pair = (individual_name, wg_name)

            pair_rules[pair].add("exact_topic_suffix")
            pair_topics[pair].add(wg_topic)
            pair_wgs[pair].add(wg)


all_exact_rows = []

for (individual_name, wg_name), rules in pair_rules.items():
    individual_lineage = draft_to_lineage[individual_name]
    wg_lineage = draft_to_lineage[wg_name]

    individual_first = draft_first_date.get(individual_name)
    individual_last = draft_last_date.get(individual_name)
    wg_first = draft_first_date.get(wg_name)
    wg00_date = wg_revision_00_date.get(wg_name)

    same_lineage = int(individual_lineage == wg_lineage)

    all_exact_rows.append(
        {
            "individual_draft": individual_name,
            "individual_lineage": individual_lineage,
            "wg_draft": wg_name,
            "wg_lineage": wg_lineage,
            "same_lineage": same_lineage,
            "wg": ";".join(sorted(pair_wgs[(individual_name, wg_name)])),
            "topic": ";".join(sorted(pair_topics[(individual_name, wg_name)])),
            "match_rule": ";".join(sorted(rules)),
            "individual_first_date": (
                individual_first.isoformat()
                if individual_first is not None else ""
            ),
            "individual_last_date": (
                individual_last.isoformat()
                if individual_last is not None else ""
            ),
            "individual_last_revision": draft_last_revision.get(
                individual_name, ""
            ),
            "wg_first_date": (
                wg_first.isoformat()
                if wg_first is not None else ""
            ),
            "wg_revision_00_date": (
                wg00_date.isoformat()
                if wg00_date is not None else ""
            ),
        }
    )

all_exact_df = pd.DataFrame(all_exact_rows)

if not all_exact_df.empty:
    all_exact_df = (
        all_exact_df
        .sort_values(
            ["same_lineage", "match_rule", "wg", "topic", "individual_draft", "wg_draft"],
            ascending=[False, True, True, True, True, True],
        )
        .reset_index(drop=True)
    )

all_exact_df.to_csv(
    ALL_EXACT_MATCHES_FILE,
    index=False,
)

same_lineage_count = int((all_exact_df["same_lineage"] == 1).sum()) if not all_exact_df.empty else 0
different_lineage_count = int((all_exact_df["same_lineage"] == 0).sum()) if not all_exact_df.empty else 0

# The actual missing-link cross-check continues only with pairs
# currently split across different reconstructed lineages.
name_df = (
    all_exact_df[all_exact_df["same_lineage"] == 0]
    .drop(columns=["same_lineage"])
    .reset_index(drop=True)
)

print()
print(f"All exact-name matches: {len(all_exact_df):,}")
print(f"Already in same lineage: {same_lineage_count:,}")
print(f"Currently in different lineages: {different_lineage_count:,}")

if not name_df.empty:
    name_df = (
        name_df
        .sort_values(
            ["match_rule", "wg", "topic", "individual_draft", "wg_draft"]
        )
        .reset_index(drop=True)
    )

name_df.to_csv(NAME_CANDIDATE_FILE, index=False)

print(f"All exact-name matches: {len(all_exact_df):,}")
print(f"Already in same lineage: {same_lineage_count:,}")
print(f"Currently in different lineages: {different_lineage_count:,}")
print(f"Exact-name candidates for cross-check: {len(name_df):,}")

if not name_df.empty:
    exploded_rules = name_df.assign(
        match_rule=name_df["match_rule"].str.split(";")
    ).explode("match_rule")

    print()
    print("Candidate counts by exact rule:")
    print(exploded_rules["match_rule"].value_counts().to_string())


# ============================================================
# 9. Stage 2: chronology / nn -> 00 handoff
# ============================================================

print()
print("=" * 72)
print("STAGE 2: NN -> 00 CHRONOLOGY")
print("=" * 72)

chronology_rows = []

for _, row in name_df.iterrows():
    individual_name = row["individual_draft"]
    wg_name = row["wg_draft"]

    individual_first = draft_first_date.get(individual_name)
    individual_last = draft_last_date.get(individual_name)
    wg_first = draft_first_date.get(wg_name)
    wg00_date = wg_revision_00_date.get(wg_name)

    if (
        individual_first is None
        or individual_last is None
        or wg_first is None
        or wg00_date is None
    ):
        continue

    if individual_first >= wg_first:
        continue

    if individual_last > wg00_date:
        continue

    handoff_gap_days = (wg00_date - individual_last).days

    chronology_rows.append(
        {
            **row.to_dict(),
            "handoff_gap_days": handoff_gap_days,
            "chronology_ok": 1,
        }
    )

chronology_df = pd.DataFrame(chronology_rows)

if not chronology_df.empty:
    chronology_df = (
        chronology_df
        .sort_values(["handoff_gap_days", "match_rule", "wg", "topic"])
        .reset_index(drop=True)
    )

chronology_df.to_csv(CHRONOLOGY_FILE, index=False)

print(
    f"Chronologically plausible nn -> 00 candidates: "
    f"{len(chronology_df):,}"
)


# ============================================================
# 10. Load Datatracker draft documents
# ============================================================

draft_type = dt.document_type_from_slug("draft")

documents_by_name = {
    document.name: document
    for document in dt.documents(doctype=draft_type)
}

print(
    f"Datatracker draft Documents: "
    f"{len(documents_by_name):,}"
)


# ============================================================
# 11. Author cache
# ============================================================

author_cache: Dict[str, Set[str]] = {}


def authors_for_draft(draft_name: str) -> Set[str]:
    if draft_name in author_cache:
        return author_cache[draft_name]

    document = documents_by_name.get(draft_name)

    if document is None:
        author_cache[draft_name] = set()
        return set()

    authors: Set[str] = set()

    try:
        for author in dt.document_authors(document):
            participant = person_id_from_author(author)

            if participant:
                authors.add(participant)

    except Exception as error:
        print(
            f"WARNING: could not read authors for {draft_name}: {error}"
        )

    author_cache[draft_name] = authors
    return authors


# ============================================================
# 12. Stage 3: shared-author support
# ============================================================

print()
print("=" * 72)
print("STAGE 3: AUTHOR OVERLAP")
print("=" * 72)

author_rows = []

for index, row in chronology_df.iterrows():
    individual_name = row["individual_draft"]
    wg_name = row["wg_draft"]

    individual_authors = authors_for_draft(individual_name)
    wg_authors = authors_for_draft(wg_name)

    overlap = individual_authors & wg_authors
    union = individual_authors | wg_authors
    overlap_count = len(overlap)

    if overlap_count < 1:
        continue

    author_jaccard = (
        overlap_count / len(union)
        if union else 0.0
    )

    author_rows.append(
        {
            **row.to_dict(),
            "individual_author_count": len(individual_authors),
            "wg_author_count": len(wg_authors),
            "author_overlap_count": overlap_count,
            "author_jaccard": round(author_jaccard, 4),
            "overlapping_person_ids": ";".join(sorted(overlap)),
        }
    )

    if (index + 1) % 500 == 0:
        print(
            f"Checked {index + 1:,} / {len(chronology_df):,}"
        )

author_df = pd.DataFrame(author_rows)

if not author_df.empty:
    author_df = (
        author_df
        .sort_values(
            ["author_overlap_count", "author_jaccard", "handoff_gap_days"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )

author_df.to_csv(AUTHOR_SUPPORTED_FILE, index=False)

print(
    f"Author-supported candidates: "
    f"{len(author_df):,}"
)


# ============================================================
# 13. Summary
# ============================================================

summary_rows = [
    {"stage": "all_reconstructed_lineages", "count": len(lineage_df)},
    {"stage": "all_draft_documents", "count": len(all_drafts)},
    {"stage": "individual_non_wg_style_drafts", "count": len(individual_drafts)},
    {"stage": "wg_style_drafts", "count": len(wg_drafts)},
    {"stage": "all_exact_name_matches", "count": len(all_exact_df)},
    {"stage": "exact_matches_same_lineage", "count": same_lineage_count},
    {"stage": "exact_matches_different_lineage", "count": different_lineage_count},
    {"stage": "exact_name_candidates", "count": len(name_df)},
    {"stage": "nn_to_00_chronology_candidates", "count": len(chronology_df)},
    {"stage": "author_supported_candidates", "count": len(author_df)},
]

if not name_df.empty:
    exploded_rules = name_df.assign(
        match_rule=name_df["match_rule"].str.split(";")
    ).explode("match_rule")

    for rule, count in exploded_rules["match_rule"].value_counts().items():
        summary_rows.append(
            {"stage": f"name_rule_{rule}", "count": int(count)}
        )

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(SUMMARY_FILE, index=False)


# ============================================================
# 14. Final output
# ============================================================

print()
print("=" * 72)
print("CROSS-CHECK COMPLETE")
print("=" * 72)
print(f"All exact-name matches: {len(all_exact_df):,}")
print(f"Already in same lineage: {same_lineage_count:,}")
print(f"Currently in different lineages: {different_lineage_count:,}")
print(f"Exact-name candidates for cross-check: {len(name_df):,}")
print(
    f"Chronologically plausible nn -> 00 candidates: "
    f"{len(chronology_df):,}"
)
print(f"Author-supported candidates: {len(author_df):,}")
print()
print(f"Audit all exact matches: {ALL_EXACT_MATCHES_FILE}")
print(f"Stage 1: {NAME_CANDIDATE_FILE}")
print(f"Stage 2: {CHRONOLOGY_FILE}")
print(f"Stage 3: {AUTHOR_SUPPORTED_FILE}")
print(f"Summary: {SUMMARY_FILE}")
