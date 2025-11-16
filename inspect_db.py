# inspect_db.py
import sqlite3

def inspect_db(db_name):
    print(f"\n--- Inspecting {db_name} ---")
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = c.fetchall()
        print("Tables:", tables)
        for t in tables:
            name = t[0]
            print(f"\nTable: {name}")
            c.execute(f"PRAGMA table_info({name});")
            cols = [c[1] for c in c.fetchall()]
            print("Columns:", cols)
            c.execute(f"SELECT * FROM {name} LIMIT 5;")
            for r in c.fetchall():
                print(r)
        conn.close()
    except Exception as e:
        print("Error opening", db_name, e)

inspect_db("ads.db")
inspect_db("users.db")
