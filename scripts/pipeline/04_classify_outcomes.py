from __future__ import annotations

from pathlib import Path
from typing import List, Set

import pandas as pd


# ============================================================
# 1. Paths and configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    /"intermediate"
    / "lineage_terminal_states.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "lineage_outcomes.csv"
)


# A draft expires after 6 months without a new revision.
EXPIRY_MONTHS = 6

# Historical reactivation analysis showed that approximately
# 95% of observed reactivations occurred within 16.85 months
# after expiry.
#
# We therefore use 18 months of post-expiry inactivity as the
# threshold for treating an expired lineage as likely inactive.
POST_EXPIRY_WAIT_MONTHS = 18


# ============================================================
# 2. Load data
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    dtype=str,
).fillna("")


# Convert the final observed history date to datetime.
df["last_history_date"] = pd.to_datetime(
    df["last_history_date"],
    errors="coerce",
)


# Use the latest date represented in the archive-derived
# lineage dataset as the common observation date.
OBSERVATION_DATE = df["last_history_date"].max()


if pd.isna(OBSERVATION_DATE):
    raise RuntimeError(
        "Could not determine observation date."
    )


print(
    "Observation date:",
    OBSERVATION_DATE.date(),
)


# ============================================================
# 3. Helpers
# ============================================================

def split_states(text: str) -> List[str]:
    """
    Convert a semicolon-separated terminal-state string
    into normalised lowercase state slugs.
    """

    return [
        x.strip().lower()
        for x in str(text).split(";")
        if x.strip()
    ]


def parse_int(value: str) -> int:
    """
    Safely convert values such as '1', '0', '1.0'
    to integers.
    """

    try:
        return int(float(value))

    except Exception:
        return 0


# ============================================================
# 4. Outcome classification
#
# Priority:
#
# 1. Successful
#    RFC mapping takes precedence over terminal state.
#
# 2. Ongoing
#    No RFC, but at least one terminal branch is active.
#
# 3. Unsuccessful
#    No RFC;
#    all terminal branches are expired;
#    and at least 18 months have passed since expiry.
#
# 4. Recently Expired
#    No RFC;
#    all terminal branches are expired;
#    but the 18-month post-expiry waiting period has
#    not yet elapsed.
#
# 5. Unknown/Other
#    Missing, removed, replaced, mixed rare states, etc.
# ============================================================

output_rows = []


for _, row in df.iterrows():

    # --------------------------------------------------------
    # RFC publication evidence
    # --------------------------------------------------------

    publication_success = parse_int(
        row.get(
            "publication_success",
            row.get("has_rfc", "0"),
        )
    )


    # --------------------------------------------------------
    # Terminal states
    # --------------------------------------------------------

    terminal_states = split_states(
        row.get(
            "terminal_state_slugs",
            ""
        )
    )

    terminal_state_set: Set[str] = set(
        terminal_states
    )


    terminal_count = parse_int(
        row.get(
            "terminal_draft_count",
            "0"
        )
    )


    # --------------------------------------------------------
    # Useful terminal-state indicators
    # --------------------------------------------------------

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
            - {
                "active",
                "expired",
                "rfc",
            }
        )
    )

    multiple_terminal_drafts = int(
        terminal_count > 1
    )


    # --------------------------------------------------------
    # Dates used for expiry classification
    # --------------------------------------------------------

    last_history_date = row.get(
        "last_history_date"
    )

    estimated_expiry_date = pd.NaT
    likely_dead_date = pd.NaT
    post_expiry_inactivity_days = None


    if not pd.isna(last_history_date):

        estimated_expiry_date = (
            last_history_date
            + pd.DateOffset(
                months=EXPIRY_MONTHS
            )
        )

        likely_dead_date = (
            estimated_expiry_date
            + pd.DateOffset(
                months=POST_EXPIRY_WAIT_MONTHS
            )
        )

        post_expiry_inactivity_days = (
            OBSERVATION_DATE
            - estimated_expiry_date
        ).days


    # ========================================================
    # 5. Final classification
    # ========================================================

    # --------------------------------------------------------
    # 5.1 Successful
    #
    # RFC mapping has highest priority.
    # --------------------------------------------------------

    if publication_success == 1:

        publication_outcome = "Successful"

        outcome_reason = (
            "Mapped to at least one RFC"
        )


    # --------------------------------------------------------
    # 5.2 Ongoing
    #
    # At least one structural terminal branch is active.
    # --------------------------------------------------------

    elif has_active_terminal == 1:

        publication_outcome = "Ongoing"

        outcome_reason = (
            "No RFC; at least one terminal "
            "draft is active"
        )


    # --------------------------------------------------------
    # 5.3 All terminal branches expired
    # --------------------------------------------------------

    elif (
        terminal_state_set
        and terminal_state_set == {"expired"}
    ):

        # Cannot evaluate inactivity without a date.
        if pd.isna(last_history_date):

            publication_outcome = (
                "Unknown/Other"
            )

            outcome_reason = (
                "All terminal drafts expired, "
                "but last history date is missing"
            )


        # Expired for long enough to be considered
        # likely inactive.
        elif (
            OBSERVATION_DATE
            >= likely_dead_date
        ):

            publication_outcome = (
                "Unsuccessful"
            )

            outcome_reason = (
                "No RFC; all terminal drafts "
                "expired and remained inactive "
                f"for at least "
                f"{POST_EXPIRY_WAIT_MONTHS} "
                "months after expiry"
            )


        # Expired, but still inside the empirical
        # waiting period.
        else:

            publication_outcome = (
                "Recently Expired"
            )

            outcome_reason = (
                "No RFC; all terminal drafts "
                "expired, but post-expiry "
                "inactivity is shorter than "
                f"{POST_EXPIRY_WAIT_MONTHS} months"
            )


    # --------------------------------------------------------
    # 5.4 Rare / ambiguous states
    # --------------------------------------------------------

    else:

        publication_outcome = (
            "Unknown/Other"
        )

        outcome_reason = (
            "No RFC and terminal states do not "
            "meet Successful, Ongoing, or "
            "Unsuccessful criteria"
        )


    # ========================================================
    # 6. Primary comparison sample
    #
    # Only Successful and Unsuccessful lineages are used
    # in the main RQ comparisons.
    # ========================================================

    primary_comparison_sample = int(
        publication_outcome
        in {
            "Successful",
            "Unsuccessful",
        }
    )


    # ========================================================
    # 7. Save output row
    # ========================================================

    out = row.to_dict()

    out.update(
        {
            "publication_outcome":
                publication_outcome,

            "outcome_reason":
                outcome_reason,

            "primary_comparison_sample":
                primary_comparison_sample,

            "has_active_terminal":
                has_active_terminal,

            "has_expired_terminal":
                has_expired_terminal,

            "has_rfc_terminal_state":
                has_rfc_terminal_state,

            "has_other_terminal_state":
                has_other_terminal_state,

            "multiple_terminal_drafts":
                multiple_terminal_drafts,

            "estimated_expiry_date":
                (
                    estimated_expiry_date.date()
                    if not pd.isna(
                        estimated_expiry_date
                    )
                    else ""
                ),

            "likely_dead_date":
                (
                    likely_dead_date.date()
                    if not pd.isna(
                        likely_dead_date
                    )
                    else ""
                ),

            "post_expiry_inactivity_days":
                (
                    post_expiry_inactivity_days
                    if
                    post_expiry_inactivity_days
                    is not None
                    else ""
                ),
        }
    )

    output_rows.append(out)


