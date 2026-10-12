"""Data layer. Day 1 uses a synthetic generator that mimics mandi prices
(trend + season + AR shocks + rainfall effect + mandi offsets).
Day 2: swap in real Agmarknet CSV via load_agmarknet_csv()."""
import numpy as np
import pandas as pd

# commodity: (base price Rs/qtl, seasonal amplitude, shock volatility)
COMMS = {"Wheat": (2400, 0.05, 0.004), "Tomato": (1800, 0.35, 0.03), "Onion": (1500, 0.28, 0.02)}
# mandi: price premium vs home market
MARKETS = {"Faridabad": 0.0, "Azadpur": 0.06, "Ghazipur": -0.02}
HOME = "Faridabad"


def make_synthetic(start="2022-01-01", days=1100, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=days)
    t = np.arange(days)
    rows = []
    for ci, (c, (base, amp, vol)) in enumerate(COMMS.items()):
        rain = np.clip(rng.gamma(0.6, 6, days) * (1 + np.sin(2 * np.pi * (t - 170) / 365)), 0, None)
        season = amp * np.sin(2 * np.pi * (t - 60 * (ci + 1)) / 365)
        shock = np.zeros(days)
        for i in range(1, days):
            shock[i] = 0.97 * shock[i - 1] + rng.normal(0, vol) + (0.0015 * (rain[i - 5] - 6) if i >= 5 else 0)
        common = base * np.exp(0.0002 * t + season + shock)
        for m, prem in MARKETS.items():
            local = np.zeros(days)
            for i in range(1, days):
                local[i] = 0.9 * local[i - 1] + rng.normal(0, 0.008)
            price = common * (1 + prem) * np.exp(local)
            arrivals = 500 * np.exp(-0.8 * (season - season.mean()) + rng.normal(0, 0.1, days))
            rows.append(pd.DataFrame({"date": dates, "commodity": c, "market": m,
                                      "modal_price": price.round(1),
                                      "arrivals_qtl": arrivals.round(0),
                                      "rainfall_mm": rain.round(1)}))
    return pd.concat(rows, ignore_index=True)


def load_agmarknet_csv(path):
    """Expected columns: date, commodity, market, modal_price, arrivals_qtl, rainfall_mm.
    Fills gaps to daily frequency."""
    df = pd.read_csv(path, parse_dates=["date"])
    out = []
    for (c, m), g in df.groupby(["commodity", "market"]):
        g = g.set_index("date").sort_index()
        g = g[~g.index.duplicated()].asfreq("D").ffill()
        g["commodity"], g["market"] = c, m
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True)


def series(df, commodity, market):
    g = df[(df.commodity == commodity) & (df.market == market)].set_index("date").sort_index()
    return g[["modal_price", "arrivals_qtl", "rainfall_mm"]]