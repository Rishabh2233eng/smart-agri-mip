import requests, os
H = {"User-Agent": "Mozilla/5.0"}
os.makedirs("data/real", exist_ok=True)
for folder in ["data", "raw"]:
    r = requests.get(f"https://api.github.com/repos/amitkaps/onions-dataset/contents/{folder}", headers=H, timeout=30)
    print(folder, "HTTP", r.status_code)
    if r.status_code != 200:
        continue
    for f in r.json():
        print("  ", f["name"], f.get("size"))
        if f["name"].lower().endswith(".csv") and f.get("download_url"):
            d = requests.get(f["download_url"], headers=H, timeout=60)
            open(f"data/real/onions_{f['name']}", "wb").write(d.content)
            print("     saved ->", f"data/real/onions_{f['name']}")
