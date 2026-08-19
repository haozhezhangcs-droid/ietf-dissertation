from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import pandas as pd


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
)

INPUT_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "CSV"
    / "rq3_author_affiliation_raw.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "CSV"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


OUTPUT_NORMALISED_FILE = (
    OUTPUT_DIR
    / "rq3_author_affiliation_normalised.csv"
)

OUTPUT_ORGANISATION_FREQUENCY = (
    OUTPUT_DIR
    / "rq3_organisation_frequency.csv"
)

OUTPUT_UNMATCHED_FILE = (
    OUTPUT_DIR
    / "rq3_unmatched_affiliations.csv"
)


# ============================================================
# 2. Organisation aliases
# ============================================================

# IMPORTANT:
#
# This mapping is intentionally conservative.
#
# We merge obvious name variants of the same recorded
# organisation.
#
# We DO NOT currently merge parent/subsidiary relationships.
#
# Therefore:
#
# Huawei != Futurewei
#
# Futurewei remains its own organisation.


ORGANISATION_ALIASES = {

    "Cisco": [
        "cisco systems inc",
        "cisco systems",
        "cisco",
    ],

    "Huawei": [
        "huawei technologies co ltd",
        "huawei technologies",
        "huawei usa",
        "huawei",
    ],

    "Futurewei": [
        "futurewei technologies",
        "futurewei",
    ],

    "Ericsson": [
        "ericsson ab",
        "ericsson",
    ],

    "China Mobile": [
        "china mobile",
    ],

    "Juniper Networks": [
        "juniper networks",
        "juniper",
    ],

    "Nokia": [
        "nokia research center",
        "nokia",
    ],

    "ZTE": [
        "zte corporation",
        "zte corp",
        "zte",
    ],

    "Microsoft": [
        "microsoft corporation",
        "microsoft",
    ],

    "Google": [
        "google llc",
        "google inc",
        "google",
    ],

    "China Telecom": [
        "china telecom",
    ],

    "China Unicom": [
        "china unicom",
    ],

    "Tsinghua University": [
        "tsinghua university",
    ],

    "NTT": [
        "ntt",
    ],

    "IBM": [
        "ibm",
    ],

    "Apple": [
        "apple inc",
        "apple",
    ],

    "Cloudflare": [
        "cloudflare",
    ],

    "Oracle": [
        "oracle",
    ],

    "Intel": [
        "intel",
    ],

    "Mozilla": [
        "mozilla",
    ],

    "Deutsche Telekom": [
        "deutsche telekom ag",
        "deutsche telekom",
    ],

    "Verizon": [
        "verizon inc",
        "verizon",
    ],

    "AT&T": [
        "at&t labs",
        "at&t",
    ],

    "Red Hat": [
        "red hat",
    ],

    "Akamai Technologies": [
        "akamai technologies",
        "akamai",
    ],
}


# ============================================================
# 3. Non-organisational affiliation labels
# ============================================================

# These values should not be treated as companies.

NON_ORGANISATIONAL_VALUES = {

    "independent",
    "individual",
    "unaffiliated",
    "consultant",
}


# ============================================================
# 4. Clean affiliation strings
# ============================================================

def clean_affiliation(
    affiliation,
):

    if pd.isna(
        affiliation
    ):

        return None


    text = str(
        affiliation
    ).strip()


    if not text:

        return None


    # --------------------------------------------------------
    # Unicode normalisation
    # --------------------------------------------------------

    text = unicodedata.normalize(
        "NFKC",
        text,
    )


    # --------------------------------------------------------
    # Lowercase
    # --------------------------------------------------------

    text = text.casefold()


    # --------------------------------------------------------
    # Standardise common punctuation
    # --------------------------------------------------------

    text = text.replace(
        "&",
        " & ",
    )


    text = re.sub(
        r"[,\.;:/\\()\[\]{}\-]+",
        " ",
        text,
    )


    # --------------------------------------------------------
    # Remove repeated whitespace
    # --------------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


    return text


# ============================================================
# 5. Prepare aliases
# ============================================================

prepared_aliases = []


for organisation, aliases in ORGANISATION_ALIASES.items():

    for alias in aliases:

        cleaned_alias = clean_affiliation(
            alias
        )

        prepared_aliases.append(
            (
                cleaned_alias,
                organisation,
            )
        )


# ------------------------------------------------------------
# Longer aliases are checked first.
#
# Example:
#
# "huawei technologies"
#
# should be checked before:
#
# "huawei"
# ------------------------------------------------------------

prepared_aliases.sort(
    key=lambda item: len(
        item[0]
    ),
    reverse=True,
)


# ============================================================
# 6. Match organisation
# ============================================================

