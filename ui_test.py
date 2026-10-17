import sys, os, time
sys.path.insert(0, os.getcwd())
from streamlit.testing.v1 import AppTest
pages = ["views/home.py", "views/live.py", "pages/4_Price_Board.py", "pages/2_Market_Explorer.py",
         "pages/1_Forecast.py", "pages/3_About.py"]
bad = 0
for p in pages:
    t0 = time.time()
    try:
        at = AppTest.from_file(p, default_timeout=900).run()
        errs = [str(e.value)[:400] for e in at.exception]
        notes = [str(e.value)[:150] for e in list(at.error) + list(at.warning)]
        if errs:
            bad += 1; print(f"[FAIL] {p}\n       {errs[0]}")
        else:
            print(f"[ OK ] {p} ({time.time()-t0:.0f}s)" + (f"  notes: {notes[:2]}" if notes else ""))
    except Exception as e:
        bad += 1; print(f"[FAIL] {p}: {type(e).__name__}: {str(e)[:300]}")
print("\nALL PAGES OK" if not bad else f"\n{bad} PAGE(S) FAILING")
