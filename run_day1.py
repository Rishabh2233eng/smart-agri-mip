import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data import make_synthetic, series, COMMS, MARKETS, HOME
from src.forecast import run_forecasts, metrics
from src.decision import recommend, backtest, HORIZONS

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
os.makedirs("outputs", exist_ok=True)
os.makedirs("data", exist_ok=True)

df = make_synthetic()
df.to_csv("data/synthetic_prices.csv", index=False)

results, metric_rows, bt_frames = {}, [], []

for c in COMMS:
    fc = {}
    for m in MARKETS:
        s = series(df, c, m)
        for h in HORIZONS:
            fc[(m, h)] = run_forecasts(s, h)
            metric_rows.append({"commodity": c, "market": m, "h": h, **metrics(fc[(m, h)]["out"])})
    results[c] = fc
    bt_frames.append(backtest(c, fc, lam=0.5))

# 1) forecast accuracy
mt = pd.DataFrame(metric_rows).round(2)
mt.to_csv("outputs/forecast_metrics.csv", index=False)
print("\n=== FORECAST METRICS (home market) ===")
print(mt[mt.market == HOME].to_string(index=False))
print("\nTarget interval coverage is 80%. Check coverage_% is close to it.")

# 2) decision backtest
bt = pd.concat(bt_frames).round(2)
bt.to_csv("outputs/decision_backtest.csv", index=False)
print("\n=== DECISION BACKTEST (realised net Rs per quintal) ===")
print(bt.to_string(index=False))

# 3) live recommendation for 50 quintals
print("\n=== LIVE RECOMMENDATION (50 quintals, top 3 options) ===")
for c in COMMS:
    fc = results[c]
    price_now = {m: fc[(m, 7)]["last"][0] for m in MARKETS}
    latest = {k: v["last"][1:] for k, v in fc.items()}
    rec = recommend(c, 50, price_now, latest, lam=0.5)
    print(f"\n{c}:")
    print(rec.head(3).to_string(index=False))

# 4) plots
fig, axs = plt.subplots(len(COMMS), 1, figsize=(10, 9))
for ax, c in zip(axs, COMMS):
    o = results[c][(HOME, 7)]["out"]
    x = o.index + pd.Timedelta(days=7)
    ax.plot(x, o["actual"], label="Actual", color="black", lw=1)
    ax.plot(x, o["p_med"], label="Forecast (7d)", color="tab:blue", lw=1)
    ax.fill_between(x, o["p_lo"], o["p_hi"], alpha=0.25, label="80% conformal interval")
    ax.set_title(f"{c} - {HOME}")
    ax.set_ylabel("Rs/qtl")
    ax.legend(loc="upper left", fontsize=8)
plt.tight_layout()
plt.savefig("outputs/forecast_plot.png", dpi=150)
plt.close()

pivot = bt.pivot(index="strategy", columns="commodity", values="avg_net_Rs_per_qtl")
pivot.plot(kind="barh", figsize=(10, 5))
plt.xlabel("Average realised net Rs/qtl (test period)")
plt.tight_layout()
plt.savefig("outputs/decision_comparison.png", dpi=150)
plt.close()

print("\nDone. See the outputs/ folder: forecast_metrics.csv, decision_backtest.csv, 2 PNG plots.")