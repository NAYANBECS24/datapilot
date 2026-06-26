import os
import csv
import io
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional

import pandas as pd

from tools.db_manager import DatabaseManager, get_db_manager, validate_query

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def execute_query(db_path: Optional[str] = None, sql: str = "", conn_str: Optional[str] = None) -> Dict[str, Any]:
    if conn_str and not conn_str.lower().startswith("sqlite"):
        mgr = DatabaseManager(conn_str)
    elif db_path:
        mgr = DatabaseManager(f"sqlite:///{db_path}")
    else:
        mgr = get_db_manager()

    check = validate_query(sql)
    if not check["valid"]:
        return {"success": False, "sql": sql, "error": check["reason"]}

    safe_sql = check["sql"]

    if mgr.db_type == "sqlite":
        db_file = db_path or mgr.params.get("database", "")
        return _sqlite_execute(db_file, safe_sql)
    else:
        return mgr.execute_query(sql)


def _sqlite_execute(db_path: str, sql: str) -> Dict[str, Any]:
    import time
    start = time.perf_counter()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        uploads_db = os.path.join(os.path.dirname(db_path), "uploads", "uploads.db") if db_path else ""
        if uploads_db and os.path.exists(uploads_db):
            try:
                conn.execute(f"ATTACH DATABASE '{uploads_db}' AS uploads")
            except Exception:
                pass

        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "success": True, "sql": sql, "columns": columns,
            "rows": [dict(r) for r in rows], "row_count": len(rows), "latency_ms": latency_ms,
        }
    except sqlite3.Error as e:
        return {"success": False, "sql": sql, "error": str(e)}


def csv_to_table(file_path: str, table_name: str) -> Dict[str, Any]:
    try:
        db_path = os.path.join(UPLOADS_DIR, "uploads.db")
        df = pd.read_csv(file_path)
        if df.empty:
            return {"success": False, "error": "CSV file is empty."}
        conn = sqlite3.connect(db_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.close()
        return {"success": True, "table_name": table_name, "columns": list(df.columns), "row_count": len(df)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_uploaded_tables() -> Dict[str, Any]:
    db_path = os.path.join(UPLOADS_DIR, "uploads.db")
    if not os.path.exists(db_path):
        return {"success": True, "tables": []}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        tables = [row[0] for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        result = []
        for table in tables:
            columns = [col[1] for col in cur.execute(f"PRAGMA table_info('{table}')").fetchall()]
            count = cur.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]
            result.append({"table_name": table, "columns": columns, "row_count": count})
        conn.close()
        return {"success": True, "tables": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def import_db_file(db_path: str, label: str = "") -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {"success": False, "error": "File not found."}
    try:
        src = sqlite3.connect(db_path)
        src_cur = src.cursor()
        tables = [row[0] for row in src_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        if not tables:
            src.close()
            return {"success": False, "error": "No tables found in database."}

        dst_path = os.path.join(UPLOADS_DIR, "uploads.db")
        dst = sqlite3.connect(dst_path)
        dst_cur = dst.cursor()

        imported = []
        for table in tables:
            safe_name = f"{label}_{table}" if label else table
            safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in safe_name)
            dst_cur.execute(f"DROP TABLE IF EXISTS \"{safe_name}\"")
            src_cur.execute(f"SELECT * FROM \"{table}\"")
            rows = src_cur.fetchall()
            col_names = [d[0] for d in src_cur.description]
            col_defs = ", ".join(f'"{c}" TEXT' for c in col_names)
            dst_cur.execute(f"CREATE TABLE \"{safe_name}\" ({col_defs})")
            placeholders = ", ".join("?" for _ in col_names)
            dst_cur.executemany(f"INSERT INTO \"{safe_name}\" VALUES ({placeholders})", rows)
            dst.commit()
            imported.append({"original": table, "as": safe_name, "row_count": len(rows)})

        src.close()
        dst.close()
        return {"success": True, "tables": imported}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clear_uploads():
    db_path = os.path.join(UPLOADS_DIR, "uploads.db")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass
    for f in os.listdir(UPLOADS_DIR):
        if f.endswith(".csv"):
            try:
                os.remove(os.path.join(UPLOADS_DIR, f))
            except PermissionError:
                pass
    for f in os.listdir(UPLOADS_DIR):
        if f.endswith(".csv"):
            try:
                os.remove(os.path.join(UPLOADS_DIR, f))
            except PermissionError:
                pass


if __name__ == "__main__":
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")

    print("-- valid query --")
    print(json.dumps(execute_query(path, "SELECT name, category, price FROM products ORDER BY price DESC"), indent=2)[:600])

    print("\n-- blocked query --")
    print(json.dumps(execute_query(path, "DELETE FROM orders"), indent=2))

    print("\n-- broken query --")
    print(json.dumps(execute_query(path, "SELECT namee FROM products"), indent=2))

    print("\n-- connection string --")
    print(json.dumps(execute_query(conn_str=f"sqlite:///{path}", sql="SELECT COUNT(*) as cnt FROM customers"), indent=2))
