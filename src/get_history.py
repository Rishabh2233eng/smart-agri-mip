import requests, sys, os
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
os.makedirs("data/real", exist_ok=True)
CANDIDATES = [
 ("github-onions-monthly", "https://raw.githubusercontent.com/amitkaps/onions-dataset/master/data/MonthWiseMarketArrivals.csv"),
 ("github-onions-daily?",  "https://raw.githubusercontent.com/amitkaps/onions-dataset/master/data/onion.csv"),
]
extra = sys.argv[1:]            # you can pass your own URLs: python get_history.py <url> <url>
CANDIDATES += [(f"user{i}", u) for i, u in enumerate(extra)]
for name, url in CANDIDATES:
    try:
        r = requests.get(url, headers=H, timeout=(8, 30))
        ok = r.status_code == 200 and len(r.content) > 500
        print(f"{name:24} HTTP {r.status_code:3}  {len(r.content):>9} bytes  {'SAVED' if ok else 'skip'}")
        if ok:
            open(f"data/real/{name}.csv", "wb").write(r.content)
    except Exception as e:
        print(f"{name:24} FAILED: {type(e).__name__}")