import statistics
from typing import Any, Dict, List, Optional


def prepare_explanation_context(
    data: List[Dict[str, Any]],
    user_question: str,
    persona: str = "analyst",
) -> Dict[str, Any]:
    if not data:
        return {"success": False, "error": "No data to explain."}

    numeric_cols = [
        k for k, v in data[0].items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]

    stats: Dict[str, Any] = {}
    for col in numeric_cols:
        values = [row[col] for row in data if row.get(col) is not None]
        if not values:
            continue
        stats[col] = {
            "min": min(values),
            "max": max(values),
            "mean": round(statistics.mean(values), 2),
            "total": round(sum(values), 2),
        }

    return {
        "success": True,
        "row_count": len(data),
        "numeric_summary": stats,
        "persona": persona,
        "user_question": user_question,
        "instruction": (
            "Write a concise, friendly explanation of this data for the user. "
            + (
                "Keep it to 2-3 sentences, focused on business impact and the headline number."
                if persona == "executive"
                else "Include the headline number plus 1-2 notable details or outliers."
            )
        ),
    }


def detect_anomalies(
    series: List[Dict[str, Any]],
    value_key: str,
    label_key: str,
    z_threshold: float = 1.8,
) -> Dict[str, Any]:
    values = [row[value_key] for row in series if row.get(value_key) is not None]
    if len(values) < 3:
        return {"success": True, "anomalies": []}

    mean = statistics.mean(values)
    stdev = statistics.pstdev(values) or 1e-9

    anomalies = []
    for row in series:
        v = row.get(value_key)
        if v is None:
            continue
        z = (v - mean) / stdev
        if abs(z) >= z_threshold:
            anomalies.append(
                {
                    "label": row.get(label_key),
                    "value": v,
                    "z_score": round(z, 2),
                    "direction": "spike" if z > 0 else "drop",
                }
            )

    return {"success": True, "mean": round(mean, 2), "stdev": round(stdev, 2), "anomalies": anomalies}


def generate_auto_insights(db_path: str, conn_str: str = "") -> Dict[str, Any]:
    try:
        if conn_str and conn_str.startswith("sqlite"):
            actual_path = conn_str.split("://", 1)[-1] if "://" in conn_str else conn_str
            db_path = actual_path or db_path

        if conn_str and (conn_str.startswith("postgresql") or conn_str.startswith("postgres")):
            return _generate_auto_insights_pg(conn_str)

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        metrics = {}

        cur.execute("SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) FROM order_items oi")
        metrics["total_revenue"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM orders")
        metrics["total_orders"] = cur.fetchone()[0]

        cur.execute("SELECT AVG(oi.quantity * oi.unit_price) FROM order_items oi")
        avg = cur.fetchone()[0]
        metrics["avg_order_value"] = avg if avg else 0

        cur.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
        metrics["active_customers"] = cur.fetchone()[0]

        trends = {}

        cur.execute("""
            SELECT strftime('%Y-%m', o.order_date) as month,
                   ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY month ORDER BY month LIMIT 12
        """)
        trends["monthly_revenue"] = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            GROUP BY p.category ORDER BY revenue DESC
        """)
        trends["category_revenue"] = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
        trends["order_status"] = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT p.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            GROUP BY p.name ORDER BY revenue DESC LIMIT 10
        """)
        trends["top_products"] = [dict(r) for r in cur.fetchall()]

        anomalies = []

        monthly = trends.get("monthly_revenue", [])
        if len(monthly) >= 3:
            vals = [r["revenue"] for r in monthly]
            mean = statistics.mean(vals)
            stdev = statistics.pstdev(vals) or 1e-9
            for r in monthly:
                z = (r["revenue"] - mean) / stdev
                if abs(z) >= 1.8:
                    anomalies.append({
                        "label": f"Revenue {r['month']}",
                        "value": r["revenue"],
                        "z_score": round(z, 2),
                        "direction": "spike" if z > 0 else "drop",
                    })

        summary_parts = []
        summary_parts.append(f"Total revenue is ${metrics['total_revenue']:,.0f} across {metrics['total_orders']:,} orders with an average order value of ${metrics['avg_order_value']:,.2f}.")
        summary_parts.append(f"There are {metrics['active_customers']:,} unique customers.")
        if trends.get("category_revenue"):
            top_cat = trends["category_revenue"][0]
            summary_parts.append(f"The top category is '{top_cat['category']}' at ${top_cat['revenue']:,.2f}.")
        if anomalies:
            summary_parts.append(f"{len(anomalies)} anomaly/ies detected in monthly revenue trends.")
        summary = " ".join(summary_parts)

        recommendations = []
        if trends.get("order_status"):
            pending_orders = sum(1 for s in trends["order_status"] if s.get("status", "").lower() in ("pending", "processing"))
            if pending_orders > 0:
                recommendations.append(f"Follow up on {pending_orders} pending/processing orders.")
        low_stock = cur.execute("SELECT COUNT(*) FROM inventory WHERE stock_quantity < 50").fetchone()[0]
        if low_stock > 0:
            recommendations.append(f"Restock {low_stock} products with inventory below 50 units.")
        if anomalies:
            recommendations.append("Investigate anomalous revenue months for root cause.")
        recommendations.append("Run a deeper customer segmentation analysis to identify high-value segments.")

        conn.close()

        return {
            "metrics": metrics,
            "trends": trends,
            "anomalies": anomalies,
            "summary": summary,
            "recommendations": recommendations,
        }
    except Exception as e:
        return {"error": str(e)}


