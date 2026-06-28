import os
import json
import time
from typing import Any, Dict, List, Optional

DB_TYPES = {}

try:
    import sqlite3
    DB_TYPES["sqlite"] = "sqlite3"
except ImportError:
    pass

try:
    import psycopg2
    import psycopg2.extras
    DB_TYPES["postgresql"] = "psycopg2"
except ImportError:
    pass

try:
    import pymysql
    DB_TYPES["mysql"] = "pymysql"
except ImportError:
    pass

try:
    import pymongo
    DB_TYPES["mongodb"] = "pymongo"
except ImportError:
    pass

DEFAULT_ROW_LIMIT = 200
BLOCKED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "attach", "detach", "pragma", "vacuum", "replace",
)


def _auto_quote_values(sql: str) -> str:
    """Auto-quote unquoted string values in WHERE/HAVING/ON clauses.

    Catches the common LLM mistake: WHERE category = Electronics
    and fixes it to: WHERE category = 'Electronics'
    """
    import re

    SQL_KEYWORDS = {
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN',
        'IS', 'NULL', 'AS', 'ON', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
        'CROSS', 'FULL', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
        'UNION', 'ALL', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'EXISTS', 'TRUE', 'FALSE', 'ASC', 'DESC', 'CAST',
    }

    def _needs_quoting(val: str) -> bool:
        if len(val) == 0:
            return False
        if val.startswith("'") or val.startswith('"'):
            return False
        if val.upper() in SQL_KEYWORDS:
            return False
        if val.upper() == "NULL":
            return False
        if "." in val:
            return False
        if re.match(r'^[+-]?\d+(\.\d+)?$', val):
            return False
        if re.match(r'^[+-]?\d+\.\d+[eE][+-]?\d+$', val):
            return False
        return True

    def _quote_op(m):
        lhs = m.group(1)
        op = m.group(2)
        val = m.group(3)
        if _needs_quoting(val):
            return f"{lhs}{op}'{val}'"
        return m.group(0)

    def _quote_in(m):
        before = m.group(1)
        inside = m.group(2)
        after = m.group(3)
        items = [item.strip() for item in inside.split(",")]
        quoted = []
        for item in items:
            if _needs_quoting(item):
                quoted.append(f"'{item}'")
            else:
                quoted.append(item)
        return f"{before}{', '.join(quoted)})"

    operators = r"(=|!=|<>|>=|<=|>|<|LIKE)"
    sql = re.sub(
        rf"(\s+){operators}\s*([\w.]+)",
        _quote_op,
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"(\s+IN\s*\()([^)]+)(\))",
        _quote_in,
        sql,
        flags=re.IGNORECASE,
    )

    return sql


def _expand_aliases(sql: str) -> str:
    """Replace table aliases (T1, T2, p, oi, etc.) with full table names.

    Catches the common LLM mistake: FROM products AS T1 ... WHERE T1.category
    and rewrites to: FROM products ... WHERE products.category

    Also strips the alias from FROM/JOIN clauses so the original
    table name can be used throughout the query.
    """
    import re

    _SKIP = {
        'ON', 'USING', 'WHERE', 'AND', 'OR', 'ORDER', 'GROUP', 'HAVING',
        'LIMIT', 'INNER', 'LEFT', 'RIGHT', 'CROSS', 'OUTER', 'JOIN', 'FULL',
        'WITH', 'SELECT', 'SET', 'BY', 'AS', 'NOT', 'IN', 'LIKE', 'BETWEEN',
        'IS', 'NULL', 'EXISTS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'UNION', 'ALL', 'DISTINCT', 'ASC', 'DESC', 'OFFSET',
    }

    alias_map = {}

    def _drop_as(m):
        kw = m.group(1)
        table = m.group(2)
        alias = m.group(3)
        alias_map[alias] = table
        return f"{kw} {table} "

    sql = re.sub(
        r'\b(FROM|JOIN)\s+(\w+)\s+AS\s+(\w+)\s+',
        _drop_as, sql, flags=re.IGNORECASE,
    )

    def _drop_short(m):
        kw = m.group(1)
        table = m.group(2)
        alias = m.group(3)
        if alias.upper() in _SKIP:
            return m.group(0)
        alias_map[alias] = table
        return f"{kw} {table} "

    sql = re.sub(
        r'\b(FROM|JOIN)\s+(\w+)\s+(\w{1,3})\s+',
        _drop_short, sql, flags=re.IGNORECASE,
    )

    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        sql = re.sub(rf'\b{re.escape(alias)}\.', f'{alias_map[alias]}.', sql)

    return sql


