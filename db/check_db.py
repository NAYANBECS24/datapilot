"""Quick DB structure check."""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), "sample_ecommerce.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

print(f"Database: {db}")
print(f"Tables ({len(tables)}): {', '.join(tables)}\n")

for t in tables:
    cur.execute(f'PRAGMA table_info("{t}")')
    cols = cur.fetchall()
    print(f"  {t}:")
    for c in cols:
        pk = " PK" if c[5] else ""
        print(f"    {c[1]} ({c[2]}){pk}")
    cur.execute(f'PRAGMA foreign_key_list("{t}")')
    fks = cur.fetchall()
    for fk in fks:
        print(f"    FK: {fk[3]} → {fk[2]}({fk[4]})")
    print()

conn.close()

print("=" * 50)
print("Sample queries that work:")
print("  SELECT COUNT(*) FROM orders")
print("  SELECT name, price FROM products ORDER BY price DESC LIMIT 5")
print("  SELECT o.order_id, c.name FROM orders o JOIN customers c ON o.customer_id = c.customer_id")
