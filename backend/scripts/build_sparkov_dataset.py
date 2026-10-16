"""Convert Sparkov generator output into the RulePilot `sparkov-cards-v1` dataset.

Usage: python scripts/build_sparkov_dataset.py SPARKOV_OUTPUT_DIR

Sparkov (https://github.com/namebrandon/Sparkov_Data_Generation, MIT licence,
(c) 2016-2022 Brandon Harris) simulates card transactions from customer
profiles, with fraud bursts on compromised cards. Its output also contains
fake names, addresses and SSNs; none of that is kept. Only numeric features
are derived, per card, from past transactions only:

  amount, hour_of_day, card_present (0 for *_net categories),
  distance_from_home_km (customer home to merchant), transactions_1h and
  transactions_24h (earlier transactions on the same card), new_payee (first
  payment from this card to this merchant).

The first WARMUP_DAYS of each card are used only as history so velocity and
new-payee features are not inflated at the start. Output is a gzip CSV in
backend/app/data_files/ and its SHA-256 is printed for datasets.py.
"""
import csv
import glob
import gzip
import hashlib
import math
import sys
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

WARMUP_DAYS = 30
OUT = Path(__file__).resolve().parents[1] / "app" / "data_files" / "sparkov-cards-v1.csv.gz"
COLUMNS = [
    "transaction_id", "amount", "hour_of_day", "card_present", "distance_from_home_km",
    "transactions_1h", "transactions_24h", "new_payee", "ground_truth_fraud",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def main(source: Path) -> None:
    by_card: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(glob.glob(str(source / "*.csv"))):
        if path.endswith("customers.csv"):
            continue
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle, delimiter="|"):
                by_card[row["cc_num"]].append(row)

    start = min(int(r["unix_time"]) for rows in by_card.values() for r in rows)
    cutoff = start + WARMUP_DAYS * 86400
    out_rows = []
    for rows in by_card.values():
        rows.sort(key=lambda r: (int(r["unix_time"]), r["trans_num"]))
        times = [int(r["unix_time"]) for r in rows]
        seen_merchants: set[str] = set()
        for index, row in enumerate(rows):
            t = times[index]
            new_payee = 0 if row["merchant"] in seen_merchants else 1
            seen_merchants.add(row["merchant"])
            if t < cutoff:
                continue
            out_rows.append({
                "unix_time": t,
                "amount": round(float(row["amt"]), 2),
                "hour_of_day": int(row["trans_time"][:2]),
                "card_present": 0 if row["category"].endswith("_net") else 1,
                "distance_from_home_km": round(haversine_km(
                    float(row["lat"]), float(row["long"]), float(row["merch_lat"]), float(row["merch_long"])), 2),
                "transactions_1h": index - bisect_left(times, t - 3600),
                "transactions_24h": index - bisect_left(times, t - 86400),
                "new_payee": new_payee,
                "ground_truth_fraud": int(row["is_fraud"]),
            })

    out_rows.sort(key=lambda r: (r["unix_time"], r["amount"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", newline="", compresslevel=9) as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for number, row in enumerate(out_rows, start=1):
            writer.writerow({**row, "transaction_id": f"SPK-{number:06d}"})
    fraud = sum(r["ground_truth_fraud"] for r in out_rows)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"{len(out_rows)} records, {fraud} fraud ({fraud / len(out_rows):.2%}) -> {OUT}")
    print(f"sha256 {digest}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
