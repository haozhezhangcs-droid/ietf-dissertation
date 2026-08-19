import csv
from pathlib import Path
from collections import Counter


INPUT = Path(
    "outputs/csv/rq3_unmatched_affiliations.csv"
)

OUTPUT = Path(
    "data/data_organisation_aliases.csv"
)


# ============================================================
# Known organisation mapping
# ============================================================

ALIASES = {

    # telecom companies
    "Orange": [
        "orange",
        "orange labs",
        "france telecom",
        "france telecom orange",
        "france telecom r&d",
    ],

    "Alcatel-Lucent": [
        "alcatel lucent",
        "alcatel-lucent",
    ],

    "Nortel": [
        "nortel",
        "nortel networks",
        "nortel networks inc",
    ],

    "Sun Microsystems": [
        "sun",
        "sun microsystems",
        "sun microsystems inc",
    ],

    "Telefonica": [
        "telefonica",
        "telefonica i+d",
    ],


    "ETRI": [
        "etri",
        "electronics and telecommunications research institute",
    ],


    "H3C": [
        "new h3c technologies",
        "h3c",
    ],


    "Comcast": [
        "comcast",
        "comcast corporation",
    ],


    "CNNIC": [
        "cnnic",
    ],


    "ICANN": [
        "icann",
    ],


    "BT": [
        "bt",
        "british telecom",
        "bt group",
    ],


    "Lucent Technologies": [
        "lucent technologies",
        "lucent",
    ],


    "NEC": [
        "nec",
        "nec corporation",
        "nec europe",
        "nec europe ltd",
    ],


    "University Carlos III of Madrid": [
        "uc3m",
        "universidad carlos iii de madrid",
    ],


    "Columbia University": [
        "columbia university",
        "columbia u.",
    ],


    "University of Bremen": [
        "universitaet bremen tzi",
        "universität bremen tzi",
    ],


    "Ciena": [
        "ciena",
        "ciena corporation",
    ],


    "Telecom Italia": [
        "telecom italia",
    ],


    "INRIA": [
        "inria",
    ],


    "Motorola": [
        "motorola",
        "motorola inc",
    ],


    "Hewlett-Packard": [
        "hewlett-packard",
        "hewlett packard",
    ],


    "Hewlett Packard Enterprise": [
        "hpe",
        "hewlett packard enterprise",
    ],


    "Siemens": [
        "siemens",
        "siemens ag",
    ],


    "Avaya": [
        "avaya",
    ],


    "APNIC": [
        "apnic",
        "asia pacific network information centre",
    ],


    "CableLabs": [
        "cablelabs",
    ],


    "Internet Systems Consortium": [
        "isc",
        "internet systems consortium",
    ],


    "Verisign": [
        "verisign",
        "verisign inc",
        "verisign labs",
    ],


    "Broadcom": [
        "broadcom",
    ],


    "MITRE": [
        "mitre",
        "the mitre corporation",
    ],


    "NetApp": [
        "netapp",
    ],


    "Qualcomm": [
        "qualcomm",
        "qualcomm inc",
    ],


    "NIST": [
        "nist",
        "national institute of standards and technology",
    ],

}


# ============================================================
# write csv
# ============================================================


with open(
    OUTPUT,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow(
        [
            "canonical",
            "alias"
        ]
    )


    for canonical, aliases in ALIASES.items():

        for alias in aliases:

            writer.writerow(
                [
                    canonical,
                    alias
                ]
            )


print("Saved:")
print(OUTPUT)



# ============================================================
# show unmatched remaining
# ============================================================

print("\nTop unmatched:")
print("----------------")


counter = Counter()


with open(INPUT, newline="", encoding="utf-8-sig") as f:

    reader = csv.DictReader(f)
    
    for row in reader:

        counter[row["affiliation_raw"]] += int(
            row["count"]
        )


for name,count in counter.most_common(30):

    print(
        f"{name:50} {count}"
    )