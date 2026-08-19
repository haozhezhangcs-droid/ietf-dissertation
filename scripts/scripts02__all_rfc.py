from collections import Counter

from ietfdata.rfcindex import RFCIndex


RFC_INDEX_PATH = (
    r"C:\Users\ZHZ\Desktop\ietf-dissertation"
    r"\data\rfc-index.xml"
)

ri = RFCIndex(rfc_index=RFC_INDEX_PATH)


counts_by_year = Counter()

for rfc in ri.rfcs():
    if rfc.year is not None:
        counts_by_year[rfc.year] += 1


print("Year | RFCs published")
print("-" * 25)

for year in sorted(counts_by_year):
    print(f"{year} | {counts_by_year[year]}")
from pathlib import Path
import matplotlib.pyplot as plt


BASE_DIR = Path(r"C:\Users\ZHZ\Desktop\ietf-dissertation")
FIGURE_DIR = BASE_DIR / "outputs" / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


years = sorted(counts_by_year)
counts = [counts_by_year[year] for year in years]


plt.figure(figsize=(11, 6))
plt.plot(years, counts)

plt.xlabel("Year")
plt.ylabel("RFCs published")
plt.title("RFCs Published per Year")

plt.tight_layout()

output_path = FIGURE_DIR / "rfcs_published_by_year.png"
plt.savefig(output_path, dpi=300)
plt.show()

print("\nFigure saved to:", output_path)