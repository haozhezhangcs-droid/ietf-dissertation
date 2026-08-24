from pathlib import Path

p = Path(
    r"C:\Users\ZHZ\Desktop\ietf-dissertation\data\ietfdata-ma (1).sqlite"
)

print(p.stat().st_size)