def match_organisation(
    affiliation,
):

    cleaned = clean_affiliation(
        affiliation
    )


    # --------------------------------------------------------
    # Missing affiliation
    # --------------------------------------------------------

    if cleaned is None:

        return pd.Series(
            {
                "affiliation_clean": None,
                "organisation_normalised": "Missing",
                "normalisation_status": "missing",
                "matched_alias": None,
                "matched_organisation_count": 0,
            }
        )


    # --------------------------------------------------------
    # Non-organisational labels
    # --------------------------------------------------------

    if cleaned in NON_ORGANISATIONAL_VALUES:

        return pd.Series(
            {
                "affiliation_clean": cleaned,
                "organisation_normalised": "Independent / Non-organisational",
                "normalisation_status": "non_organisational",
                "matched_alias": cleaned,
                "matched_organisation_count": 0,
            }
        )


    # --------------------------------------------------------
    # Organisation matching
    # --------------------------------------------------------

    #
    # We search across the ENTIRE affiliation string.
    #
    # Therefore this can match:
    #
    # "Research Center, Huawei Technologies, Beijing"
    #
    # because "huawei technologies" appears in the middle.
    #

    padded_text = (
        " "
        +
        cleaned
        +
        " "
    )
    matched_organisations = set()
    matched_aliases = []

    for alias, organisation in prepared_aliases:

        padded_alias = (
            " "
            +
            alias
            +
            " "
        )


        if padded_alias in padded_text:
            matched_organisations.add(
                organisation
            )

            matched_aliases.append(
                alias
            )        
           


    # --------------------------------------------------------
    # Not yet normalised
    # --------------------------------------------------------
    if len(
            matched_organisations
        ) == 0: 
        return pd.Series(
                {
                    "affiliation_clean": cleaned,
                    "organisation_normalised": None,
                    "normalisation_status": "unmatched",
                    "matched_alias": None,
                    "matched_organisation_count": 0,
                }
            )
    if len(matched_organisations) == 1:

        organisation = next(
            iter(matched_organisations)
        )

        return pd.Series(
            {
                "affiliation_clean": cleaned,
                "organisation_normalised": organisation,
                "normalisation_status": "alias_matched",
                "matched_alias": "; ".join(
                    sorted(matched_aliases)
                ),
                "matched_organisation_count": 1,
            }
        )
    # ========================================================
    # 6. Multiple organisations matched
    # ========================================================

    return pd.Series(
        {
            "affiliation_clean": cleaned,

            "organisation_normalised":
                "; ".join(
                    sorted(matched_organisations)
                ),

            "normalisation_status":
                "multi_organisation",

            "matched_alias":
                "; ".join(
                    sorted(matched_aliases)
                ),

            "matched_organisation_count":
                len(matched_organisations),
        }
    )
# ============================================================
# 7. Load author-affiliation dataset
# ============================================================

df = pd.read_csv(
    INPUT_FILE
)


print(
    "Rows loaded:",
    len(df)
)


print(
    "\nColumns:"
)

print(
    df.columns.tolist()
)


# ============================================================
# 8. Normalise affiliations
# ============================================================

normalisation_results = (
    df[
        "affiliation_raw"
    ]
    .apply(
        match_organisation
    )
)


df = pd.concat(
    [
        df,
        normalisation_results,
    ],
    axis=1,
)


# ============================================================
# 9. Save normalised author dataset
# ============================================================

df.to_csv(
    OUTPUT_NORMALISED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 10. Organisation frequency
# ============================================================

organisation_frequency = (

    df.loc[
        df[
            "organisation_normalised"
        ].notna(),
        "organisation_normalised",
    ]

    .value_counts()

    .rename_axis(
        "organisation_normalised"
    )

    .reset_index(
        name="author_records"
    )
)


organisation_frequency.to_csv(
    OUTPUT_ORGANISATION_FREQUENCY,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 11. Unmatched affiliations
# ============================================================

unmatched_df = (

    df.loc[
        df[
            "normalisation_status"
        ] == "unmatched",
        "affiliation_raw",
    ]

    .dropna()

    .value_counts()

    .rename_axis(
        "affiliation_raw"
    )

    .reset_index(
        name="count"
    )
)


unmatched_df.to_csv(
    OUTPUT_UNMATCHED_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 12. Summary
# ============================================================

print(
    "\n"
    +
    "=" * 70
)

print(
    "RQ3 affiliation normalisation"
)

print(
    "=" * 70
)


print(
    "\nNormalisation status:"
)

print(
    df[
        "normalisation_status"
    ].value_counts(
        dropna=False
    )
)


print(
    "\nTop normalised organisations:"
)

print(
    "-" * 70
)

print(
    organisation_frequency
    .head(50)
    .to_string(
        index=False
    )
)


print(
    "\nTop unmatched affiliations:"
)

print(
    "-" * 70
)

print(
    unmatched_df
    .head(100)
    .to_string(
        index=False
    )
)


# ============================================================
# 13. Specifically inspect Huawei and Futurewei
# ============================================================

print(
    "\nHuawei examples"
)

print(
    "-" * 70
)


print(
    df.loc[
        df[
            "organisation_normalised"
        ] == "Huawei",
        [
            "affiliation_raw",
            "affiliation_clean",
            "matched_alias",
        ],
    ]
    .drop_duplicates()
    .head(100)
    .to_string(
        index=False
    )
)


print(
    "\nFuturewei examples"
)

print(
    "-" * 70
)


print(
    df.loc[
        df[
            "organisation_normalised"
        ] == "Futurewei",
        [
            "affiliation_raw",
            "affiliation_clean",
            "matched_alias",
        ],
    ]
    .drop_duplicates()
    .head(100)
    .to_string(
        index=False
    )
)


print(
    "\nFiles saved:"
)

print(
    OUTPUT_NORMALISED_FILE
)

print(
    OUTPUT_ORGANISATION_FREQUENCY
)

print(
    OUTPUT_UNMATCHED_FILE
)