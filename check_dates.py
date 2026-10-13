import time
from collections import Counter
import data_tools as dtl

dtl.need_key()
cnt, offset = Counter(), 0
while True:
    r = dtl.get({"api-key": dtl.KEY, "format": "json", "limit": 500, "offset": offset})
    r.raise_for_status()
    recs = r.json().get("records", [])
    cnt.update(x.get("arrival_date") for x in recs)
    offset += len(recs)
    if len(recs) < 500:
        break
    time.sleep(0.3)
print("records scanned:", offset)
for d, n in sorted(cnt.items(), key=lambda kv: str(kv[0])):
    print(d, n)