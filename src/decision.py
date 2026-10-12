"""Cost-aware, risk-aware sell-timing and market-selection engine."""
import numpy as np
import pandas as pd
from . import config as C

HORIZONS = (7, 14)


def net_value(price, comm, market, h):
    a = C.ASSUMP[comm]
    keep = (1 - a["spoil"]) ** h
    return (price * keep * (1 - C.COMMISSION)
            - C.TRANSPORT_PER_QTL_KM * C.DIST_KM.get(market, 50) - a["store"] * h)


def score(df, comm, med_col, lo_col, lam):
    nm = np.array([net_value(p, comm, m, h) for p, m, h in zip(df[med_col], df["market"], df["h"])])
    nl = np.array([net_value(p, comm, m, h) for p, m, h in zip(df[lo_col], df["market"], df["h"])])
    return nm - lam * (nm - nl)


def recommend(comm, qty, markets, price_now, latest, lam=0.5):
    rows = []
    for m in markets:
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


def build_options(fc, markets, d):
    rows = []
    for m in markets:
        pn = fc[(m, 7)]["out"].loc[d, "price_now"]
        rows.append(dict(market=m, h=0, p_lo=pn, p_med=pn, p_naive=pn, actual=pn))
        for h in HORIZONS:
            r = fc[(m, h)]["out"].loc[d]
            rows.append(dict(market=m, h=h, p_lo=r["p_lo"], p_med=r["p_med"],
                             p_naive=r["price_now"], actual=r["actual"]))
    return pd.DataFrame(rows)


def boot_ci(d, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    means = [rng.choice(d, len(d)).mean() for _ in range(n)]
    return np.percentile(means, [2.5, 97.5])


def backtest(comm, fc, markets, home, lams=(0.0, 0.25, 0.5, 0.75, 1.0), step=7):
    dates = None
    for v in fc.values():
        idx = v["out"].index
        dates = idx if dates is None else dates.intersection(idx)
    dates = dates[::step]
    if len(dates) < 5:
        raise ValueError(f"Too few backtest dates for {comm}")

    naive_name = "Naive (no forecast)"
    names = [naive_name] + [f"Forecast lam={l}" for l in lams]
    res = {n: [] for n in names}
    res["Sell now at home"] = []
    res["Oracle (perfect hindsight)"] = []

    for d in dates:
        opts = build_options(fc, markets, d)
        real = np.array([net_value(a, comm, m, h)
                         for a, m, h in zip(opts["actual"], opts["market"], opts["h"])])
        sc = score(opts, comm, "p_naive", "p_naive", 0.0)
        res[naive_name].append(real[int(np.argmax(sc))])
        for l in lams:
            sc = score(opts, comm, "p_med", "p_lo", l)
            res[f"Forecast lam={l}"].append(real[int(np.argmax(sc))])
        home_i = opts[(opts["market"] == home) & (opts["h"] == 0)].index[0]
        res["Sell now at home"].append(real[home_i])
        res["Oracle (perfect hindsight)"].append(real.max())

    naive = np.array(res[naive_name])
    oracle_mean = np.mean(res["Oracle (perfect hindsight)"])
    home_mean = np.mean(res["Sell now at home"])
    rows = []
    for k, v in res.items():
        v = np.array(v)
        d = v - naive
        lo, hi = boot_ci(d)
        rows.append({"strategy": k, "commodity": comm,
                     "avg_net_Rs_per_qtl": v.mean(),
                     "p10_net_Rs_per_qtl": np.percentile(v, 10),
                     "regret_vs_oracle": oracle_mean - v.mean(),
                     "uplift_vs_sell_now_%": (v.mean() / home_mean - 1) * 100,
                     "gain_vs_naive_Rs": d.mean(),
                     "gain_vs_naive_CI95": f"[{lo:.1f}, {hi:.1f}]",
                     "n_decisions": len(v)})
    return pd.DataFrame(rows)