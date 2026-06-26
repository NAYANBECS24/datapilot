import os
import sqlite3
from typing import Any, Dict


def get_schema(db_path: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        tables = [
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]

        schema: Dict[str, Any] = {"tables": {}, "relationships": []}

        for table in tables:
            columns = []
            for col in cur.execute(f"PRAGMA table_info('{table}')").fetchall():
                columns.append(
                    {"name": col[1], "type": col[2], "primary_key": bool(col[5])}
                )

            fks = []
            for fk in cur.execute(f"PRAGMA foreign_key_list('{table}')").fetchall():
                fks.append(
                    {
                        "column": fk[3],
                        "references_table": fk[2],
                        "references_column": fk[4],
                    }
                )
                schema["relationships"].append(
                    {"from_table": table, "to_table": fk[2], "via": fk[3]}
                )

            schema["tables"][table] = {"columns": columns, "foreign_keys": fks}

        conn.close()

        uploads_db = os.path.join(os.path.dirname(db_path), "uploads", "uploads.db")
        if os.path.exists(uploads_db):
            try:
                uconn = sqlite3.connect(uploads_db)
                ucur = uconn.cursor()
                utables = [
                    row[0]
                    for row in ucur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                for table in utables:
                    ucolumns = []
                    for col in ucur.execute(f"PRAGMA table_info('{table}')").fetchall():
                        ucolumns.append(
                            {"name": col[1], "type": col[2], "primary_key": bool(col[5])}
                        )
                    schema["tables"][f"uploads.{table}"] = {
                        "columns": ucolumns,
                        "foreign_keys": [],
                        "uploaded": True,
                    }
                uconn.close()
            except Exception:
                pass

        return {"success": True, "schema": schema}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import json

    path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")
    print(json.dumps(get_schema(path), indent=2))
