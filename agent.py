import json
import os
import time
from typing import Any, Dict, List, Optional


def _json_default(o):
    if hasattr(o, 'tolist'):
        return o.tolist()
    try:
        return str(o)
    except Exception:
        return None


def _safe_json_dumps(val: Any, maxlen: int = 8000) -> str:
    try:
        return json.dumps(val, default=_json_default)[:maxlen]
    except Exception:
        return json.dumps({"error": "result could not be serialized"})

from dotenv import load_dotenv

from tools.schema_tool import get_schema
from tools.query_tool import execute_query
from tools.chart_tool import generate_chart
from tools.flowchart_tool import generate_flowchart
from tools.insight_tool import prepare_explanation_context, detect_anomalies
from tools.analytics_tool import generate_forecast, compare_segments
from tools.quality_tool import scan_quality
from tools.report_tool import generate_report
from tools.rag_tool import retrieve_context
from tools.ml_tool import auto_ml_forecast
from tools.dashboard_tool import build_dashboard
from tools.db_manager import DEFAULT_CONN_STRING
from trace.tracer import AgentTracer, timed

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "sample_ecommerce.db")

# Auto-seed database if not present (Streamlit Cloud fix)
if not os.path.exists(DB_PATH):
    try:
        from db.seed_db import main as seed_db
        seed_db()
    except Exception:
        pass

DB_CONN_STRING = os.getenv("DATABASE_URL", "")
MAX_SQL_RETRIES = 3
MAX_TOOL_ITERATIONS = 8

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia").lower()


class _LocalToolCall:
    """OpenAI-shaped tool call used when a model returns raw JSON text."""

    def __init__(self, name: str, arguments: Dict[str, Any], tool_id: str):
        self.type = "function"
        self.id = tool_id
        self.function = type("func", (), {"name": name, "arguments": json.dumps(arguments)})()


def _tool_names() -> set:
    return {
        t.get("function", {}).get("name")
        for t in TOOLS
        if t.get("type") == "function" and t.get("function", {}).get("name")
    }


