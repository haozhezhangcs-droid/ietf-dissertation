import pandas as pd


INPUT_FILE = "outputs/common/lineage_history_records.csv"
OUTPUT_FILE = "outputs/validation/generic_topic_frequency.csv"


def parse_wg_draft(draft_name: str):
    """
    Example:
        draft-ietf-sidrops-rpkimaxlen

    Returns:
        wg = sidrops
        topic = rpkimaxlen
    """

    if not isinstance(draft_name, str):
        return None, None

    draft_name = draft_name.strip().lower()

    if not draft_name.startswith("draft-ietf-"):
        return None, None

    remainder = draft_name[len("draft-ietf-"):]

    parts = remainder.split("-")

    if len(parts) < 2:
        return None, None

    wg = parts[0]
    topic = "-".join(parts[1:])

    return wg, topic


# ============================================================
# Load data
# ============================================================

df = pd.read_csv(INPUT_FILE)

print(f"Rows loaded: {len(df):,}")
print("Columns:", df.columns.tolist())


# ============================================================
# Get unique draft names
# ============================================================

drafts = (
    df["draft_name"]
    .dropna()
    .astype(str)
    .drop_duplicates()
)

print(f"Unique drafts: {len(drafts):,}")


# ============================================================
# Extract WG and topic
# ============================================================

records = []

for draft_name in drafts:

    wg, topic = parse_wg_draft(draft_name)

    if wg is None or topic is None:
        continue

    records.append(
        {
            "draft_name": draft_name,
            "wg": wg,
            "topic": topic,
        }
    )


topic_df = pd.DataFrame(records)

print(f"WG drafts found: {len(topic_df):,}")


# ============================================================
# Count frequencies
# ============================================================

summary = (
    topic_df
    .groupby("topic")
    .agg(
        wg_draft_count=("draft_name", "nunique"),
        different_wg_count=("wg", "nunique"),
    )
    .reset_index()
)


summary = summary.sort_values(
    ["different_wg_count", "wg_draft_count"],
    ascending=False
)


# ============================================================
# Print top 50
# ============================================================

print("\nMost reused WG topics:")
print(
    summary.head(50).to_string(index=False)
)


# ============================================================
# Save
# ============================================================

summary.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"\nSaved to: {OUTPUT_FILE}")