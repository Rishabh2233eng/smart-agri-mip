import pandas as pd, glob
for p in sorted(glob.glob("data/real/onions_*.csv")):
    df = pd.read_csv(p, low_memory=False)
    print("\n==", p, len(df), "rows")
    print("columns:", list(df.columns))
    print(df.head(3).to_string())
    for c in df.columns:
        if any(k in c.lower() for k in ("market", "center", "state", "city")):
            print(c, "->", df[c].nunique(), "unique; sample:", list(df[c].astype(str).unique()[:12]))
        if "date" in c.lower():
            print(c, "range:", df[c].astype(str).min(), "to", df[c].astype(str).max())
