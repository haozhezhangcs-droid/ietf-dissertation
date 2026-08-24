from __future__ import annotations

from pathlib import Path
from typing import List, Set

import pandas as pd


# ============================================================
# 1. Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "outputs" / "lineage_terminal_states.csv"
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "lineage_outcomes.csv"


# ============================================================
# 2. Load data
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    dtype=str,
).fillna("")


# ============================================================
# 3. Helpers
# ============================================================

def split_states(text: str) -> List[str]:
    return [
        x.strip().lower()
        for x in str(text).split(";")
        if x.strip()
    ]


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


# ============================================================
# 4. Conservative outcome classification
#
# Priority:
#   1. Successful:
#      RFC mapping takes precedence over terminal state.
#
#   2. Ongoing:
#      No RFC, but at least one terminal branch is active.
#
#   3. Unsuccessful:
#      No RFC, and all observed terminal states are expired.
#
#   4. Unknown / Other:
#      Missing, removal, replaced, mixed rare states, etc.
# ============================================================

output_rows = []

for _, row in df.iterrows():

    publication_success = parse_int(
        row.get(
            "publication_success",
            row.get("has_rfc", "0"),
        )
    )

    terminal_states = split_states(
        row.get("terminal_state_slugs", "")
    )

    terminal_state_set: Set[str] = set(terminal_states)

    terminal_count = parse_int(
        row.get("terminal_draft_count", "0")
    )

    # 1. Published RFC evidence always wins.
    if publication_success == 1:

        publication_outcome = "Successful"
        outcome_reason = "Mapped published RFC"
        primary_comparison_sample = 1

    # 2. If any terminal branch is active, the lineage is ongoing.
    elif "active" in terminal_state_set:

        publication_outcome = "Ongoing"
        outcome_reason = (
            "No mapped RFC; at least one terminal draft is active"
        )
        primary_comparison_sample = 0

    # 3. Conservative unsuccessful definition:
    #    at least one known state and all terminal states are expired.
    elif (
        terminal_state_set
        and terminal_state_set == {"expired"}
    ):

        publication_outcome = "Unsuccessful"
        outcome_reason = (
            "No mapped RFC; all observed terminal draft states are expired"
        )
        primary_comparison_sample = 1

    # 4. Rare/unclear cases remain separate.
    else:

        publication_outcome = "Unknown / Other"

        if not terminal_state_set:
            outcome_reason = (
                "No mapped RFC; terminal state missing"
            )
        else:
            outcome_reason = (
                "No mapped RFC; terminal state is "
                + ";".join(sorted(terminal_state_set))
            )

        primary_comparison_sample = 0

    has_active_terminal = int(
        "active" in terminal_state_set
    )

    has_expired_terminal = int(
        "expired" in terminal_state_set
    )

    has_rfc_terminal_state = int(
        "rfc" in terminal_state_set
    )

    has_other_terminal_state = int(
        bool(
            terminal_state_set
            - {"active", "expired", "rfc"}
        )
    )

    multiple_terminal_drafts = int(
        terminal_count > 1
    )

    out = row.to_dict()

    out.update(
        {
            "publication_outcome": publication_outcome,
            "outcome_reason": outcome_reason,
            "primary_comparison_sample": primary_comparison_sample,
            "has_active_terminal": has_active_terminal,
            "has_expired_terminal": has_expired_terminal,
            "has_rfc_terminal_state": has_rfc_terminal_state,
            "has_other_terminal_state": has_other_terminal_state,
            "multiple_terminal_drafts": multiple_terminal_drafts,
        }
    )

    output_rows.append(out)


result_df = pd.DataFrame(output_rows)

result_df.to_csv(
    OUTPUT_FILE,
    index=False,
)


# ============================================================
# 5. Validation summary
# ============================================================

print()
print("=" * 72)
print("FINAL OUTCOME CLASSIFICATION")
print("=" * 72)

print(
    result_df["publication_outcome"]
    .value_counts(dropna=False)
)

print()

print(
    "Primary RQ1 comparison sample:",
    int(
        pd.to_numeric(
            result_df["primary_comparison_sample"],
            errors="coerce",
        ).fillna(0).sum()
    ),
)

print()

print(
    "Successful lineages whose terminal state does not contain 'rfc':",
    int(
        (
            (result_df["publication_outcome"] == "Successful")
            &
            (
                pd.to_numeric(
                    result_df["has_rfc_terminal_state"],
                    errors="coerce",
                ).fillna(0)
                == 0
            )
        ).sum()
    ),
)

print(
    "Unsuccessful lineages with multiple terminal drafts:",
    int(
        (
            (result_df["publication_outcome"] == "Unsuccessful")
            &
            (
                pd.to_numeric(
                    result_df["multiple_terminal_drafts"],
                    errors="coerce",
                ).fillna(0)
                == 1
            )
        ).sum()
    ),
)

print(
    "Ongoing lineages with multiple terminal drafts:",
    int(
        (
            (result_df["publication_outcome"] == "Ongoing")
            &
            (
                pd.to_numeric(
                    result_df["multiple_terminal_drafts"],
                    errors="coerce",
                ).fillna(0)
                == 1
            )
        ).sum()
    ),
)

print()
print(f"Saved: {OUTPUT_FILE}")

print()
print("Primary RQ1 rule:")
print("  Successful   = mapped RFC")
print("  Unsuccessful = no RFC and all terminal states expired")
print("  Ongoing      = no RFC and >=1 active terminal state")
print("  Unknown      = all other no-RFC terminal-state cases")