def validate_query(sql: str) -> Dict[str, Any]:
    cleaned = sql.strip().rstrip(";")
    lowered = cleaned.lower()

    if not lowered.startswith("select") and not lowered.startswith("with"):
        return {"valid": False, "reason": "Only read-only SELECT/WITH queries are permitted.", "sql": cleaned}

    import re
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            return {
                "valid": False,
                "reason": f"Query contains a blocked keyword: '{kw}'. Only read-only queries are allowed.",
                "sql": cleaned,
            }

    open_parens = cleaned.count("(")
    close_parens = cleaned.count(")")
    if open_parens != close_parens:
        return {
            "valid": False,
            "reason": f"Unbalanced parentheses ({open_parens} open, {close_parens} close) — the SQL appears incomplete or truncated. Rewrite the complete query with all closing parentheses.",
            "sql": cleaned,
        }

    join_count = len(re.findall(r'\bJOIN\b', cleaned, re.IGNORECASE))
    on_count = len(re.findall(r'\bON\b', cleaned, re.IGNORECASE))
    using_count = len(re.findall(r'\bUSING\b', cleaned, re.IGNORECASE))
    if join_count > on_count + using_count:
        return {
            "valid": False,
            "reason": f"Missing ON/USING clause after JOIN (found {join_count} JOIN(s) but only {on_count + using_count} ON/USING). The SQL appears truncated — write the complete query with all JOIN conditions (e.g. JOIN products ON ...).",
            "sql": cleaned,
        }

    cleaned = _expand_aliases(cleaned)
    cleaned = _auto_quote_values(cleaned)
    lowered = cleaned.lower()

    if "limit" not in lowered:
        cleaned = f"{cleaned} LIMIT {DEFAULT_ROW_LIMIT}"
    else:
        limit_match = re.search(r"\blimit\s+(\d+|(\d+)\s*,\s*(\d+))", lowered)
        if not limit_match:
            return {
                "valid": False,
                "reason": "LIMIT clause found but no valid integer limit value specified (e.g. LIMIT 10). Specify a number after LIMIT.",
                "sql": cleaned,
            }

    return {"valid": True, "reason": None, "sql": cleaned}


def parse_connection_string(conn_str: str) -> Dict[str, Any]:
    if not conn_str or conn_str.lower().startswith("sqlite"):
        db_path = conn_str.split("://", 1)[-1] if "://" in conn_str else conn_str
        if not db_path:
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sample_ecommerce.db")
        return {"type": "sqlite", "database": db_path}

    if conn_str.startswith("postgresql://") or conn_str.startswith("postgres://"):
        parts = conn_str.split("://", 1)[1].split("@")
        user_pass, host_part = parts[0], parts[1] if len(parts) > 1 else ""
        user, password = user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
        host_db = host_part.split("/", 1)
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 5432
        database = host_db[1] if len(host_db) > 1 else ""
        return {"type": "postgresql", "host": host, "port": port, "user": user, "password": password, "database": database}

    if conn_str.startswith("mysql://"):
        parts = conn_str.split("://", 1)[1].split("@")
        user_pass, host_part = parts[0], parts[1] if len(parts) > 1 else ""
        user, password = user_pass.split(":", 1) if ":" in user_pass else (user_pass, "")
        host_db = host_part.split("/", 1)
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else 3306
        database = host_db[1] if len(host_db) > 1 else ""
        return {"type": "mysql", "host": host, "port": port, "user": user, "password": password, "database": database}

    if conn_str.startswith("mongodb://") or conn_str.startswith("mongodb+srv://"):
        uri = conn_str
        db_name = os.getenv("MONGO_DB_NAME", "default")
        return {"type": "mongodb", "uri": uri, "database": db_name}

    return {"type": "sqlite", "database": conn_str}


