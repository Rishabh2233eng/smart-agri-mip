# Edit this file to change markets, crops and cost assumptions.
HOME = "Faridabad"
MARKETS = ["Faridabad", "Azadpur", "Ghazipur"]
COMMODITIES = ["Wheat", "Tomato", "Onion"]

# how names appear in your downloaded CSV (lowercase)
ALIASES = {"Wheat": ["wheat"], "Tomato": ["tomato"], "Onion": ["onion"]}          # exact match
MARKET_ALIASES = {"Faridabad": ["faridabad"], "Azadpur": ["azadpur"], "Ghazipur": ["ghazipur"]}  # contains

# ---- COST ASSUMPTIONS: placeholders, replace with sourced values before the paper ----
DIST_KM = {"Faridabad": 0, "Azadpur": 45, "Ghazipur": 50}
TRANSPORT_PER_QTL_KM = 0.5      # Rs per quintal per km
COMMISSION = 0.02               # fraction of sale value
ASSUMP = {                      # spoil = fraction lost per day, store = Rs per quintal per day
    "Wheat":  dict(spoil=0.0002, store=0.5),
    "Tomato": dict(spoil=0.015,  store=3.0),
    "Onion":  dict(spoil=0.002,  store=1.0),
}