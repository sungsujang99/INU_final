# stats.py
import sqlite3, csv, io, datetime as dt
from db import DB_NAME

def _parse(dstr:str, end=False):
    d = dt.datetime.strptime(dstr, "%Y-%m-%d")
    return d if not end else d.replace(hour=23, minute=59, second=59)

# ─────────────────────────────────────────────
def fetch_logs(date_from:str, date_to:str):
    """모든 product_logs 레코드 (dict list)"""
    s, e = _parse(date_from), _parse(date_to, True)
    con = sqlite3.connect(DB_NAME); cur = con.cursor()
    cur.execute("""
        SELECT product_code, product_name, rack, slot,
               movement_type, quantity, cargo_owner, timestamp
          FROM product_logs
         WHERE timestamp BETWEEN ? AND ?
         ORDER BY timestamp
    """, (s.isoformat(), e.isoformat()))
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close(); return rows

def logs_to_csv(rows:list[dict]) -> str:
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows); return buf.getvalue()