class DatabaseManager:
    def __init__(self, conn_str: str = ""):
        self.params = parse_connection_string(conn_str) if conn_str else {"type": "sqlite", "database": ""}
        self.db_type = self.params["type"]

    def get_schema(self) -> Dict[str, Any]:
        if self.db_type == "sqlite":
            return self._sqlite_schema()
        elif self.db_type == "postgresql":
            return self._postgresql_schema()
        elif self.db_type == "mysql":
            return self._mysql_schema()
        elif self.db_type == "mongodb":
            return self._mongodb_schema()
        return {"success": False, "error": f"Unsupported database type: {self.db_type}"}

    def execute_query(self, sql: str) -> Dict[str, Any]:
        check = validate_query(sql)
        if not check["valid"]:
            return {"success": False, "sql": sql, "error": check["reason"]}

        safe_sql = check["sql"]
        start = time.perf_counter()

        try:
            if self.db_type == "sqlite":
                return self._sqlite_execute(safe_sql, start)
            elif self.db_type == "postgresql":
                return self._postgresql_execute(safe_sql, start)
            elif self.db_type == "mysql":
                return self._mysql_execute(safe_sql, start)
            elif self.db_type == "mongodb":
                return self._mongodb_execute(safe_sql, start)
            return {"success": False, "sql": safe_sql, "error": f"Unsupported database type: {self.db_type}"}
        except Exception as e:
            return {"success": False, "sql": safe_sql, "error": str(e)}

    def _sqlite_schema(self) -> Dict[str, Any]:
        try:
            conn = sqlite3.connect(self.params["database"])
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

                fk_list = []
                for fk in cur.execute(f"PRAGMA foreign_key_list('{table}')").fetchall():
                    fk_list.append({"column": fk[3], "references_table": fk[2], "references_column": fk[4]})
                    schema["relationships"].append({"from_table": table, "to_table": fk[2], "via": fk[3]})

                schema["tables"][table] = {"columns": columns, "foreign_keys": fk_list}

            conn.close()
            return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _sqlite_execute(self, sql: str, start: float) -> Dict[str, Any]:
        conn = sqlite3.connect(self.params["database"])
        conn.row_factory = sqlite3.Row
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

    def _postgresql_schema(self) -> Dict[str, Any]:
        conn = psycopg2.connect(**{k: v for k, v in self.params.items() if k != "type"})
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = [r["table_name"] for r in cur.fetchall()]

        schema: Dict[str, Any] = {"tables": {}, "relationships": []}

        for table in tables:
            cur.execute("""
                SELECT column_name, data_type, is_nullable,
                    (SELECT COUNT(*) FROM information_schema.table_constraints tc
                     JOIN information_schema.key_column_usage kcu
                     ON tc.constraint_name = kcu.constraint_name
                     WHERE tc.table_name = %s AND kcu.column_name = c.column_name
                     AND tc.constraint_type = 'PRIMARY KEY') > 0 as pk
                FROM information_schema.columns c
                WHERE table_name = %s
            """, (table, table))
            columns = [{"name": r["column_name"], "type": r["data_type"], "primary_key": r["pk"]} for r in cur.fetchall()]

            cur.execute("""
                SELECT kcu.column_name, ccu.table_name AS foreign_table_name,
                       ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
            """, (table,))
            for r in cur.fetchall():
                schema["relationships"].append({
                    "from_table": table, "to_table": r["foreign_table_name"], "via": r["column_name"]
                })

            schema["tables"][table] = {"columns": columns, "foreign_keys": []}

        conn.close()
        return {"success": True, "schema": schema}

    def _postgresql_execute(self, sql: str, start: float) -> Dict[str, Any]:
        conn = psycopg2.connect(**{k: v for k, v in self.params.items() if k != "type"})
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql)
        rows = cur.fetchall()
        columns = list(rows[0].keys()) if rows else []
        conn.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "success": True, "sql": sql, "columns": columns,
            "rows": [dict(r) for r in rows], "row_count": len(rows), "latency_ms": latency_ms,
        }

    def _mysql_schema(self) -> Dict[str, Any]:
        conn = pymysql.connect(**{k: v for k, v in self.params.items() if k != "type"})
        cur = conn.cursor(pymysql.cursors.DictCursor)

        cur.execute("SHOW TABLES")
        tables = [list(r.values())[0] for r in cur.fetchall()]

        schema: Dict[str, Any] = {"tables": {}, "relationships": []}

        for table in tables:
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            columns_data = cur.fetchall()
            columns = []
            for c in columns_data:
                col_name = c["Field"]
                col_type = c["Type"]
                is_pk = c["Key"] == "PRI"
                columns.append({"name": col_name, "type": col_type, "primary_key": is_pk})

            cur.execute(f"SHOW CREATE TABLE `{table}`")
            create_stmt = cur.fetchone()
            if create_stmt:
                import re
                fk_matches = re.findall(
                    r"FOREIGN KEY\s*\(`?(\w+)`?\)\s*REFERENCES\s+`?(\w+)`?\s*\(`?(\w+)`?\)",
                    create_stmt[list(create_stmt.keys())[-1]], re.IGNORECASE
                )
                for fk_col, ref_table, ref_col in fk_matches:
                    schema["relationships"].append({
                        "from_table": table, "to_table": ref_table, "via": fk_col
                    })

            schema["tables"][table] = {"columns": columns, "foreign_keys": []}

        conn.close()
        return {"success": True, "schema": schema}

    def _mysql_execute(self, sql: str, start: float) -> Dict[str, Any]:
        conn = pymysql.connect(**{k: v for k, v in self.params.items() if k != "type"})
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(sql)
        rows = cur.fetchall()
        columns = list(rows[0].keys()) if rows else []
        conn.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "success": True, "sql": sql, "columns": columns,
            "rows": [dict(r) for r in rows], "row_count": len(rows), "latency_ms": latency_ms,
        }


    def _mongodb_schema(self) -> Dict[str, Any]:
        try:
            client = pymongo.MongoClient(self.params["uri"], serverSelectionTimeoutMS=5000)
            db = client[self.params["database"]]
            collections = db.list_collection_names()

            schema: Dict[str, Any] = {"tables": {}, "relationships": []}

            for coll in collections:
                sample = db[coll].find_one()
                columns = []
                if sample:
                    for key, val in sample.items():
                        col_type = type(val).__name__ if val is not None else "null"
                        columns.append({"name": key, "type": col_type, "primary_key": key == "_id"})
                schema["tables"][coll] = {"columns": columns, "foreign_keys": []}

            client.close()
            return {"success": True, "schema": schema}
        except Exception as e:
            return {"success": False, "error": f"MongoDB schema error: {e}"}

    def _mongodb_execute(self, sql: str, start: float) -> Dict[str, Any]:
        import re

        client = pymongo.MongoClient(self.params["uri"], serverSelectionTimeoutMS=5000)
        db = client[self.params["database"]]

        m = re.match(r"SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?(?:\s+LIMIT\s+(\d+))?\s*$", sql, re.IGNORECASE)
        if not m:
            client.close()
            return {"success": False, "sql": sql, "error": "MongoDB only supports simple SELECT ... FROM ... WHERE ... LIMIT queries."}

        fields_str = m.group(1).strip()
        collection_name = m.group(2)
        where_clause = m.group(3)
        limit = int(m.group(4)) if m.group(4) else DEFAULT_ROW_LIMIT

        if collection_name not in db.list_collection_names():
            client.close()
            return {"success": False, "sql": sql, "error": f"Collection '{collection_name}' not found."}

        qfilter = {}
        if where_clause:
            op_map = {"=": "$eq", ">": "$gt", "<": "$lt", ">=": "$gte", "<=": "$lte", "!=": "$ne", "<>": "$ne"}
            cond_match = re.match(r"(\w+)\s*(=|>|<|>=|<=|!=|<>)\s*(.+)", where_clause)
            if cond_match:
                field, op, val_str = cond_match.groups()
                val_str = val_str.strip().strip("'\"")
                val = float(val_str) if val_str.replace(".", "", 1).isdigit() else val_str
                qfilter[field] = {op_map.get(op, "$eq"): val}

        projection = None
        if fields_str != "*":
            projection = {f.strip(): 1 for f in fields_str.split(",")}
            if projection and "_id" not in projection:
                projection["_id"] = 0

        cursor = db[collection_name].find(qfilter, projection).limit(limit)
        rows = list(cursor)
        columns = list(rows[0].keys()) if rows else []
        client.close()

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "success": True, "sql": sql, "columns": columns,
            "rows": rows, "row_count": len(rows), "latency_ms": latency_ms,
        }


DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sample_ecommerce.db")
DEFAULT_CONN_STRING = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")


def get_db_manager(conn_str: Optional[str] = None) -> DatabaseManager:
    return DatabaseManager(conn_str or DEFAULT_CONN_STRING)
