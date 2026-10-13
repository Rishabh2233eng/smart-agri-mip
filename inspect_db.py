import sys
import pandas as pd
from src import db

crop = sys.argv[1] if len(sys.argv) > 1 else "Wheat"
con = db.connect()
q = pd.read_sql_query(
    "SELECT state, district, market, COUNT(*) AS rows_n, ROUND(AVG(modal_price)) AS avg_price "
    "FROM prices WHERE lower(commodity)=? GROUP BY state, district, market "
    "ORDER BY rows_n DESC LIMIT 25", con, params=(crop.lower(),))
con.close()
print(q.to_string(index=False))
