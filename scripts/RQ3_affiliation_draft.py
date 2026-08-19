from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from ietfdata.datatracker import DataTracker
from ietfdata.dt_backend import DTBackendArchive


# ============================================================
# 1. Configuration
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
)

DATABASE_FILE = (
    PROJECT_ROOT
    / "data"
    / "ietfdata-dt.sqlite"
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


OUTPUT_AUTHOR_FILE = (
    OUTPUT_DIR
    / "rq3_author_affiliation_raw.csv"
)

OUTPUT_FREQUENCY_FILE = (
    OUTPUT_DIR
    / "rq3_affiliation_frequency.csv"
)


# ============================================================
# 2. Open Datatracker
# ============================================================

dt = DataTracker(
    DTBackendArchive(
        str(DATABASE_FILE)
    )
)

draft_type = dt.document_type_from_slug(
    "draft"
)


# ============================================================
# 3. Storage
# ============================================================

records = []

draft_count = 0
author_record_count = 0
missing_affiliation_count = 0
error_count = 0


# ============================================================
# 4. Read all Internet-Draft authors
# ============================================================

for draft in dt.documents(
    doctype=draft_type
):

    draft_count += 1

    if draft_count % 1000 == 0:

        print(
            "Drafts processed:",
            draft_count
        )


    try:

        authors = dt.document_authors(
            draft
        )

    except Exception as exc:

        error_count += 1

        print(
            "Could not read authors:",
            draft.name,
            exc,
        )

        continue


    for author in authors:

        author_record_count += 1


        # ----------------------------------------------------
        # Read the affiliation exactly as stored
        # ----------------------------------------------------

        affiliation = getattr(
            author,
            "affiliation",
            None,
        )


        # ----------------------------------------------------
        # Convert empty values to missing
        # ----------------------------------------------------

        if affiliation is not None:

            affiliation = str(
                affiliation
            ).strip()


        if not affiliation:

            affiliation = None
            missing_affiliation_count += 1


        # ----------------------------------------------------
        # Other useful fields for later inspection
        # ----------------------------------------------------

        email = getattr(
            author,
            "email",
            None,
        )

        country = getattr(
            author,
            "country",
            None,
        )

        person = getattr(
            author,
            "person",
            None,
        )


        records.append(
            {
                "draft_name": draft.name,
                "person_reference": (
                    str(person)
                    if person is not None
                    else None
                ),
                "email": (
                    str(email)
                    if email is not None
                    else None
                ),
                "country": (
                    str(country)
                    if country is not None
                    else None
                ),
                "affiliation_raw": affiliation,
            }
        )


# ============================================================
# 5. Convert to DataFrame
# ============================================================

authors_df = pd.DataFrame(
    records
)


# ============================================================
# 6. Save raw author-affiliation records
# ============================================================

authors_df.to_csv(
    OUTPUT_AUTHOR_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 7. Count affiliation strings
# ============================================================

affiliation_frequency = (
    authors_df[
        "affiliation_raw"
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


# Percentage of all non-missing affiliation records

if len(
    affiliation_frequency
) > 0:

    total_known_affiliations = (
        affiliation_frequency[
            "count"
        ].sum()
    )

    affiliation_frequency[
        "percentage"
    ] = (
        affiliation_frequency[
            "count"
        ]
        /
        total_known_affiliations
        *
        100
    ).round(3)


affiliation_frequency.to_csv(
    OUTPUT_FREQUENCY_FILE,
    index=False,
    encoding="utf-8-sig",
)


# ============================================================
# 8. Summary
# ============================================================

print("\n" + "=" * 70)

print(
    "RQ3 affiliation audit"
)

print(
    "=" * 70
)

print(
    "Drafts checked:",
    draft_count
)

print(
    "Author records:",
    author_record_count
)

print(
    "Missing affiliation:",
    missing_affiliation_count
)

print(
    "Known affiliation:",
    (
        author_record_count
        -
        missing_affiliation_count
    )
)

print(
    "Unique raw affiliation strings:",
    authors_df[
        "affiliation_raw"
    ].nunique(
        dropna=True
    )
)

print(
    "Errors:",
    error_count
)


# ============================================================
# 9. Top affiliations
# ============================================================

print(
    "\nTop 100 raw affiliations"
)

print(
    "-" * 70
)

print(
    affiliation_frequency
    .head(100)
    .to_string(
        index=False
    )
)


# ============================================================
# 10. Look specifically for strings containing common words
#     This is ONLY for inspection, not normalisation.
# ============================================================

keywords = [
    "huawei",
    "futurewei",
    "cisco",
    "ericsson",
    "nokia",
    "google",
    "microsoft",
    "juniper",
]


print(
    "\nExamples containing selected organisation keywords"
)

print(
    "=" * 70
)


for keyword in keywords:

    matches = (
        affiliation_frequency[
            affiliation_frequency[
                "affiliation_raw"
            ]
            .str.contains(
                keyword,
                case=False,
                na=False,
                regex=False,
            )
        ]
    )

    print(
        f"\n[{keyword}]"
    )

    if matches.empty:

        print(
            "No matches."
        )

    else:

        print(
            matches
            .head(30)
            .to_string(
                index=False
            )
        )


# ============================================================
# 11. Some structurally complex affiliations
# ============================================================

complex_affiliations = (
    affiliation_frequency[
        affiliation_frequency[
            "affiliation_raw"
        ]
        .str.contains(
            ",|/|;",
            regex=True,
            na=False,
        )
    ]
)


print(
    "\nAffiliations containing comma / slash / semicolon"
)

print(
    "-" * 70
)

print(
    complex_affiliations
    .head(100)
    .to_string(
        index=False
    )
)


print(
    "\nFiles saved:"
)

print(
    OUTPUT_AUTHOR_FILE
)

print(
    OUTPUT_FREQUENCY_FILE
)