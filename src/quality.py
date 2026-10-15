"""Data-quality checks for mandi quotes."""


def mark_suspect(d, lo=0.5, hi=2.0, min_rows=10):
    """Adds `ref` (median modal price of the same crop and date across markets) and `suspect` (bool).
    Heuristic: a quote more than 2x above or below the median is likely a unit or entry error.
    Needs at least `min_rows` quotes for that crop and date, otherwise nothing is flagged."""
    d = d.copy()
    g = d.groupby(["commodity", "date"])["modal_price"]
    d["ref"] = g.transform("median")
    d["n_rows"] = g.transform("count")
    ratio = d["modal_price"] / d["ref"]
    d["suspect"] = (d["n_rows"] >= min_rows) & ((ratio < lo) | (ratio > hi))
    return d

import pandas as pd

def history_flag(price, hist, k=4.0, min_n=5):
    """Flag a quote far outside this market's own recent prices.
    hist: list/Series of past modal prices for the same crop+market.
    Uses median and MAD, so one earlier bad quote doesn't poison it."""
    h = pd.Series(hist).dropna()
    if len(h) < min_n:
        return None  # not enough history to judge
    med = h.median()
    mad = (h - med).abs().median() or max(med * 0.05, 1.0)
    return abs(price - med) / (1.4826 * mad) > k