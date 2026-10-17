"""Pipeline health check. Run: python doctor.py   then paste the output to Claude."""
import sys, os, subprocess, importlib, time, traceback
fails = 0
def ok(m): print("  [ OK ]", m)
def bad(m, fix=""):
    global fails; fails += 1
    print("  [FAIL]", m); 
    if fix: print("         fix:", fix)
def head(t): print("\n==", t)

head("Python and packages")
ok(sys.version.split()[0])
for mod in ["numpy", "pandas", "sklearn", "matplotlib", "requests", "dotenv", "streamlit", "openpyxl"]:
    try:
        m = importlib.import_module(mod); ok(f"{mod} {getattr(m, '__version__', '')}")
    except Exception:
        bad(f"{mod} missing", "pip install -r requirements.txt")

head("API key and live feed")
KEY = None
try:
    from dotenv import load_dotenv; load_dotenv(); KEY = os.getenv("DATAGOV_API_KEY")
    rid = os.getenv("DATAGOV_RESOURCE_ID")
    ok("DATAGOV_API_KEY found") if KEY and len(KEY) > 10 else bad("DATAGOV_API_KEY missing in .env", "add DATAGOV_API_KEY=your_key to .env")
    if rid and rid != "9ef84268-d588-465a-a308-a864a43d0070":
        bad(f"DATAGOV_RESOURCE_ID in .env is {rid} (not the mandi dataset)", "delete that line from .env")
    import requests
    r = requests.get("https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
                     params={"api-key": KEY, "format": "json", "limit": 1}, timeout=(8, 40),
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"})
    ok(f"feed HTTP {r.status_code}, total {r.json().get('total')}") if r.status_code == 200 else bad(f"feed HTTP {r.status_code}", "check the key or retry later")
except Exception as e:
    bad(f"feed check failed: {type(e).__name__}", "check internet; retry")

head("Database")
try:
    import dbinfo
    if not dbinfo.available(): bad("data/mandi.db not found", "python collect_all.py")
    else:
        s = dbinfo.summary(); ok(f"{s['rows']:,} rows, {s['commodities']} commodities, {s['markets']} markets, {s['days']} days, {s['first']} to {s['last']}")
        if s["days"] < 2: bad("only 1 day collected", "the nightly job is not adding days: see Scheduled task below")
except Exception:
    bad("database check failed: " + traceback.format_exc().strip().splitlines()[-1])

head("Data files")
for d, label in [("data/real", "history CSVs"), ("data/weather", "weather CSVs")]:
    n = len([f for f in os.listdir(d)]) if os.path.isdir(d) else 0
    ok(f"{label}: {n} files") if n else bad(f"no {label} in {d}", "python get_history.py  /  python weather.py")

head("Code imports")
for mod in ["src.config", "src.data", "src.forecast", "src.decision", "src.db", "src.casestudy"]:
    try: importlib.import_module(mod); ok(mod)
    except Exception: bad(f"{mod}: " + traceback.format_exc().strip().splitlines()[-1])

head("Forecast smoke test (one market, 7 day)")
try:
    t0 = time.time()
    from src import casestudy
    S, crops, missing = casestudy.setup()
    if not crops: bad("no crop passed the data checks", "check data/real files and ASSUMP in src/config.py")
    else:
        from src.forecast import run_forecasts, metrics
        import src.config as C
        k = (crops[0], C.HOME); o = run_forecasts(S[k], 7)["out"]
        ok(f"{k} -> {len(o)} test rows, {metrics(o)}  ({time.time()-t0:.0f}s)")
except Exception:
    bad("forecast failed: " + traceback.format_exc().strip().splitlines()[-1])

head("Scheduled task and log")
try:
    q = subprocess.run(["schtasks", "/Query", "/TN", "mandi_snapshot", "/FO", "LIST", "/V"], capture_output=True, text=True)
    for line in q.stdout.splitlines():
        if any(x in line for x in ("Task To Run", "Last Result", "Last Run Time", "Next Run Time", "Status:")): print("  ", line.strip())
    if "collect_all.py" not in q.stdout: bad("task does not run collect_all.py", "see the Set-ScheduledTask command")
except Exception: print("   (could not query the task)")
if os.path.exists("snapshot.log"):
    print("  last log lines:"); [print("    ", l.rstrip()) for l in open("snapshot.log", errors="ignore").readlines()[-3:]]

print(f"\n{'ALL CHECKS PASSED' if not fails else str(fails) + ' PROBLEM(S) FOUND'}")
