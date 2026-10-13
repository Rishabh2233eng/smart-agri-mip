from src.live import lookup

c = input("Commodity (e.g. Onion / Tomato / Potato / Wheat): ").strip()
m = input("Market or district: ").strip()
s = input("State (optional, press Enter to skip): ").strip() or None
r = lookup(c, m, s)
h = r["hit"]
if h:
    tag = "LIVE" if h["is_live"] else "NOT LIVE - " + str(h["age_days"]) + " days old"
    print(f"\n{c} at {h['market']} ({h['state']}): Rs {h['price']:.0f} per quintal  [{tag}]")
    print(f"price date: {h['date']} | source: {h['source']} | simple average of {h['n_varieties']} variety/grade quote(s)")
    if r["others"]:
        print("\nOther markets in the same state today (highest first, before transport costs):")
        for name, p in r["others"]:
            print(f"  {name}: Rs {p:.0f}")
else:
    if not r["api_ok"]:
        print("\nThe live API could not be reached right now.")
    else:
        print(f"\nNo {c} price for '{m}' in today's feed.")
    if r["stored"]:
        st = r["stored"]
        print(f"Last stored price: Rs {st['price']:.0f} at {st['market']} on {st['date']} ({st['age_days']} days old, NOT LIVE)")
    if r["state_markets"]:
        print(f"\n{c} markets reporting today in {s}:")
        for name, p in r["state_markets"]:
            print(f"  {name}: Rs {p:.0f}")
    elif r["states"]:
        print(f"\n{c} is reported today in these states (markets): " +
              ", ".join(f"{k} ({v})" for k, v in r["states"].items()))
        print("Run again and type one of these states to list its markets.")
    elif r["api_ok"]:
        print(f"{c} is not reported anywhere in today's feed" + (f" for {s}." if s else "."))
