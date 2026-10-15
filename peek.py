import sys, pandas as pd
p = sys.argv[1]
df = pd.read_excel(p) if p.lower().endswith(("xlsx", "xls")) else pd.read_csv(p, low_memory=False)
print("rows:", len(df))
print("columns:", list(df.columns))
print(df.head(3).to_string())
