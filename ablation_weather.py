"""Does real rainfall help? Same model with and without rainfall, observed days only, block-bootstrap CI."""
import os, numpy as np, pandas as pd
from src import casestudy
import src.config as C
S, crops, missing = casestudy.setup()
from src.forecast import run_forecasts
from src.decision import HORIZONS

def block_ci(x, L, n=2000, seed=0):
    x = np.asarray(x, float); N = len(x); L = max(1, min(L, N))
    nb = int(np.ceil(N / L)); rng = np.random.default_rng(seed)
    st = rng.integers(0, N - L + 1, (n, nb))
    idx = (st[:, :, None] + np.arange(L)).reshape(n, -1)[:, :N]
    mu = x[idx].mean(1)
    return np.percentile(mu, 2.5), np.percentile(mu, 97.5)

rows = []
for c in crops:
    for m in [m for m in C.MARKETS if (c, m) in S]:
        for h in HORIZONS:
            ow = run_forecasts(S[(c, m)], h)["out"]
            oz = run_forecasts(S[(c, m)].assign(rainfall_mm=0.0), h)["out"]
            obs = S[(c, m)].attrs["obs_dates"]
            idx = ow.index.intersection(oz.index)
            idx = idx[(idx + pd.Timedelta(days=h)).isin(obs)]
            if len(idx) < 20:
                continue
            a = ow.loc[idx, "actual"].values
            aw = 100 * np.abs(ow.loc[idx, "p_med"].values - a) / a
            az = 100 * np.abs(oz.loc[idx, "p_med"].values - a) / a
            d = az - aw                      # positive = rainfall helps
            lo, hi = block_ci(d, h)
            rows.append({"crop": c, "market": m, "h": h, "n": len(idx), "MAPE_no_rain": az.mean(),
                         "MAPE_with_rain": aw.mean(), "gain_pts": d.mean(), "gain_lo": lo, "gain_hi": hi})
res = pd.DataFrame(rows).round(2)
os.makedirs("outputs/real", exist_ok=True)
res.to_csv("outputs/real/ablation_weather.csv", index=False)
pd.set_option("display.width", 200)
print(res.to_string(index=False))
for h in HORIZONS:
    s = res[res.h == h]
    print(f"\nh={h}: rainfall helps in {int((s.gain_pts > 0).sum())}/{len(s)} series; CI excludes zero in {int((s.gain_lo > 0).sum())}; "
          f"hurts significantly in {int((s.gain_hi < 0).sum())}; mean gain {s.gain_pts.mean():.2f} pts")
