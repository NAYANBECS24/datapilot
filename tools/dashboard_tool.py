import json
import os
from typing import Any, Dict, List, Optional

from tools.chart_tool import generate_chart
from tools.query_tool import execute_query


def build_dashboard(
    specs: List[Dict[str, Any]],
    db_path: str,
    conn_str: str = "",
) -> Dict[str, Any]:
    if not specs:
        return {"success": False, "error": "No chart specs provided.", "charts": []}

    charts = []
    for i, spec in enumerate(specs):
        sql = spec.get("sql", "")
        chart_type = spec.get("chart_type", "bar")
        title = spec.get("title", f"Chart {i+1}")
        x = spec.get("x")
        y = spec.get("y")

        if not sql:
            charts.append({"error": f"Chart {i+1}: no SQL query.", "title": title})
            continue

        result = execute_query(db_path, sql, conn_str=conn_str)
        if not result.get("success"):
            charts.append({"error": f"Chart {i+1}: {result.get('error', 'query failed')}", "title": title})
            continue

        data = result.get("rows", [])
        if not data:
            charts.append({"error": f"Chart {i+1}: query returned no rows.", "title": title})
            continue

        chart_result = generate_chart(data, chart_type, x=x, y=y, title=title)
        if chart_result.get("success"):
            charts.append({
                "title": title,
                "chart_type": chart_result.get("chart_type", chart_type),
                "figure": chart_result["figure"],
            })
        else:
            charts.append({"error": f"Chart {i+1}: {chart_result.get('error', 'render failed')}", "title": title})

    return {"success": True, "charts": charts}


DASHBOARD_PLANNING_PROMPT = """You are a dashboard planner for an e-commerce database. Given a user's request, output a JSON array of chart specifications. Each spec must have:

- "title": short chart title
- "sql": a valid read-only SQLite SELECT query against the sample_ecommerce.db schema
- "chart_type": one of "bar", "line", "pie", "scatter", "choropleth", "scatter_mapbox"
- "x": column for x-axis / category
- "y": column for y-axis / value

SCHEMA:
  customers(customer_id, name, email, city, signup_date)
  products(product_id, name, category, price, cost)
  orders(order_id, customer_id, order_date, status)
  order_items(order_item_id, order_id, product_id, quantity, unit_price)
  inventory(inventory_id, product_id, warehouse_location, stock_quantity)
  suppliers(supplier_id, name, contact_email, phone, city, supply_category)
  reviews(review_id, product_id, customer_id, rating, review_text, review_date)
  payments(payment_id, order_id, payment_method, amount, payment_date, transaction_id)
  shipping(shipping_id, order_id, address, city, pincode, shipped_date, delivered_date, carrier)

IMPORTANT: Use products.name for product names (NOT product_name).
Use customers.name for customer names (NOT customer_name).

RULES:
- Return ONLY a valid JSON array. No markdown fences, no extra text.
- Generate 2-4 charts that best answer the user's request.
- Pick diverse chart types (not all bars).
- Use meaningful titles.
- Prefix time-series queries with appropriate GROUP BY and ORDER BY.

EXAMPLE for "show me sales overview":
[
  {"title": "Monthly Revenue Trend", "sql": "SELECT strftime('%Y-%m', o.order_date) as month, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue FROM orders o JOIN order_items oi ON o.order_id = oi.order_id GROUP BY month ORDER BY month LIMIT 12", "chart_type": "line", "x": "month", "y": "revenue"},
  {"title": "Revenue by Category", "sql": "SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.category ORDER BY revenue DESC", "chart_type": "pie", "x": "category", "y": "revenue"},
  {"title": "Top Products", "sql": "SELECT p.name, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.name ORDER BY revenue DESC LIMIT 10", "chart_type": "bar", "x": "name", "y": "revenue"}
]
"""


def plan_dashboard_llm(
    user_request: str,
    llm_api_key: str,
    llm_base_url: Optional[str] = None,
    model: str = "meta/llama-3.1-70b-instruct",
) -> List[Dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=llm_api_key) if not llm_base_url else OpenAI(api_key=llm_api_key, base_url=llm_base_url)

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            temperature=0.1,
            messages=[
                {"role": "system", "content": DASHBOARD_PLANNING_PROMPT},
                {"role": "user", "content": user_request},
            ],
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("\n", 1)[0]
            if content.endswith("```"):
                content = content[:-3]
        return json.loads(content)
    except Exception as e:
        return [{"error": str(e), "title": "Planning failed"}]
