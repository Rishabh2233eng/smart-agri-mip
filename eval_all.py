import os, numpy as np, pandas as pd
from src import casestudy
import src.config as C
S, crops, missing = casestudy.setup()
from src.forecast import run_forecasts
from src.decision import backtest, HORIZONS

def block_ci(x, L, n=2000, seed=0):
    x = np.asarray(x, float); N = len(x); L = max(1, min(L, N))
    nb = int(np.ceil(N / L)); rng = np.random.default_rng(seed)
    st = rng.integers(0, N - L + 1, (n, nb))
    idx = (st[:, :, None] + np.arange(L)).reshape(n, -1)[:, :N]
    mu = x[idx].mean(1)
    return np.percentile(mu, 2.5), np.percentile(mu, 97.5)

rows, bts = [], []
for c in crops:
    mk = [m for m in C.MARKETS if (c, m) in S]
    if C.HOME not in mk or len(mk) < 2:
        continue
    fc = {}
    for m in mk:
        for h in HORIZONS:
            fc[(m, h)] = run_forecasts(S[(c, m)], h)
            obs = S[(c, m)].attrs["obs_dates"]
            o = fc[(m, h)]["out"]
            tgt = o.index + pd.Timedelta(days=h)
            o = o[tgt.isin(obs)]
            if len(o) < 20:
                continue
            a = o["actual"].values
            ape_n = 100 * np.abs(o["p_naive"].values - a) / a
            ape_g = 100 * np.abs(o["p_med"].values - a) / a
            d = ape_n - ape_g                      # positive = GBM better
            glo, ghi = block_ci(d, h)
            hit = ((a >= o["p_lo"].values) & (a <= o["p_hi"].values)).astype(float)
            clo, chi = block_ci(hit, h)
            r = {"crop": c, "market": m, "h": h, "n": len(o),
                 "MAPE_naive": ape_n.mean(), "MAPE_gbm": ape_g.mean(),
                 "gain_pts": d.mean(), "gain_lo": glo, "gain_hi": ghi,
                 "cov_rolling_%": 100 * hit.mean(), "cov_lo": 100 * clo, "cov_hi": 100 * chi,
                 "width_%": (100 * (o["p_hi"] - o["p_lo"]) / o["p_med"]).mean()}
            if "p_lo_s" in o:
                r["cov_static_%"] = 100 * ((a >= o["p_lo_s"].values) & (a <= o["p_hi_s"].values)).mean()
            rows.append(r)
    b = backtest(c, fc, mk, C.HOME)
    bts.append(b)

res = pd.DataFrame(rows).round(2)
os.makedirs("outputs/real", exist_ok=True)
res.to_csv("outputs/real/eval_all_markets.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("\n=== OBSERVED-DAYS-ONLY, PER CROP/MARKET/HORIZON (gain>0 means GBM beats naive; block bootstrap 95% CI) ===")
print(res.to_string(index=False))
for h in HORIZONS:
    s = res[res.h == h]
    print(f"\nh={h}: GBM better than naive in {int((s.gain_pts > 0).sum())}/{len(s)} series; "
          f"CI excludes zero in {int((s.gain_lo > 0).sum())}; rolling coverage mean {s['cov_rolling_%'].mean():.1f}% (target 80), "
          f"range {s['cov_rolling_%'].min():.1f} to {s['cov_rolling_%'].max():.1f}")
if bts:
    bt = pd.concat(bts).round(2); bt.to_csv("outputs/real/decision_all_crops.csv", index=False)
    print("\n=== DECISION BACKTEST at home market ===")
    print(bt.drop(columns=["regret_vs_oracle"], errors="ignore").to_string(index=False))
print("\nSaved to outputs/real/")

