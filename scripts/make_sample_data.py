"""Generate reproducible sample datasets (with a few planted anomalies) into sample_data/."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "sample_data"
random.seed(42)

PRODUCTS = [("Laptop", "Computers", 900, 650), ("Phone", "Mobile", 600, 420), ("Tablet", "Mobile", 400, 290),
            ("Monitor", "Computers", 250, 170), ("Headset", "Accessories", 90, 55), ("Cable", "Accessories", 12, 4)]
REGIONS = {"North": 1.0, "South": 0.8, "East": 1.0, "West": 1.15}
SEGMENTS, COUNTRIES = ["Enterprise", "SMB", "Startup"], ["India", "USA", "Germany", "UK"]


def write(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


customers = [(f"C{i:03d}", f"Customer {i}", SEGMENTS[i % 3], COUNTRIES[i % 4]) for i in range(1, 13)]
write("customers.csv", ["customer_id", "customer_name", "segment", "country"], customers)
write("products.csv", ["product", "category", "unit_cost"], [(p, c, cost) for p, c, _, cost in PRODUCTS])

sales = []
for i in range(500):
    d = date(2025, 1, 1) + timedelta(days=random.randrange(640))
    product, _, price, _ = random.choice(PRODUCTS)
    region = random.choice(list(REGIONS))
    units = random.randint(1, 5)
    revenue = round(units * price * random.uniform(0.85, 1.15) * REGIONS[region], 2)
    sales.append([1000 + i, d.isoformat(), region, product, random.choice(customers)[0], units, revenue])
sales[60][6], sales[210][6], sales[330][5] = 48000.0, 39500.0, 60  # planted anomalies
write("sales.csv", ["order_id", "order_date", "region", "product", "customer_id", "units", "revenue"], sales)
print("Wrote sample data to", OUT)
