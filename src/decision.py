"""Cost-aware, risk-aware sell-timing and market-selection engine.
All cost numbers are ASSUMPTIONS for Day 1: replace with sourced values on Day 3."""
import numpy as np
import pandas as pd
from .data import MARKETS, HOME

HORIZONS = (7, 14)
DIST_KM = {"Faridabad": 0, "Azadpur": 45, "Ghazipur": 50}
TRANSPORT_PER_QTL_KM = 0.5      # Rs per quintal per km
COMMISSION = 0.02               # mandi commission on sale value
ASSUMP = {                      # spoil: fraction lost per day, store: Rs/qtl/day
    "Wheat":  dict(spoil=0.0002, store=0.5),
    "Tomato": dict(spoil=0.015,  store=3.0),
    "Onion":  dict(spoil=0.002,  store=1.0),
}


def net_value(price, comm, market, h):
    a = ASSUMP[comm]
    keep = (1 - a["spoil"]) ** h
    return price * keep * (1 - COMMISSION) - TRANSPORT_PER_QTL_KM * DIST_KM[market] - a["store"] * h


def score(df, comm, med_col, lo_col, lam):
    nm = np.array([net_value(p, comm, m, h) for p, m, h in zip(df[med_col], df["market"], df["h"])])
    nl = np.array([net_value(p, comm, m, h) for p, m, h in zip(df[lo_col], df["market"], df["h"])])
    return nm - lam * (nm - nl)       # risk-adjusted: penalise gap to worst case


def recommend(comm, qty, price_now, latest, lam=0.5):
    rows = []
    for m in MARKETS:
        rows.append((m, 0, price_now[m], price_now[m]))
        for h in HORIZONS:
            lo, med, hi = latest[(m, h)]
            rows.append((m, h, lo, med))
    df = pd.DataFrame(rows, columns=["market", "h", "p_lo", "p_med"])
    df["exp_net_per_qtl"] = [net_value(p, comm, m, h) for p, m, h in zip(df.p_med, df.market, df.h)]
    df["worst_net_per_qtl"] = [net_value(p, comm, m, h) for p, m, h in zip(df.p_lo, df.market, df.h)]
    df["risk_score"] = df.exp_net_per_qtl - lam * (df.exp_net_per_qtl - df.worst_net_per_qtl)
    df["expected_total_Rs"] = df.exp_net_per_qtl * qty
    df = df.rename(columns={"h": "sell_after_days"})
    return df.sort_values("risk_score", ascending=False).round(1).reset_index(drop=True)


def build_options(fc, d):
    rows = []
    for m in MARKETS:
        pn = fc[(m, 7)]["out"].loc[d, "price_now"]
        rows.append(dict(market=m, h=0, p_lo=pn, p_med=pn, p_naive=pn, actual=pn))
        for h in HORIZONS:
            r = fc[(m, h)]["out"].loc[d]
            rows.append(dict(market=m, h=h, p_lo=r["p_lo"], p_med=r["p_med"],
                             p_naive=r["price_now"], actual=r["actual"]))
    return pd.DataFrame(rows)


def backtest(comm, fc, lam=0.5, step=7):
    dates = None
    for v in fc.values():
        idx = v["out"].index
        dates = idx if dates is None else dates.intersection(idx)
    dates = dates[::step]

    strategies = {
        "Proposed (forecast + risk-aware)": ("p_med", "p_lo", lam),
        "Median forecast (no risk term)":   ("p_med", "p_lo", 0.0),
        "Naive (no forecast)":              ("p_naive", "p_naive", 0.0),
    }
    res = {k: [] for k in strategies}
    res["Sell now at home"] = []
    res["Oracle (perfect hindsight)"] = []

    for d in dates:
        opts = build_options(fc, d)
        real = np.array([net_value(a, comm, m, h)
                         for a, m, h in zip(opts["actual"], opts["market"], opts["h"])])
        for name, (med, lo, l) in strategies.items():
            sc = score(opts, comm, med, lo, l)
            res[name].append(real[int(np.argmax(sc))])
        home_i = opts[(opts["market"] == HOME) & (opts["h"] == 0)].index[0]
        res["Sell now at home"].append(real[home_i])
        res["Oracle (perfect hindsight)"].append(real.max())

    oracle = np.mean(res["Oracle (perfect hindsight)"])
    home = np.mean(res["Sell now at home"])
    rows = []
    for k, v in res.items():
        v = np.array(v)
        rows.append({"strategy": k, "commodity": comm,
                     "avg_net_Rs_per_qtl": v.mean(),
                     "p10_net_Rs_per_qtl": np.percentile(v, 10),
                     "regret_vs_oracle": oracle - v.mean(),
                     "uplift_vs_sell_now_%": (v.mean() / home - 1) * 100,
                     "n_decisions": len(v)})
    return pd.DataFrame(rows)