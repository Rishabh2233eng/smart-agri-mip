from src.live import get_price

c = input("Commodity (Wheat / Onion / Tomato): ").strip()
m = input("Market or district: ").strip()
r = get_price(c, m)
if r is None:
    print("No price found in the live API or the database for that crop and market.")
else:
    tag = "LIVE" if r["is_live"] else f"NOT LIVE - {r['age_days']} days old"
    print(f"{c} at {r['market']}: Rs {r['price']:.0f} per quintal  [{tag}]")
    print(f"price date: {r['date']} | source: {r['source']}")