def _generate_auto_insights_pg(conn_str: str) -> Dict[str, Any]:
    try:
        import psycopg2
        import psycopg2.extras

        from tools.db_manager import parse_connection_string
        params = parse_connection_string(conn_str)
        pg_params = {k: v for k, v in params.items() if k != "type"}

        conn = psycopg2.connect(**pg_params)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        metrics = {}

        cur.execute("SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) FROM order_items oi")
        metrics["total_revenue"] = cur.fetchone()["coalesce"]

        cur.execute("SELECT COUNT(*) FROM orders")
        metrics["total_orders"] = cur.fetchone()["count"]

        cur.execute("SELECT AVG(oi.quantity * oi.unit_price) FROM order_items oi")
        avg = cur.fetchone()["avg"]
        metrics["avg_order_value"] = avg if avg else 0

        cur.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
        metrics["active_customers"] = cur.fetchone()["count"]

        trends = {}

        cur.execute("""
            SELECT to_char(o.order_date, 'YYYY-MM') as month,
                   ROUND(SUM(oi.quantity * oi.unit_price)::numeric, 2) as revenue
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            GROUP BY month ORDER BY month LIMIT 12
        """)
        trends["monthly_revenue"] = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price)::numeric, 2) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            GROUP BY p.category ORDER BY revenue DESC
        """)
        trends["category_revenue"] = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT status, COUNT(*)::int as count FROM orders GROUP BY status")
        trends["order_status"] = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT p.name, ROUND(SUM(oi.quantity * oi.unit_price)::numeric, 2) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            GROUP BY p.name ORDER BY revenue DESC LIMIT 10
        """)
        trends["top_products"] = [dict(r) for r in cur.fetchall()]

        anomalies = []

        monthly = trends.get("monthly_revenue", [])
        if len(monthly) >= 3:
            vals = [r["revenue"] for r in monthly]
            mean = statistics.mean(vals)
            stdev = statistics.pstdev(vals) or 1e-9
            for r in monthly:
                z = (r["revenue"] - mean) / stdev
                if abs(z) >= 1.8:
                    anomalies.append({"label": f"Revenue {r['month']}", "value": r["revenue"], "z_score": round(z, 2), "direction": "spike" if z > 0 else "drop"})

        summary_parts = []
        summary_parts.append(f"Total revenue is ${metrics['total_revenue']:,.0f} across {metrics['total_orders']:,} orders with an average order value of ${metrics['avg_order_value']:,.2f}.")
        summary_parts.append(f"There are {metrics['active_customers']:,} unique customers.")
        if trends.get("category_revenue"):
            top_cat = trends["category_revenue"][0]
            summary_parts.append(f"The top category is '{top_cat['category']}' at ${top_cat['revenue']:,.2f}.")
        if anomalies:
            summary_parts.append(f"{len(anomalies)} anomaly/ies detected in monthly revenue trends.")
        summary = " ".join(summary_parts)

        recommendations = []
        cur.execute("SELECT COUNT(*) FROM inventory WHERE stock_quantity < 50")
        low_stock = cur.fetchone()["count"]
        if low_stock > 0:
            recommendations.append(f"Restock {low_stock} products with inventory below 50 units.")
        if anomalies:
            recommendations.append("Investigate anomalous revenue months for root cause.")
        recommendations.append("Run a deeper customer segmentation analysis to identify high-value segments.")

        conn.close()

        return {"metrics": metrics, "trends": trends, "anomalies": anomalies, "summary": summary, "recommendations": recommendations}
    except ImportError:
        return {"error": "PostgreSQL driver (psycopg2) not installed. Install with: pip install psycopg2-binary"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import json, os
    sample = [
        {"day": "Mon", "revenue": 12000},
        {"day": "Tue", "revenue": 12500},
        {"day": "Wed", "revenue": 11800},
        {"day": "Thu", "revenue": 41000},
        {"day": "Fri", "revenue": 12100},
    ]
    print(detect_anomalies(sample, value_key="revenue", label_key="day"))
    print(prepare_explanation_context(sample, "How did revenue look this week?", persona="executive"))
    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")
    import json as _json
    print(_json.dumps(generate_auto_insights(db_path), indent=2, default=str))
