"""Import a large Agmarknet-style CSV in chunks, keeping only our crops and states.
Usage: python import_big.py <file.csv> [--crops wheat,onion,tomato,potato] [--states haryana,delhi,"uttar pradesh"]"""
import argparse
import os
import re
import pandas as pd
from src import db

ap = argparse.ArgumentParser()
ap.add_argument("path")
ap.add_argument("--crops", default="wheat,onion,tomato,potato")
ap.add_argument("--states", default="haryana,delhi,uttar pradesh")
a = ap.parse_args()
crops = {c.strip().lower() for c in a.crops.split(",")}
states = {s.strip().lower() for s in a.states.split(",")}


def map_col(name):
    n = re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()
    if any(k in n for k in ("code", "unit", "latitude", "longitude", "origin", "type")) or n == "id":
        return None
    if "date" in n:
        return "date"
    if "modal" in n:
        return "modal_price"
    if "min" in n:
        return "min_price"
    if "max" in n:
        return "max_price"
    if "arrival" in n:
        return "arrivals_tonnes"
    if "state" in n:
        return "state"
    if "district" in n:
        return "district"
    if "market" in n:
        return "market"
    if "commodity" in n:
        return "commodity"
    if "variety" in n:
        return "variety"
    if "grade" in n:
        return "grade"
    return None


first, total = True, 0
src_name = os.path.basename(a.path)
for chunk in pd.read_csv(a.path, chunksize=500_000, dtype=str, low_memory=False, encoding_errors="replace"):
    mapping, seen = {}, set()
    for c in chunk.columns:
        m = map_col(c)
        if m and m not in seen:
            mapping[c] = m
            seen.add(m)
    if first:
        print("Columns found:", list(chunk.columns))
        print("Mapped as:", mapping)
        need = {"date", "modal_price", "market", "commodity"} - seen
        if need:
            raise SystemExit(f"Could not find columns for {sorted(need)}. Send me the 'Columns found' line above.")
        first = False
    d = chunk[list(mapping)].rename(columns=mapping)
    d = d[d["commodity"].str.strip().str.lower().isin(crops)]
    if "state" in d.columns:
        d = d[d["state"].str.strip().str.lower().isin(states)]
    if d.empty:
        continue
    total += db.upsert(d, src_name)
    print("rows kept so far:", total)
print("Done. Rows imported:", total)
