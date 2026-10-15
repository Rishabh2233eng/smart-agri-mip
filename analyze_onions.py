import pandas as pd, glob
df = pd.concat([pd.read_csv(p, low_memory=False) for p in sorted(glob.glob("data/real/onions_*.csv"))])
df.columns = ["date", "market", "arrivals", "pmin", "pmax", "modal"]
df["date"] = pd.to_datetime(df["date"], format="%d/%b/%Y", errors="coerce")
for c in ["arrivals", "pmin", "pmax", "modal"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["date", "modal"]).drop_duplicates(["date", "market"])
print("rows:", len(df), "| dates:", df.date.min().date(), "to", df.date.max().date())
print("months present:", sorted(df.date.dt.to_period("M").astype(str).unique()))
g = df.groupby("market").agg(days=("date", "nunique"), first=("date", "min"), last=("date", "max"))
print("\nTop 15 markets by days:")
print(g.sort_values("days", ascending=False).head(15).to_string())
print("\nDelhi/Haryana/UP-NCR markets:")
m = g[g.index.str.contains("DELHI|AZADPUR|GHAZIPUR|FARIDABAD|GURGAON|NOIDA|BALLABH|HAR\\)|\\(HR|\\(DEL", case=False, regex=True)]
print(m.to_string() if len(m) else "none found")
df.to_csv("data/real/onions_all_clean.csv", index=False)
