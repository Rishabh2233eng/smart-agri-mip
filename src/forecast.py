"""Quantile GBM + conformal calibration (CQR) for h-day-ahead price forecasts."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_features(s, h):
    lp = np.log(s["modal_price"])
    X = pd.DataFrame(index=s.index)
    for l in (1, 2, 3, 7, 14, 28):
        X[f"ret_lag{l}"] = lp - lp.shift(l)
    X["dev_ma7"] = lp - lp.rolling(7).mean()
    X["dev_ma30"] = lp - lp.rolling(30).mean()
    X["vol7"] = lp.diff().rolling(7).std()
    X["arr_ratio"] = np.log(s["arrivals_qtl"] / s["arrivals_qtl"].rolling(30).mean())
    X["rain7"] = s["rainfall_mm"].rolling(7).sum()
    X["rain14"] = s["rainfall_mm"].rolling(14).sum()
    doy = s.index.dayofyear
    X["sin_doy"] = np.sin(2 * np.pi * doy / 365.25)
    X["cos_doy"] = np.cos(2 * np.pi * doy / 365.25)
    y = lp.shift(-h) - lp          # target: h-day log return
    return X, y


class QuantileForecaster:
    def __init__(self, alpha=0.2):          # alpha=0.2 -> 80% interval
        self.alpha = alpha
        self.q_lo, self.q_hi = alpha / 2, 1 - alpha / 2

    def _gbm(self, q):
        return GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=150,
                                         max_depth=3, learning_rate=0.05,
                                         subsample=0.8, random_state=0)

    def _raw(self, X):
        lo = self.m[self.q_lo].predict(X)
        med = self.m[0.5].predict(X)
        hi = self.m[self.q_hi].predict(X)
        return np.minimum(lo, med), med, np.maximum(hi, med)

    def fit(self, Xtr, ytr, Xca, yca):
        self.m = {q: self._gbm(q).fit(Xtr, ytr) for q in (self.q_lo, 0.5, self.q_hi)}
        lo, _, hi = self._raw(Xca)
        y = np.asarray(yca)
        score = np.maximum(lo - y, y - hi)          # conformity scores
        n = len(y)
        level = min(1.0, np.ceil((n + 1) * (1 - self.alpha)) / n)
        self.qhat = float(np.quantile(score, level))
        return self

    def predict(self, X):
        lo, med, hi = self._raw(X)
        return lo - self.qhat, med, hi + self.qhat


def split_dates(index, f1=0.6, f2=0.8):
    n = len(index)
    return index[int(f1 * n)], index[int(f2 * n)]


def run_forecasts(s, h, alpha=0.2):
    X, y = build_features(s, h)
    T1, T2 = split_dates(s.index)
    gap = pd.Timedelta(days=h)                      # avoids target leakage across splits
    ok = X.notna().all(axis=1)
    tr = ok & y.notna() & (X.index < T1 - gap)
    ca = ok & y.notna() & (X.index >= T1) & (X.index < T2 - gap)
    te = ok & y.notna() & (X.index >= T2)

    f = QuantileForecaster(alpha).fit(X[tr], y[tr], X[ca], y[ca])
    lo, med, hi = f.predict(X[te])
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(X[tr], y[tr])
    r = ridge.predict(X[te])

    pn = s["modal_price"][te].values
    out = pd.DataFrame({
        "price_now": pn,
        "actual": s["modal_price"].shift(-h)[te].values,
        "p_naive": pn,
        "p_ridge": pn * np.exp(r),
        "p_lo": pn * np.exp(lo),
        "p_med": pn * np.exp(med),
        "p_hi": pn * np.exp(hi),
    }, index=X.index[te])

    # live forecast from the most recent day
    Xl = X.iloc[[-1]]
    l2, m2, h2 = f.predict(Xl)
    p0 = float(s["modal_price"].iloc[-1])
    last = (p0, p0 * np.exp(l2[0]), p0 * np.exp(m2[0]), p0 * np.exp(h2[0]))
    return {"out": out, "model": f, "last": last}


def metrics(out):
    a = out["actual"]
    res = {}
    for name, col in [("naive", "p_naive"), ("ridge", "p_ridge"), ("gbm", "p_med")]:
        res[f"MAE_{name}"] = float((a - out[col]).abs().mean())
        res[f"MAPE_{name}"] = float(((a - out[col]).abs() / a).mean() * 100)
    res["coverage_%"] = float(((a >= out["p_lo"]) & (a <= out["p_hi"])).mean() * 100)
    res["width_%"] = float(((out["p_hi"] - out["p_lo"]) / out["p_med"]).mean() * 100)
    return res