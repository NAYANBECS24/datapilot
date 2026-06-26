import os
import re
import sqlite3
import tempfile
import time
from typing import Any, Dict

import pandas as pd

BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "replace",
)

DEFAULT_ROW_LIMIT = 200

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def validate_query(sql: str) -> Dict[str, Any]:
    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()

    if not lowered.startswith("select") and not lowered.startswith("with"):
        return {"valid": False, "reason": "Only read-only SELECT/WITH queries are permitted.", "sql": cleaned}

    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            return {
                "valid": False,
                "reason": f"Query contains a blocked keyword: '{kw}'. Only read-only queries are allowed.",
                "sql": cleaned,
            }

    if "limit" not in lowered:
        cleaned = f"{cleaned} LIMIT {DEFAULT_ROW_LIMIT}"

    return {"valid": True, "reason": None, "sql": cleaned}


def csv_to_table(file_path: str, table_name: str) -> Dict[str, Any]:
    try:
        db_path = os.path.join(UPLOADS_DIR, "uploads.db")
        df = pd.read_csv(file_path)
        if df.empty:
            return {"success": False, "error": "CSV file is empty."}
        conn = sqlite3.connect(db_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.close()
        return {
            "success": True,
            "table_name": table_name,
            "columns": list(df.columns),
            "row_count": len(df),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_uploaded_tables() -> Dict[str, Any]:
    db_path = os.path.join(UPLOADS_DIR, "uploads.db")
    if not os.path.exists(db_path):
        return {"success": True, "tables": []}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        tables = [
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        result = []
        for table in tables:
            columns = [col[1] for col in cur.execute(f"PRAGMA table_info('{table}')").fetchall()]
            count = cur.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]
            result.append({"table_name": table, "columns": columns, "row_count": count})
        conn.close()
        return {"success": True, "tables": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_query(db_path: str, sql: str) -> Dict[str, Any]:
    check = validate_query(sql)
    if not check["valid"]:
        return {"success": False, "sql": sql, "error": check["reason"]}

    safe_sql = check["sql"]
    start = time.perf_counter()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        uploads_db = os.path.join(UPLOADS_DIR, "uploads.db")
        if os.path.exists(uploads_db):
            conn.execute(f"ATTACH DATABASE '{uploads_db}' AS uploads")
        cur = conn.cursor()
        cur.execute(safe_sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "success": True,
            "sql": safe_sql,
            "columns": columns,
            "rows": [dict(r) for r in rows],
            "row_count": len(rows),
            "latency_ms": latency_ms,
        }
    except sqlite3.Error as e:
        return {"success": False, "sql": safe_sql, "error": str(e)}


def clear_uploads():
    db_path = os.path.join(UPLOADS_DIR, "uploads.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    for f in os.listdir(UPLOADS_DIR):
        if f.endswith(".csv"):
            os.remove(os.path.join(UPLOADS_DIR, f))


if __name__ == "__main__":
    import json

    path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")

    print("-- valid query --")
    print(json.dumps(execute_query(path, "SELECT name, category, price FROM products ORDER BY price DESC"), indent=2)[:600])

    print("\n-- blocked query --")
    print(json.dumps(execute_query(path, "DELETE FROM orders"), indent=2))

    print("\n-- broken query --")
    print(json.dumps(execute_query(path, "SELECT namee FROM products"), indent=2))