def _json_from_text(text: str) -> Any:
    stripped = (text or "").strip()
    if not stripped:
        return None

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    candidates = [stripped]
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = stripped.find(open_char)
        end = stripped.rfind(close_char)
        if start != -1 and end > start:
            candidates.append(stripped[start:end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _coerce_tool_arguments(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _raw_tool_calls_from_obj(obj: Any) -> List[_LocalToolCall]:
    calls: List[_LocalToolCall] = []
    names = _tool_names()

    def visit(node: Any):
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return

        for key in ("tool_calls", "tools"):
            if isinstance(node.get(key), list):
                visit(node[key])

        function = node.get("function")
        name = node.get("name") or node.get("tool") or node.get("tool_name")
        raw_args = node.get("parameters", node.get("arguments", node.get("input", {})))

        if isinstance(function, dict):
            name = function.get("name") or name
            raw_args = function.get("arguments", raw_args)

        if name in names:
            tool_id = str(node.get("id") or f"raw_call_{len(calls) + 1}")
            calls.append(_LocalToolCall(name, _coerce_tool_arguments(raw_args), tool_id))

    visit(obj)
    return calls


def _coerce_message_tool_calls(msg: Any) -> tuple[List[Any], bool]:
    structured = getattr(msg, "tool_calls", None)
    if structured:
        return list(structured), False

    raw_calls = _raw_tool_calls_from_obj(_json_from_text(getattr(msg, "content", "") or ""))
    return raw_calls, bool(raw_calls)


def _tool_call_id(tc: Any, fallback: str) -> str:
    if isinstance(tc, dict):
        return str(tc.get("id") or fallback)
    return str(getattr(tc, "id", fallback) or fallback)


def _tool_call_name(tc: Any) -> str:
    if isinstance(tc, dict):
        function = tc.get("function") or {}
        return function.get("name") or tc.get("name") or ""
    return getattr(getattr(tc, "function", None), "name", "")


def _tool_call_input(tc: Any) -> Dict[str, Any]:
    if isinstance(tc, dict):
        function = tc.get("function") or {}
        raw_args = function.get("arguments", tc.get("arguments", tc.get("parameters", {})))
    else:
        raw_args = getattr(getattr(tc, "function", None), "arguments", {})
    return _coerce_tool_arguments(raw_args)


def _tool_call_message(tc: Any, fallback: str) -> Dict[str, Any]:
    return {
        "id": _tool_call_id(tc, fallback),
        "type": "function",
        "function": {
            "name": _tool_call_name(tc),
            "arguments": json.dumps(_tool_call_input(tc)),
        },
    }


def _resolve_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        return ""


OPENAI_API_KEY = _resolve_api_key()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
NVIDIA_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")

LLM_DISPLAY_NAMES = {
    "nvidia": f"NVIDIA {NVIDIA_MODEL}",
    "openai": f"OpenAI {OPENAI_MODEL}",
    "anthropic": f"Anthropic {ANTHROPIC_MODEL}",
}


def _resolve_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        return ""


def _get_llm_client():
    openai_key = _resolve_key()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not openai_key and not anthropic_key:
        try:
            import streamlit as st
            anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass

    if LLM_PROVIDER == "openai":
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY not set for OpenAI provider.")
        from openai import OpenAI
        return OpenAI(api_key=openai_key)

    elif LLM_PROVIDER == "anthropic":
        if not anthropic_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set for Anthropic provider.")
        from anthropic import Anthropic
        return Anthropic(api_key=anthropic_key)

    else:
        if not openai_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Get a free NVIDIA API key at https://build.nvidia.com, "
                "then add it to .env (local) or Streamlit Cloud dashboard → Advanced Settings → Secrets."
            )
        from openai import OpenAI
        return OpenAI(api_key=openai_key, base_url=NVIDIA_BASE_URL)


def _call_llm(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Any:
    client = _get_llm_client()
    model = NVIDIA_MODEL if LLM_PROVIDER == "nvidia" else (OPENAI_MODEL if LLM_PROVIDER == "openai" else ANTHROPIC_MODEL)

    try:
        if LLM_PROVIDER == "anthropic":
            return _call_anthropic(client, model, messages, tools)
        else:
            return _call_openai_compat(client, model, messages, tools)
    except Exception as e:
        raise RuntimeError(f"LLM API call failed ({LLM_PROVIDER}): {e}")


def _call_llm_stream(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
    client = _get_llm_client()
    model = NVIDIA_MODEL if LLM_PROVIDER == "nvidia" else (OPENAI_MODEL if LLM_PROVIDER == "openai" else ANTHROPIC_MODEL)

    if LLM_PROVIDER == "anthropic":
        text = _call_anthropic(client, model, messages, tools).content
        for chunk in _chunk_text(text):
            yield chunk
    else:
        stream = client.chat.completions.create(
            model=model,
            max_tokens=8192,
            tools=tools,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


def _chunk_text(text: str, size: int = 5) -> List[str]:
    words = text.split(" ")
    for i in range(0, len(words), size):
        yield " ".join(words[i:i + size]) + " "


def _forecast_with_sql(kw: dict, username: str = "") -> dict:
    data_raw = kw.get("data")
    sql = kw.get("sql", "").strip()
    if sql or (isinstance(data_raw, str) and data_raw.strip().lower().startswith("select")):
        sql_to_run = sql or data_raw.strip()
        result = execute_query(DB_PATH, sql_to_run, conn_str=DB_CONN_STRING, username=username)
        if not result.get("success"):
            return {"success": False, "error": f"SQL execution failed: {result.get('error', '')}"}
        data = result.get("rows", [])
    elif isinstance(data_raw, str):
        return {"success": False, "error": f"Expected data as an array, got string. Pass the SQL query via the 'sql' parameter instead."}
    else:
        data = _normalise_data(data_raw)
    try:
        return generate_forecast(
            data,
            kw.get("date_col", ""),
            kw.get("value_col", ""),
            int(kw.get("periods", 5)),
        )
    except Exception as e:
        return {"success": False, "error": f"Forecast failed: {e}"}

def _build_tool_impl(username: str = "") -> Dict[str, Any]:
    return {
        "get_schema": lambda **kw: get_schema(DB_PATH, conn_str=DB_CONN_STRING, username=username),
        "execute_query": lambda **kw: execute_query(DB_PATH, kw.get("sql", ""), conn_str=DB_CONN_STRING, username=username),
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
            kw.get("question"),
            kw.get("branches"),
        ),
        "explain_data": lambda **kw: prepare_explanation_context(
            _normalise_data(kw.get("data", [])),
            kw.get("user_question", ""),
            kw.get("persona", "analyst"),
        ),
        "forecast_data": lambda **kw: _forecast_with_sql(kw, username=username),
        "compare_data": lambda **kw: compare_segments(
            _normalise_data(kw.get("data_a", [])),
            _normalise_data(kw.get("data_b", [])),
            kw.get("label_a", "A"),
            kw.get("label_b", "B"),
            kw.get("value_col", ""),
            kw.get("category_col", ""),
        ),
        "retrieve_context": lambda **kw: retrieve_context(kw.get("query", ""), username=username, top_k=int(kw.get("top_k", 5))),
        "scan_quality": lambda **kw: scan_quality(DB_PATH),
        "generate_report": lambda **kw: generate_report(
            _normalise_data(kw.get("data", [])),
            kw.get("columns", []),
            kw.get("question", ""),
            kw.get("chart_titles"),
        ),
        "auto_ml_forecast": lambda **kw: auto_ml_forecast(
            DB_PATH,
            kw.get("table", ""),
            kw.get("target_col", ""),
            kw.get("date_col"),
            int(kw.get("periods", 6)),
            conn_str=DB_CONN_STRING,
        ),
        "build_dashboard": lambda **kw: build_dashboard(
            kw.get("specs", []),
            DB_PATH,
            conn_str=DB_CONN_STRING,
            username=username,
        ),
    }


def run_agent_turn_stream(
    user_message: str,
    history: List[Dict[str, Any]],
    tracer: AgentTracer,
    language: str = "en",
    username: str = "",
    file_mode: bool = False,
):
    lang_instruction = LANGUAGES.get(language, "")
    user_context = ""
    if file_mode:
        user_context = (
            f"\nCURRENT MODE: Ask from Uploaded File. "
            f"The user ({username or 'shared'}) wants to ask questions ONLY about their uploaded data.\n"
            f"- Call get_schema first to discover their uploaded tables (prefixed with 'my.' or 'uploads.').\n"
            f"- Focus all answers and queries on their uploaded data only.\n"
        )
    elif username:
        user_context = (
            f"\nCurrent user: {username}. "
            f"They have personal uploads (prefixed with 'my.' in schema) and "
            f"shared uploads (prefixed with 'uploads.' in schema) available.\n"
        )
    system_content = SYSTEM_PROMPT_TEMPLATE.format(lang_instruction=lang_instruction) + user_context
    tool_impl = _build_tool_impl(username)

    messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": user_message}]

    charts = []
    diagrams = []
    sql_queries = []
    sql_retry_count = 0
    tool_iterations = 0

    while True:
        try:
            msg = _call_llm(messages, TOOLS)
        except Exception as e:
            yield {"type": "reply", "content": f"⚠️ Sorry, I encountered an error contacting the LLM provider (**{LLM_PROVIDER}**).\n\n> {e}\n\nPlease check your API key and try again."}
            return

        tool_calls, raw_tool_calls = _coerce_message_tool_calls(msg)
        if not tool_calls:
            yield {"type": "charts", "content": charts}
            yield {"type": "diagrams", "content": diagrams}
            yield {"type": "sql_queries", "content": sql_queries}
            yield {"type": "stream_start", "content": ""}
            for chunk in _chunk_text(msg.content or ""):
                yield {"type": "stream", "content": chunk}
            yield {"type": "stream_end", "content": ""}
            return

        tool_iterations += 1
        if tool_iterations > MAX_TOOL_ITERATIONS:
            yield {"type": "reply", "content": "I ran too many tool steps without reaching a final answer. Please try a narrower question."}
            return

        messages.append({
            "role": "assistant",
            "content": "" if raw_tool_calls else msg.content or "",
            "tool_calls": [_tool_call_message(tc, f"call_{i}") for i, tc in enumerate(tool_calls)],
        })
        tool_results = []

        for i, tc in enumerate(tool_calls):
            tool_name = _tool_call_name(tc)
            tool_input = _tool_call_input(tc)
            tool_call_id = _tool_call_id(tc, f"call_{i}")

            with timed() as t:
                fn = tool_impl.get(tool_name)
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
            if tool_name == "auto_ml_forecast" and result.get("success"):
                charts.append(result["figure"])
            if tool_name == "forecast_data" and result.get("success"):
                if result.get("figure"):
                    charts.append(result["figure"])
            if tool_name == "build_dashboard" and result.get("success"):
                for c in result.get("charts", []):
                    if "figure" in c:
                        charts.append(c["figure"])

            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": _safe_json_dumps(result),
            })

        messages.extend(tool_results)


def _call_openai_compat(client, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Any:
    response = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        temperature=0,
        tools=tools,
        messages=messages,
    )
    return response.choices[0].message


def _call_anthropic(client, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Any:
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]

    system_content = system_msgs[0]["content"] if system_msgs else ""

    anthropic_tools = []
    for t in tools:
        if t["type"] == "function":
            anthropic_tools.append({
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            })

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=system_content,
        tools=anthropic_tools if anthropic_tools else None,
        messages=other_msgs,
    )

    class ToolCall:
        def __init__(self, name, input_dict, tool_id):
            self.type = "function"
            self.id = tool_id
            self.function = type("func", (), {"name": name, "arguments": json.dumps(input_dict)})()

    class Message:
        def __init__(self, content, tool_calls):
            self.content = content
            self.tool_calls = tool_calls

    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append(ToolCall(block.name, block.input, block.id))

    return Message(
        content=response.content[0].text if response.content and response.content[0].type == "text" else "",
        tool_calls=tool_calls if tool_calls else None,
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

SYSTEM_PROMPT_TEMPLATE = """{lang_instruction}You are Eunoia, a conversational BI copilot for a database.

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

USER-UPLOADED DATA:
  Users can upload CSV files or entire SQLite databases. When you call get_schema,
  any uploaded tables will appear with an "uploads." prefix (e.g. "uploads.my_table").
  These tables live in a separate database file but you can query them with normal SQL.

UPLOADED DOCUMENTS (RAG):
  Users can upload PDF, TXT, and MD files. These are chunked, embedded, and stored in a vector database.
  When a user asks about document content, call retrieve_context to search relevant passages.
  Combine document context with SQL results for richer answers. Always cite the source filename.

MACHINE LEARNING FORECASTING:
  You can train a simple ML model on any table to forecast numeric values.
  Option A — forecast_data: Pass a SQL query and column names to forecast_data(sql, date_col, value_col, periods).
    The tool executes the SQL internally and forecasts from the results.
    Example: "Predict sales for the next 6 months" → forecast_data(sql="SELECT strftime('%Y-%m', order_date) AS month, SUM(quantity * unit_price) AS revenue FROM orders JOIN order_items USING(order_id) GROUP BY month ORDER BY month", date_col="month", value_col="revenue", periods=6)
  Option B — auto_ml_forecast: Call auto_ml_forecast(table, target_col, date_col, periods) directly on existing table columns.
    Works on tables with numeric columns like order_items (quantity, unit_price) or payments (amount).
    Example: "Forecast order quantities" → auto_ml_forecast(table="order_items", target_col="quantity", date_col="order_date", periods=6)

GEOGRAPHIC MAPS:
  You can create choropleth maps (for country/state data) and scatter_mapbox maps (for lat/lon data).
  Use chart_type="choropleth" with a location column as x, or chart_type="scatter_mapbox" with lat/lon columns.

DASHBOARDS:
  When a user asks for a "dashboard" or "overview" of multiple metrics, plan 2-4 diverse charts
  and call build_dashboard with the specs. Each spec needs: title, sql, chart_type, x, y.
  Pick diverse chart types (mix of bar, line, pie, scatter, choropleth).

RULES:

    CRITICAL SQL RULES — These are the most important rules. Follow them strictly:
      A. NEVER use table aliases (like T1, T2, p, oi, c, o). Always write full table names:
         "products", "order_items", "customers", "orders". SQLite handles full names fine in JOINs.
         Example: SELECT products.name, SUM(order_items.quantity) FROM products JOIN order_items ON products.product_id = order_items.product_id
      B. CRITICAL — ALWAYS quote string literals in WHERE/HAVING clauses with single quotes.
         Example: WHERE category = 'Electronics' (NOT WHERE category = Electronics).
         Unquoted string values cause SQL syntax errors. Numbers and column references should NOT be quoted.
         Correct: WHERE category = 'Electronics' AND quantity > 5
      C. CRITICAL — SQL COMPLETENESS: Write the ENTIRE query in one go. Never truncate or abbreviate.
         Every clause (SELECT, FROM, JOIN ... ON, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT)
         must be fully written. Incomplete SQL causes execution errors.
      D. Only write read-only SELECT queries. Never DML/DDL.

    General rules:
    1. ALWAYS call get_schema before writing SQL if you haven't seen the schema yet.
       This also discovers any user-uploaded tables.
    2. When a chart or diagram helps, call generate_chart or generate_flowchart.
    3. For ER diagrams, call generate_flowchart(diagram_type="er_diagram", schema=<get_schema result>).
       Pass the full result from get_schema (with 'success' and 'schema' keys) — the tool handles unwrapping.
    4. If execute_query returns success=false, fix the SQL and retry (up to 3 times).
    5. After getting data, write a short clear summary with real numbers.
    6. Suggest one follow-up question the user might ask next.
    7. Be concise. Let charts and diagrams do the heavy lifting.
    8. CLARIFYING QUESTIONS: If the user's query is ambiguous (e.g. "show me sales" without specifying
       a time period, ask a short clarifying question instead of guessing.
    9. MULTI-HOP CONTEXT: Pay close attention to pronouns like "them", "those", "that", "these"
       in follow-up questions. They refer to entities from the previous turn, not all data.
    10. CROSS-DB QUERIES: The sample DB and uploads DB are attached together in SQLite.
        You can JOIN across them using fully qualified table names (e.g. "uploads.my_table").
    11. DOCUMENTS (RAG): When a user asks about document/report content, call retrieve_context
        to search uploaded PDF/TXT/MD files. Use the passages to inform your answer and cite the
        filename. You can combine document context with database results.
    12. KEEP REASONING BRIEF: Do not write long chains of thought before calling a tool.
        Call the tool immediately — tool arguments must be complete and never truncated.
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
                    "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter", "choropleth", "scatter_mapbox", "auto"]},
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
                "description": "Generate a Mermaid ER diagram (from get_schema result), a decision tree (from question/branches), or a process-flow diagram (from ordered steps).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "diagram_type": {"type": "string", "enum": ["er_diagram", "decision_tree", "process_flow"]},
                        "schema": {"type": "object", "description": "For er_diagram: pass the FULL result from get_schema (with success and schema keys)."},
                        "question": {"type": "string", "description": "For decision_tree: the root question."},
                        "branches": {"type": "array", "description": "For decision_tree: list of {label, children?} dicts representing decision branches.", "items": {"type": "object"}},
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
    {
        "type": "function",
        "function": {
            "name": "forecast_data",
            "description": "Predict future values from time-series data. Pass the SQL result data array, OR provide a SQL query to execute first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}, "description": "Row dicts from execute_query result. Required unless 'sql' is provided."},
                    "date_col": {"type": "string", "description": "Column with dates."},
                    "value_col": {"type": "string", "description": "Column with numeric values to forecast."},
                    "periods": {"type": "integer", "description": "Number of future periods to predict (default 5)."},
                    "sql": {"type": "string", "description": "Alternative to 'data': a SQL query that returns time-series data with date_col and value_col. The query is executed first, then forecast runs on results."},
                },
                "required": ["date_col", "value_col"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_data",
            "description": "Compare two sets of query results side-by-side (e.g. two time periods, two segments).",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_a": {"type": "array", "items": {"type": "object"}, "description": "First segment rows."},
                    "data_b": {"type": "array", "items": {"type": "object"}, "description": "Second segment rows."},
                    "label_a": {"type": "string", "description": "Label for first segment (e.g. 'This Quarter')."},
                    "label_b": {"type": "string", "description": "Label for second segment (e.g. 'Last Quarter')."},
                    "value_col": {"type": "string", "description": "Numeric column to compare."},
                    "category_col": {"type": "string", "description": "Optional category column for breakdown."},
                },
                "required": ["data_a", "data_b", "value_col"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_context",
            "description": "Search uploaded PDF/TXT/MD documents (RAG) for passages relevant to a query. Use when the user asks about uploaded documents, reports, or policy content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to find relevant document passages."},
                    "top_k": {"type": "integer", "description": "Number of top passages to return (default 5)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_quality",
            "description": "Scan the database for data quality issues: nulls, duplicates, and outlier values.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate a structured data storytelling report with summary stats and insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "object"}},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "question": {"type": "string", "description": "The original question."},
                    "chart_titles": {"type": "array", "items": {"type": "string"}, "description": "Titles of charts included."},
                },
                "required": ["data", "columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auto_ml_forecast",
            "description": "Train a LinearRegression model on a table to forecast a numeric column. Returns a forecast plot with 95% confidence intervals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name to train on."},
                    "target_col": {"type": "string", "description": "Numeric column to forecast."},
                    "date_col": {"type": "string", "description": "Optional date column for time-based forecasting."},
                    "periods": {"type": "integer", "description": "Number of future periods to predict (default 6)."},
                },
                "required": ["table", "target_col"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_dashboard",
            "description": "Generate multiple charts from a list of chart specifications (each with title, sql, chart_type, x, y). Use when the user wants a multi-chart dashboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specs": {
                        "type": "array",
                        "description": "List of chart specs: each with title, sql, chart_type, x, y.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "sql": {"type": "string"},
                                "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter", "choropleth", "scatter_mapbox"]},
                                "x": {"type": "string"},
                                "y": {"type": "string"},
                            },
                            "required": ["title", "sql", "chart_type"],
                        },
                    },
                },
                "required": ["specs"],
            },
        },
    },
]

def run_agent_turn(
    user_message: str,
    history: List[Dict[str, Any]],
    tracer: AgentTracer,
    language: str = "en",
    username: str = "",
    file_mode: bool = False,
) -> Dict[str, Any]:
    lang_instruction = LANGUAGES.get(language, "")
    user_context = ""
    if file_mode:
        user_context = (
            f"\nCURRENT MODE: Ask from Uploaded File. "
            f"The user ({username or 'shared'}) wants to ask questions ONLY about their uploaded data.\n"
            f"- Call get_schema first to discover their uploaded tables (prefixed with 'my.' or 'uploads.').\n"
            f"- Focus all answers and queries on their uploaded data only.\n"
        )
    elif username:
        user_context = (
            f"\nCurrent user: {username}. "
            f"They have personal uploads (prefixed with 'my.' in schema) and "
            f"shared uploads (prefixed with 'uploads.' in schema) available.\n"
        )
    system_content = SYSTEM_PROMPT_TEMPLATE.format(lang_instruction=lang_instruction) + user_context
    tool_impl = _build_tool_impl(username)

    messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": user_message}]

    charts: List[Dict[str, Any]] = []
    diagrams: List[str] = []
    sql_queries: List[Dict[str, Any]] = []
    sql_retry_count = 0
    tool_iterations = 0

    while True:
        try:
            msg = _call_llm(messages, TOOLS)
        except Exception as e:
            return {
                "reply": f"⚠️ Sorry, I encountered an error contacting the LLM provider (**{LLM_PROVIDER}**).\n\n> {e}\n\nPlease check your API key and try again.",
                "charts": charts,
                "diagrams": diagrams,
                "sql_queries": sql_queries,
            }

        tool_calls, raw_tool_calls = _coerce_message_tool_calls(msg)
        if not tool_calls:
            return {
                "reply": msg.content or "",
                "charts": charts,
                "diagrams": diagrams,
                "sql_queries": sql_queries,
            }

        tool_iterations += 1
        if tool_iterations > MAX_TOOL_ITERATIONS:
            return {
                "reply": "I ran too many tool steps without reaching a final answer. Please try a narrower question.",
                "charts": charts,
                "diagrams": diagrams,
                "sql_queries": sql_queries,
            }

        messages.append({
            "role": "assistant",
            "content": "" if raw_tool_calls else msg.content or "",
            "tool_calls": [_tool_call_message(tc, f"call_{i}") for i, tc in enumerate(tool_calls)],
        })
        tool_results = []

        for i, tc in enumerate(tool_calls):
            tool_name = _tool_call_name(tc)
            tool_input = _tool_call_input(tc)
            tool_call_id = _tool_call_id(tc, f"call_{i}")

            with timed() as t:
                fn = tool_impl.get(tool_name)
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
            if tool_name == "auto_ml_forecast" and result.get("success"):
                charts.append(result["figure"])
            if tool_name == "forecast_data" and result.get("success"):
                if result.get("figure"):
                    charts.append(result["figure"])
            if tool_name == "build_dashboard" and result.get("success"):
                for c in result.get("charts", []):
                    if "figure" in c:
                        charts.append(c["figure"])

            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": _safe_json_dumps(result),
            })

        messages.extend(tool_results)


def get_llm_status() -> Dict[str, Any]:
    has_key = bool(os.getenv("OPENAI_API_KEY")) or bool(os.getenv("ANTHROPIC_API_KEY"))
    provider = LLM_PROVIDER
    model = NVIDIA_MODEL if provider == "nvidia" else (OPENAI_MODEL if provider == "openai" else ANTHROPIC_MODEL)
    display = LLM_DISPLAY_NAMES.get(provider, f"{provider}/{model}")
    return {"connected": has_key, "provider": provider, "model": model, "display": display}
