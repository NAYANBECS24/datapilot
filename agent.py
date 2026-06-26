import json
import os
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from tools.schema_tool import get_schema
from tools.query_tool import execute_query
from tools.chart_tool import generate_chart
from tools.flowchart_tool import generate_flowchart
from tools.insight_tool import prepare_explanation_context, detect_anomalies
from trace.tracer import AgentTracer, timed

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "sample_ecommerce.db")
MAX_SQL_RETRIES = 3

NVIDIA_API_KEY = os.getenv("OPENAI_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
NVIDIA_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")

if not NVIDIA_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY not set. Copy .env.example -> .env and add your NVIDIA key "
        "(starts with nvapi-)."
    )


def _normalise_schema(schema) -> Dict:
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(schema, dict):
        if "tables" in schema:
            return schema
        if "schema" in schema and isinstance(schema["schema"], dict):
            return schema["schema"]
    return schema if isinstance(schema, dict) else {}


def _normalise_data(data) -> list:
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "rows" in parsed:
                return parsed["rows"]
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(data, list):
        return data
    return []


LANGUAGES = {
    "en": "",
    "hi": "IMPORTANT: Respond in Hindi (Devanagari script). Use Hindi for all explanations and summaries.",
    "es": "IMPORTANT: Respond in Spanish. Use Spanish for all explanations and summaries.",
    "fr": "IMPORTANT: Respond in French. Use French for all explanations and summaries.",
    "de": "IMPORTANT: Respond in German. Use German for all explanations and summaries.",
}

LANGUAGE_INSTRUCTION = LANGUAGES.get("en", "")

SYSTEM_PROMPT = f"""{LANGUAGE_INSTRUCTION}You are DataPilot, a conversational BI copilot for an e-commerce database.

TABLES AND COLUMNS (use these exact names):

  customers(customer_id, name, email, city, signup_date)
  products(product_id, name, category, price, cost)
  orders(order_id, customer_id, order_date, status)
  order_items(order_item_id, order_id, product_id, quantity, unit_price)
  inventory(inventory_id, product_id, warehouse_location, stock_quantity)

Also available for deeper analysis:
  suppliers(supplier_id, name, contact_email, phone, city, supply_category)
  reviews(review_id, product_id, customer_id, rating, review_text, review_date)
  payments(payment_id, order_id, payment_method, amount, payment_date, transaction_id)
  shipping(shipping_id, order_id, address, city, pincode, shipped_date, delivered_date, carrier)

IMPORTANT COLUMN NOTES:
  - products.name (NOT product_name) holds the product name
  - Use products.name in your queries, never "product_name"
  - Use customers.name (NOT customer_name) for customer names
  - Use category from products for product categories

RULES:
  1. ALWAYS call get_schema before writing SQL if you haven't seen the schema yet.
  2. Only write read-only SELECT queries. Never DML/DDL.
  3. When a chart or diagram helps, call generate_chart or generate_flowchart.
  4. For ER diagrams, call generate_flowchart(diagram_type="er_diagram", schema=<get_schema result>).
     Pass the full result from get_schema (with 'success' and 'schema' keys) — the tool handles unwrapping.
  5. If execute_query returns success=false, fix the SQL and retry (up to 3 times).
  6. After getting data, write a short clear summary with real numbers.
  7. Suggest one follow-up question the user might ask next.
  8. Be concise. Let charts and diagrams do the heavy lifting.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Get the full database schema: tables, columns, types, and foreign-key relationships. Call this FIRST before any SQL.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": "Execute a read-only SELECT query against the database and return result rows.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "A read-only SELECT SQL query."}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Render a bar, line, pie, scatter, or auto chart from query result data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}, "description": "Row dicts from execute_query."},
                    "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter", "auto"]},
                    "x": {"type": "string", "description": "Column for x-axis / category."},
                    "y": {"type": "string", "description": "Column for y-axis / value."},
                    "title": {"type": "string", "description": "Chart title."},
                },
                "required": ["data", "chart_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_flowchart",
            "description": "Generate a Mermaid ER diagram (from get_schema result) or a process-flow diagram (from ordered steps).",
            "parameters": {
                "type": "object",
                "properties": {
                    "diagram_type": {"type": "string", "enum": ["er_diagram", "process_flow"]},
                    "schema": {"type": "object", "description": "For er_diagram: pass the FULL result from get_schema (with success and schema keys)."},
                    "steps": {"type": "array", "items": {"type": "string"}, "description": "For process_flow: ordered stage labels."},
                    "decision_points": {"type": "object", "description": "Optional branching, e.g. {'Confirmed': ['Cancelled']}."},
                },
                "required": ["diagram_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_data",
            "description": "Generate a natural-language summary and insight from query result data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}, "description": "The rows from execute_query."},
                    "user_question": {"type": "string", "description": "The original user question."},
                    "persona": {"type": "string", "enum": ["analyst", "executive"], "description": "Explanation style."},
                },
                "required": ["data", "user_question"],
            },
        },
    },
]

TOOL_IMPL: Dict[str, Any] = {
    "get_schema": lambda **kw: get_schema(DB_PATH),

    "execute_query": lambda **kw: execute_query(DB_PATH, kw.get("sql", "")),

    "generate_chart": lambda **kw: generate_chart(
        _normalise_data(kw.get("data", [])),
        kw.get("chart_type", "bar"),
        kw.get("x"),
        kw.get("y"),
        kw.get("title", ""),
    ),

    "generate_flowchart": lambda **kw: generate_flowchart(
        kw.get("diagram_type", "er_diagram"),
        _normalise_schema(kw.get("schema")),
        kw.get("steps"),
        kw.get("decision_points"),
    ),

    "explain_data": lambda **kw: prepare_explanation_context(
        _normalise_data(kw.get("data", [])),
        kw.get("user_question", ""),
        kw.get("persona", "analyst"),
    ),
}


def run_agent_turn(
    user_message: str,
    history: List[Dict[str, Any]],
    tracer: AgentTracer,
    language: str = "en",
) -> Dict[str, Any]:
    client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
    model = NVIDIA_MODEL

    lang_instruction = LANGUAGES.get(language, "")
    system_content = f"""{lang_instruction}You are DataPilot, a conversational BI copilot for an e-commerce database.

