import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import config as C
from src.data import make_synthetic, series
from src.realdata import load_real
from src.db import load_from_db
from src.forecast import run_forecasts, metrics
from src.decision import recommend, backtest, HORIZONS

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)

# ---- data source priority: database -> CSV folder -> synthetic ----
S = load_from_db()
SRC = "database"
if not S and os.path.isdir("data/real"):
    S = load_real("data/real")
    SRC = "csv folder"

if not S:
    TAG = "synthetic"
    print("\n*** NO REAL DATA FOUND (database or data/real) -> using SYNTHETIC data. "
          "Do NOT use these numbers in the paper. ***\n")
    df = make_synthetic()
    S = {(c, m): series(df, c, m) for c in C.COMMODITIES for m in C.MARKETS}
else:
    TAG = "real"
    print(f"\nUsing REAL data from the {SRC}\n")

OUT = f"outputs/{TAG}"
os.makedirs(OUT, exist_ok=True)

# ---- dataset summary (goes into the paper's dataset table) ----
rows = []
for (c, m), g in sorted(S.items()):
    obs = g.attrs.get("observed")
    rows.append({"commodity": c, "market": m, "start": g.index[0].date(), "end": g.index[-1].date(),
                 "days": len(g), "observed_%": round(100 * obs / len(g), 1) if obs else np.nan})
summary = pd.DataFrame(rows)
summary.to_csv(f"{OUT}/data_summary.csv", index=False)
print("=== DATA SUMMARY ===")
print(summary.to_string(index=False))

MIN_DAYS = 400
results, metric_rows, bt_frames, mk_used = {}, [], [], {}
for c in C.COMMODITIES:
    mk = [m for m in C.MARKETS if (c, m) in S and len(S[(c, m)]) >= MIN_DAYS]
    if C.HOME not in mk or len(mk) < 2:
        have = [(m, len(S[(c, m)])) for m in C.MARKETS if (c, m) in S]
        print(f"\nSkipping {c}: need >= {MIN_DAYS} days for home market {C.HOME} and one more market. Have: {have}")
        continue
    mk_used[c] = mk
    fc = {}
    for m in mk:
        for h in HORIZONS:
            fc[(m, h)] = run_forecasts(S[(c, m)], h)
            metric_rows.append({"commodity": c, "market": m, "h": h, **metrics(fc[(m, h)]["out"])})
    results[c] = fc
    bt_frames.append(backtest(c, fc, mk, C.HOME))

if not results:
    sys.exit("No usable series yet. Run:  python data_tools.py stats  to see how many days you have, "
             "then fix HOME / MARKETS / aliases in src/config.py")

mt = pd.DataFrame(metric_rows).round(2)
mt.to_csv(f"{OUT}/forecast_metrics.csv", index=False)
cols = ["commodity", "h", "n_test", "MAPE_naive", "MAPE_ridge", "MAPE_rf", "MAPE_gbm",
        "cov_static_%", "cov_rolling_%", "width_%"]
print("\n=== FORECAST METRICS (home market, target coverage 80%) ===")
print(mt[mt.market == C.HOME][cols].to_string(index=False))

bt = pd.concat(bt_frames).round(2)
bt.to_csv(f"{OUT}/decision_backtest.csv", index=False)
print("\n=== DECISION BACKTEST (realised net Rs per quintal) ===")
print(bt.drop(columns=["regret_vs_oracle"]).to_string(index=False))

print("\n=== LIVE RECOMMENDATION (50 quintals, top 3 options, lam=0.5) ===")
for c, fc in results.items():
    mk = mk_used[c]
    price_now = {m: fc[(m, 7)]["last"][0] for m in mk}
    latest = {k: v["last"][1:] for k, v in fc.items()}
    print(f"\n{c}:")
    print(recommend(c, 50, mk, price_now, latest, lam=0.5).head(3).to_string(index=False))

# ---- plots ----
n = len(results)
fig, axs = plt.subplots(n, 1, figsize=(10, 3 * n), squeeze=False)
for ax, c in zip(axs[:, 0], results):
    o = results[c][(C.HOME, 7)]["out"]
    x = o.index + pd.Timedelta(days=7)
    ax.plot(x, o["actual"], color="black", lw=1, label="Actual")
    ax.plot(x, o["p_med"], color="tab:blue", lw=1, label="Forecast (7d)")
    ax.fill_between(x, o["p_lo"], o["p_hi"], alpha=0.25, label="80% rolling-conformal interval")
    ax.set_title(f"{c} - {C.HOME}")
    ax.set_ylabel("Rs/qtl")
    ax.legend(loc="upper left", fontsize=8)
plt.tight_layout()
plt.savefig(f"{OUT}/forecast_plot.png", dpi=150)
plt.close()

fig, axs = plt.subplots(1, n, figsize=(5 * n, 4), squeeze=False)
for ax, c in zip(axs[0], results):
    b = bt[bt.commodity == c]
    f = b[b.strategy.str.startswith("Forecast")]
    ax.plot(f["p10_net_Rs_per_qtl"], f["avg_net_Rs_per_qtl"], "o-", label="Forecast engine")
    for _, r in f.iterrows():
        ax.annotate(r["strategy"].split("=")[1], (r["p10_net_Rs_per_qtl"], r["avg_net_Rs_per_qtl"]), fontsize=8)
    for name, mark in [("Naive (no forecast)", "s"), ("Sell now at home", "x")]:
        r = b[b.strategy == name].iloc[0]
        ax.scatter(r["p10_net_Rs_per_qtl"], r["avg_net_Rs_per_qtl"], marker=mark, s=60, label=name)
    ax.set_xlabel("Worst-10% net (Rs/qtl)")
    ax.set_ylabel("Average net (Rs/qtl)")
    ax.set_title(f"{c}: risk trade-off (labels = lam)")
    ax.legend(fontsize=7)
plt.tight_layout()
plt.savefig(f"{OUT}/risk_tradeoff.png", dpi=150)
plt.close()

print(f"\nDone. Results saved in {OUT}/")