# ============================================================
# 8. Save
# ============================================================

result_df = pd.DataFrame(
    output_rows
)

result_df.to_csv(
    OUTPUT_FILE,
    index=False,
)


# ============================================================
# 9. Validation summary
# ============================================================

print()
print("=" * 72)
print("FINAL OUTCOME CLASSIFICATION")
print("=" * 72)

print(
    result_df[
        "publication_outcome"
    ].value_counts(
        dropna=False
    )
)


print()
print("=" * 72)
print("PRIMARY COMPARISON SAMPLE")
print("=" * 72)

primary_n = (
    pd.to_numeric(
        result_df[
            "primary_comparison_sample"
        ],
        errors="coerce",
    )
    .fillna(0)
    .sum()
)

print(
    "Successful + Unsuccessful:",
    f"{int(primary_n):,}",
)


# ============================================================
# 10. Additional checks
# ============================================================

print()
print("=" * 72)
print("VALIDATION CHECKS")
print("=" * 72)


successful_without_rfc_terminal = int(
    (
        (
            result_df[
                "publication_outcome"
            ]
            == "Successful"
        )
        &
        (
            pd.to_numeric(
                result_df[
                    "has_rfc_terminal_state"
                ],
                errors="coerce",
            )
            .fillna(0)
            == 0
        )
    ).sum()
)


print(
    "Successful lineages whose terminal "
    "state does not contain 'rfc':",
    successful_without_rfc_terminal,
)


unsuccessful_multiple_terminal = int(
    (
        (
            result_df[
                "publication_outcome"
            ]
            == "Unsuccessful"
        )
        &
        (
            pd.to_numeric(
                result_df[
                    "multiple_terminal_drafts"
                ],
                errors="coerce",
            )
            .fillna(0)
            == 1
        )
    ).sum()
)


print(
    "Unsuccessful lineages with "
    "multiple terminal drafts:",
    unsuccessful_multiple_terminal,
)


ongoing_multiple_terminal = int(
    (
        (
            result_df[
                "publication_outcome"
            ]
            == "Ongoing"
        )
        &
        (
            pd.to_numeric(
                result_df[
                    "multiple_terminal_drafts"
                ],
                errors="coerce",
            )
            .fillna(0)
            == 1
        )
    ).sum()
)


print(
    "Ongoing lineages with "
    "multiple terminal drafts:",
    ongoing_multiple_terminal,
)


recently_expired_count = int(
    (
        result_df[
            "publication_outcome"
        ]
        == "Recently Expired"
    ).sum()
)


print(
    "Recently Expired lineages:",
    recently_expired_count,
)


# ============================================================
# 11. Final rule summary
# ============================================================

print()
print("=" * 72)
print("OUTCOME RULE")
print("=" * 72)

print(
    "Successful       = mapped RFC"
)

print(
    "Ongoing          = no RFC and >=1 "
    "active terminal draft"
)

print(
    "Unsuccessful     = no RFC, all terminal "
    "drafts expired, and >=18 months of "
    "post-expiry inactivity"
)

print(
    "Recently Expired = no RFC, all terminal "
    "drafts expired, but <18 months of "
    "post-expiry inactivity"
)

print(
    "Unknown/Other    = all other no-RFC cases"
)

print()
print(
    f"Saved: {OUTPUT_FILE}"
)