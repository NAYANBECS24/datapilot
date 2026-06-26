import os
from typing import Any, Dict, Optional

from tools.db_manager import DatabaseManager, get_db_manager


def get_schema(db_path: Optional[str] = None, conn_str: Optional[str] = None) -> Dict[str, Any]:
    if conn_str:
        mgr = DatabaseManager(conn_str)
    elif db_path:
        mgr = DatabaseManager(f"sqlite:///{db_path}")
    else:
        mgr = get_db_manager()

    result = mgr.get_schema()

    if result.get("success") and result["schema"].get("tables"):
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

            uploads_db = os.path.join(os.path.dirname(db_path), "uploads", "uploads.db")
            if os.path.exists(uploads_db):
                try:
                    uconn = sqlite3.connect(uploads_db)
                    ucur = uconn.cursor()
                    utables = [
                        row[0] for row in ucur.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                        ).fetchall()
                    ]
                    for table in utables:
                        ucolumns = []
                        for col in ucur.execute(f"PRAGMA table_info('{table}')").fetchall():
                            ucolumns.append({"name": col[1], "type": col[2], "primary_key": bool(col[5])})
                        schema["tables"][f"uploads.{table}"] = {"columns": ucolumns, "foreign_keys": [], "uploaded": True}
                    uconn.close()
                except Exception:
                    pass

            return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return result


if __name__ == "__main__":
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")
    print(json.dumps(get_schema(path), indent=2))
