"""Quantile GBM + rolling (adaptive) conformal calibration. Predicts h-day log return."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_features(s, h):
    lp = np.log(s["modal_price"])
    arr = s["arrivals_qtl"]
    X = pd.DataFrame(index=s.index)
    for l in (1, 2, 3, 7, 14, 28):
        X[f"ret_lag{l}"] = lp - lp.shift(l)
    X["dev_ma7"] = lp - lp.rolling(7).mean()
    X["dev_ma30"] = lp - lp.rolling(30).mean()
    X["vol7"] = lp.diff().rolling(7).std()
    X["arr_ratio"] = np.log1p(arr) - np.log1p(arr.rolling(30).mean())
    X["rain7"] = s["rainfall_mm"].rolling(7).sum()
    X["rain14"] = s["rainfall_mm"].rolling(14).sum()
    doy = s.index.dayofyear
    X["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    X["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    y = lp.shift(-h) - lp
    return X, y


class QuantileGBM:
    def __init__(self, alpha=0.2):
        self.alpha = alpha
        self.q_lo, self.q_hi = alpha / 2, 1 - alpha / 2

    def _gbm(self, q):
        return GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=150,
                                         max_depth=3, learning_rate=0.05,
                                         subsample=0.8, random_state=0)

    def fit(self, X, y):
        self.m = {q: self._gbm(q).fit(X, y) for q in (self.q_lo, 0.5, self.q_hi)}
        return self

    def raw(self, X):
        lo, med, hi = (self.m[self.q_lo].predict(X), self.m[0.5].predict(X),
                       self.m[self.q_hi].predict(X))
        return np.minimum(lo, med), med, np.maximum(hi, med)


def conformal_q(scores, alpha):
    n = len(scores)
    if n == 0:
        return 0.0
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level))


def split_dates(index, f1=0.6, f2=0.8):
    n = len(index)
    return index[int(f1 * n)], index[int(f2 * n)]


def run_forecasts(s, h, alpha=0.2, window=90):
    X, y = build_features(s, h)
    T1, T2 = split_dates(s.index)
    gap = pd.Timedelta(days=h)
    ok = np.isfinite(X).all(axis=1)
    known = ok & y.notna()
    tr = known & (X.index < T1 - gap)
    ev = known & (X.index >= T1)          # calibration + test pool
    te = known & (X.index >= T2)
    if tr.sum() < 100 or te.sum() < 30:
        raise ValueError("Series too short for this split (need roughly 400+ days).")

    gbm = QuantileGBM(alpha).fit(X[tr], y[tr])
    lo_e, med_e, hi_e = gbm.raw(X[ev])
    y_e = y[ev].values
    sc = pd.Series(np.maximum(lo_e - y_e, y_e - hi_e), index=X.index[ev])

    def qhat_at(t):
        """Conformal margin from the most recent `window` days of scores already resolved at time t."""
        avail = sc[(sc.index <= t - gap) & (sc.index > t - gap - pd.Timedelta(days=window))]
        if len(avail) < 20:
            avail = sc[sc.index <= t - gap]
        return conformal_q(avail.values, alpha)

    q_static = conformal_q(sc[sc.index < T2 - gap].values, alpha)   # Day-1 style, for ablation
    in_te = X.index[ev] >= T2
    idx = X.index[te]
    qh = np.array([qhat_at(t) for t in idx])
    lo_t, med_t, hi_t = lo_e[in_te], med_e[in_te], hi_e[in_te]

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X[tr], y[tr])
    rf = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, n_jobs=-1,
                               random_state=0).fit(X[tr], y[tr])
    pn = s["modal_price"][te].values
    out = pd.DataFrame({
        "price_now": pn,
        "actual": s["modal_price"].shift(-h)[te].values,
        "p_naive": pn,
        "p_ridge": pn * np.exp(ridge.predict(X[te])),
        "p_rf": pn * np.exp(rf.predict(X[te])),
        "p_lo": pn * np.exp(lo_t - qh),
        "p_med": pn * np.exp(med_t),
        "p_hi": pn * np.exp(hi_t + qh),
        "p_lo_s": pn * np.exp(lo_t - q_static),
        "p_hi_s": pn * np.exp(hi_t + q_static),
    }, index=idx)

    l2, m2, h2 = gbm.raw(X.iloc[[-1]])
    q = qhat_at(X.index[-1])
    p0 = float(s["modal_price"].iloc[-1])
    last = (p0, p0 * np.exp(l2[0] - q), p0 * np.exp(m2[0]), p0 * np.exp(h2[0] + q))
    return {"out": out, "model": gbm, "last": last}


def metrics(out):
    a = out["actual"]
    res = {"n_test": len(out)}
    for name, col in [("naive", "p_naive"), ("ridge", "p_ridge"), ("rf", "p_rf"), ("gbm", "p_med")]:
        res[f"MAE_{name}"] = float((a - out[col]).abs().mean())
        res[f"MAPE_{name}"] = float(((a - out[col]).abs() / a).mean() * 100)
    res["cov_rolling_%"] = float(((a >= out["p_lo"]) & (a <= out["p_hi"])).mean() * 100)
    res["cov_static_%"] = float(((a >= out["p_lo_s"]) & (a <= out["p_hi_s"])).mean() * 100)
    res["width_%"] = float(((out["p_hi"] - out["p_lo"]) / out["p_med"]).mean() * 100)
    return res