"""Runs the forecasting + decision pipeline on the labelled SIMULATION (no real history yet).
Once real history is loaded, run run_day2.py instead."""
import src.db as db
import src.realdata as rd

db.load_from_db = lambda *a, **k: None
rd.load_real = lambda *a, **k: None
exec(compile(open("run_day2.py", encoding="utf-8").read(), "run_day2.py", "exec"), {"__name__": "__main__"})
