import sqlite3
import os
from typing import Any, Dict, List


def scan_quality(db_path: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {"success": False, "error": "Database not found."}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        tables = [row[0] for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]

        report = {}
        total_issues = 0
        for table in tables:
            cols = [col[1] for col in cur.execute(f"PRAGMA table_info('{table}')").fetchall()]
            total = cur.execute(f"SELECT COUNT(*) FROM \"{table}\"").fetchone()[0]

            null_counts = {}
            dup_count = 0
            outlier_cols = []

            for c in cols:
                nulls = cur.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{c}" IS NULL').fetchone()[0]
                if nulls:
                    null_counts[c] = nulls

            if total > 1:
                dup = cur.execute(f"SELECT COUNT(*) - COUNT(DISTINCT rowid) FROM \"{table}\"").fetchone()[0]
                dup_count = max(0, dup)

            for c in cols:
                sample = cur.execute(f'SELECT "{c}" FROM "{table}" WHERE "{c}" IS NOT NULL LIMIT 100').fetchall()
                nums = []
                for row in sample:
                    try:
                        nums.append(float(row[0]))
                    except (ValueError, TypeError):
                        pass
                if len(nums) > 5:
                    mean = sum(nums) / len(nums)
                    var = sum((x - mean) ** 2 for x in nums) / len(nums)
                    std = var ** 0.5
                    outliers = sum(1 for x in nums if abs(x - mean) > 2 * std)
                    if outliers > len(nums) * 0.1:
                        outlier_cols.append({"column": c, "outliers": outliers, "threshold": round(mean + 2 * std, 2)})

            issues = len(null_counts) + dup_count + len(outlier_cols)
            total_issues += issues
            report[table] = {
                "row_count": total,
                "null_columns": null_counts,
                "duplicate_rows": dup_count,
                "outlier_columns": outlier_cols,
                "issue_count": issues,
            }

        conn.close()
        return {
            "success": True,
            "tables": report,
            "total_issues": total_issues,
            "clean": total_issues == 0,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
