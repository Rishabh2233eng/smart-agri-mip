"""Suggests HOME / MARKETS for src/config.py from what is actually in the database.
Usage: python suggest_config.py [min_days]"""
import re
import sys
import pandas as pd
from src import config as C
from src import db

STOP = {"apmc", "market", "grain", "new", "mandi", "f", "v", "fruit", "vegetable", "yard", "sabzi"}
min_days = int(sys.argv[1]) if len(sys.argv) > 1 else 400
con = db.connect()
q = pd.read_sql_query(
    "SELECT commodity, market, COUNT(DISTINCT date) AS days FROM prices GROUP BY commodity, market", con)
con.close()
if q.empty:
    sys.exit("The database is empty. Import data first (python import_big.py <file> or python data_tools.py import <folder>).")


def core(name):
    toks = [t for t in re.findall(r"[a-z]+", name.lower()) if t not in STOP]
    return max(toks, key=len) if toks else name.lower()


q["core"] = q["market"].map(core)
q["commodity"] = q["commodity"].str.strip().str.title()
g = q.groupby(["commodity", "core"], as_index=False)["days"].max()

good = {}
for c, sub in g.groupby("commodity"):
    sub = sub.sort_values("days", ascending=False)
    ok = sub[sub["days"] >= min_days]
    good[c] = list(ok["core"])
    print(f"\n{c}: {len(ok)} market(s) with at least {min_days} days. Top 8:")
    print(sub.head(8).to_string(index=False))

crops = [c for c, m in good.items() if len(m) >= 2]
if not crops:
    sys.exit(f"\nNo crop has 2+ markets with {min_days}+ days yet. Import more history first.")
common = set.intersection(*[set(good[c]) for c in crops])
if len(common) < 2:
    sys.exit("\nThe crops share fewer than 2 qualifying markets. Try a lower min_days, or fewer crops.")

rank = g[g["commodity"].isin(crops) & g["core"].isin(common)].groupby("core")["days"].sum()
pick = list(rank.sort_values(ascending=False).index[:3])
keys = [p.title() for p in pick]
print("\n--- Paste into src/config.py (HOME = market with most data; change it to the one nearest your farmer) ---")
print(f'HOME = "{keys[0]}"')
print("MARKETS =", keys)
print("COMMODITIES =", sorted(crops))
print("ALIASES =", {c: [c.lower()] for c in sorted(crops)})
print("MARKET_ALIASES =", {k: [p] for k, p in zip(keys, pick)})
print("DIST_KM =", {k: (0 if i == 0 else 50) for i, k in enumerate(keys)}, "  # TODO: replace with real road distances")
missing = [c for c in crops if c not in C.ASSUMP]
for c in missing:
    print(f'ASSUMP needs an entry for {c}, for example "{c}": dict(spoil=0.001, store=1.0),  # ASSUMPTION: replace with a sourced value')
