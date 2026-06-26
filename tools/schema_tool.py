import os
from typing import Any, Dict, Optional

from tools.db_manager import DatabaseManager, get_db_manager


def get_schema(db_path: Optional[str] = None, conn_str: Optional[str] = None, username: str = "") -> Dict[str, Any]:
    if conn_str and not conn_str.lower().startswith("sqlite"):
        mgr = DatabaseManager(conn_str)
    elif db_path:
        mgr = DatabaseManager(f"sqlite:///{db_path}")
    else:
        mgr = get_db_manager()

    result = mgr.get_schema()

    if result.get("success") and result["schema"].get("tables"):
        _merge_uploads(result, db_path, username)
        return result

    if not db_path and not conn_str:
        return result

    if not result.get("success") and db_path:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            tables = [
                row[0] for row in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]

            schema: Dict[str, Any] = {"tables": {}, "relationships": []}

            for table in tables:
                columns = []
                for col in cur.execute(f"PRAGMA table_info('{table}')").fetchall():
                    columns.append({"name": col[1], "type": col[2], "primary_key": bool(col[5])})

                for fk in cur.execute(f"PRAGMA foreign_key_list('{table}')").fetchall():
                    schema["relationships"].append({"from_table": table, "to_table": fk[2], "via": fk[3]})

                schema["tables"][table] = {"columns": columns, "foreign_keys": []}

            conn.close()
            _merge_uploads(schema, db_path, username)
            return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return result


def _merge_uploads(result: Dict[str, Any], db_path: Optional[str] = None, username: str = ""):
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        candidates = []
        if username.strip():
            candidates.append(os.path.join(base_dir, "uploads", username.strip().lower(), "uploads.db"))
        candidates.append(os.path.join(base_dir, "uploads", "shared", "uploads.db"))

        schema = result["schema"]
        for uploads_db in candidates:
            if not os.path.exists(uploads_db):
                continue
            import sqlite3
            uconn = sqlite3.connect(uploads_db)
            ucur = uconn.cursor()
            utables = [
                row[0] for row in ucur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            prefix = "uploads." if "shared" in uploads_db else "my."
            for table in utables:
                ucolumns = []
                for col in ucur.execute(f"PRAGMA table_info('{table}')").fetchall():
                    ucolumns.append({"name": col[1], "type": col[2], "primary_key": bool(col[5])})
                schema["tables"][f"{prefix}{table}"] = {"columns": ucolumns, "foreign_keys": [], "uploaded": True}
            uconn.close()
    except Exception:
        pass