TABLES AND COLUMNS (use these exact names):

  customers(customer_id, name, email, city, signup_date)
  products(product_id, name, category, price, cost)
  orders(order_id, customer_id, order_date, status)
  order_items(order_item_id, order_id, product_id, quantity, unit_price)
  inventory(inventory_id, product_id, warehouse_location, stock_quantity)

Also available for deeper analysis:
  suppliers(supplier_id, name, contact_email, phone, city, supply_category)
  reviews(review_id, product_id, customer_id, rating, review_text, review_date)
  payments(payment_id, order_id, payment_method, amount, payment_date, transaction_id)
  shipping(shipping_id, order_id, address, city, pincode, shipped_date, delivered_date, carrier)

IMPORTANT COLUMN NOTES:
  - products.name (NOT product_name) holds the product name
  - Use products.name in your queries, never "product_name"
  - Use customers.name (NOT customer_name) for customer names
  - Use category from products for product categories

RULES:
  1. ALWAYS call get_schema before writing SQL if you haven't seen the schema yet.
  2. Only write read-only SELECT queries. Never DML/DDL.
  3. When a chart or diagram helps, call generate_chart or generate_flowchart.
  4. For ER diagrams, call generate_flowchart(diagram_type="er_diagram", schema=<get_schema result>).
     Pass the full result from get_schema (with 'success' and 'schema' keys) — the tool handles unwrapping.
  5. If execute_query returns success=false, fix the SQL and retry (up to 3 times).
  6. After getting data, write a short clear summary with real numbers.
  7. Suggest one follow-up question the user might ask next.
  8. Be concise. Let charts and diagrams do the heavy lifting.
"""

    messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": user_message}]

    charts: List[Dict[str, Any]] = []
    diagrams: List[str] = []
    sql_queries: List[Dict[str, Any]] = []
    sql_retry_count = 0

    while True:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            tools=TOOLS,
            messages=messages,
        )

        choice = response.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            return {
                "reply": msg.content or "",
                "charts": charts,
                "diagrams": diagrams,
                "sql_queries": sql_queries,
            }

        messages.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})
        tool_results = []

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                tool_input = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                tool_input = {}

            with timed() as t:
                fn = TOOL_IMPL.get(tool_name)
                result = fn(**tool_input) if fn else {"success": False, "error": f"Unknown tool '{tool_name}'"}
            tracer.log_tool_call(tool_name, tool_input, result, t.ms)

            if tool_name == "execute_query" and not result.get("success"):
                sql_retry_count += 1
                if sql_retry_count > MAX_SQL_RETRIES:
                    result["error"] = (
                        result.get("error", "")
                        + f" (gave up after {MAX_SQL_RETRIES} retries — please rephrase.)"
                    )

            if tool_name == "execute_query" and result.get("success"):
                sql_queries.append({
                    "sql": result.get("sql", ""),
                    "columns": result.get("columns", []),
                    "rows": result.get("rows", []),
                    "row_count": result.get("row_count", 0),
                    "latency_ms": result.get("latency_ms", 0),
                })

            if tool_name == "generate_chart" and result.get("success"):
                charts.append(result["figure"])
            if tool_name == "generate_flowchart" and result.get("success"):
                diagrams.append(result["mermaid_code"])

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)[:8000],
            })

        messages.extend(tool_results)
