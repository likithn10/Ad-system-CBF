# check_dbs.py
import sqlite3
from pathlib import Path

candidates = ["users.db", "ads.db", "data/user_data.db", "data/user_data.sqlite"]
for p in candidates:
    path = Path(p)
    print("\n---", p, "->", path.resolve())
    if not path.exists():
        print("  (missing)")
        continue
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        print("  tables:", cur.fetchall())
        conn.close()
    except Exception as e:
        print("  error:", e)
