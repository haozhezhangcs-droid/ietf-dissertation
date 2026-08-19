from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from ietfdata.rfcindex import RFCIndex


BASE_DIR = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation")
RFC_INDEX_PATH = BASE_DIR / "data" / "rfc-index.xml"
FIGURE_DIR = BASE_DIR / "outputs" / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


ri = RFCIndex(rfc_index=str(RFC_INDEX_PATH))


# These are the main categories shown in the original paper.
MAJOR_AREAS = {
    "rtg",
    "int",
    "app",
    "ops",
    "sec",
    "tsv",
    "rai",
    "art",
}

AREA_ORDER = [
    "Other",
    "rtg",
    "int",
    "app",
    "ops",
    "sec",
    "tsv",
    "rai",
    "art",
]


# year -> area -> count
counts = defaultdict(lambda: defaultdict(int))


for rfc in ri.rfcs():
    if rfc.year is None:
        continue

    # Exclude the incomplete current year.
    if rfc.year > 2025:
        continue

    raw_area = rfc.area

    if raw_area in MAJOR_AREAS:
        plot_area = raw_area
    else:
        plot_area = "Other"

    counts[rfc.year][plot_area] += 1


years = sorted(counts)

series = []

for area in AREA_ORDER:
    values = [
        counts[year].get(area, 0)
        for year in years
    ]
    series.append(values)


# Print totals before drawing.
print("Area totals in the plotted data")
print("-" * 35)

for area, values in zip(AREA_ORDER, series):
    print(f"{area:<10} {sum(values):>8}")


plt.figure(figsize=(11, 6))

plt.stackplot(
    years,
    *series,
    labels=AREA_ORDER,
)

plt.xlabel("Year")
plt.ylabel("RFCs published")
plt.title("RFCs Published per Year by IETF Area, 1969–2025")

plt.legend(
    loc="upper left",
    ncol=5,
)

plt.tight_layout()

output_path = FIGURE_DIR / "rfcs_by_major_area_1969_2025.png"

plt.savefig(
    output_path,
    dpi=300,
    bbox_inches="tight",
)

plt.show()

print("\nFigure saved to:")
print(output_path)