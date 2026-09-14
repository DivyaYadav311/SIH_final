import sqlite3
import json

con = sqlite3.connect("data/p6_control_tower/p6.db")
cur = con.cursor()
tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables in data/p6_control_tower/p6.db:", tables)
for t in tables:
    count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"Table '{t}': {count} rows")
    rows = cur.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
    col_names = [d[0] for d in cur.description]
    print(f"  Columns: {col_names}")
    for r in rows:
        print(f"  Sample row: {r}")

con.close()
