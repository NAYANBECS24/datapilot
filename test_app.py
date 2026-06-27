import sys, os
sys.path.insert(0, os.path.dirname(__file__))
print("--- Schema ---")
from tools.schema_tool import get_schema
db_path = os.path.join(os.path.dirname(__file__), "db", "sample_ecommerce.db")
r = get_schema(db_path)
print("schema success:", r.get("success"))
if r.get("success"):
    print("tables:", list(r["schema"]["tables"].keys()))
print()
print("--- Query ---")
from tools.query_tool import execute_query
r2 = execute_query(db_path, "SELECT COUNT(*) as cnt FROM orders")
print("query success:", r2.get("success"))
print("rows:", r2.get("rows"))
print()
print("--- Forecast ---")
from tools.ml_tool import auto_ml_forecast
r3 = auto_ml_forecast(db_path, "orders", "order_id", periods=3)
print("forecast success:", r3.get("success"))
print("metrics:", r3.get("metrics"))
print()
print("--- Chart ---")
from tools.chart_tool import generate_chart
r4 = generate_chart([{"month":"Jan","rev":100},{"month":"Feb","rev":200}], "bar", "month", "rev", "Test")
print("chart success:", r4.get("success"))
print()
print("ALL OK")
