import json
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from tools.schema_tool import get_schema
from tools.query_tool import execute_query
from tools.chart_tool import generate_chart
from tools.flowchart_tool import generate_flowchart
from tools.insight_tool import prepare_explanation_context, detect_anomalies
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

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia").lower()


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
            max_tokens=4000,
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


def run_agent_turn_stream(
    user_message: str,
    history: List[Dict[str, Any]],
    tracer: AgentTracer,
    language: str = "en",
):
    lang_instruction = LANGUAGES.get(language, "")
    system_content = SYSTEM_PROMPT_TEMPLATE.format(lang_instruction=lang_instruction)

    messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": user_message}]

    charts = []
    diagrams = []
    sql_queries = []
    sql_retry_count = 0

    while True:
        try:
            msg = _call_llm(messages, TOOLS)
        except Exception as e:
            yield {"type": "reply", "content": f"⚠️ Sorry, I encountered an error contacting the LLM provider (**{LLM_PROVIDER}**).\n\n> {e}\n\nPlease check your API key and try again."}
            return

        if not msg.tool_calls:
            yield {"type": "charts", "content": charts}
            yield {"type": "diagrams", "content": diagrams}
            yield {"type": "sql_queries", "content": sql_queries}
            yield {"type": "stream_start", "content": ""}
            for chunk in _chunk_text(msg.content or ""):
                yield {"type": "stream", "content": chunk}
            yield {"type": "stream_end", "content": ""}
            return

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


def _call_openai_compat(client, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Any:
    response = client.chat.completions.create(
        model=model,
        max_tokens=4000,
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

SYSTEM_PROMPT_TEMPLATE = """{lang_instruction}You are DataPilot, a conversational BI copilot for a database.

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

RULES:
  1. ALWAYS call get_schema before writing SQL if you haven't seen the schema yet.
     This also discovers any user-uploaded tables.
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
]

TOOL_IMPL: Dict[str, Any] = {
    "get_schema": lambda **kw: get_schema(DB_PATH, conn_str=DB_CONN_STRING),

    "execute_query": lambda **kw: execute_query(DB_PATH, kw.get("sql", ""), conn_str=DB_CONN_STRING),

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
}


def run_agent_turn(
    user_message: str,
    history: List[Dict[str, Any]],
    tracer: AgentTracer,
    language: str = "en",
) -> Dict[str, Any]:
    lang_instruction = LANGUAGES.get(language, "")
    system_content = SYSTEM_PROMPT_TEMPLATE.format(lang_instruction=lang_instruction)

    messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": user_message}]

    charts: List[Dict[str, Any]] = []
    diagrams: List[str] = []
    sql_queries: List[Dict[str, Any]] = []
    sql_retry_count = 0

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


def get_llm_status() -> Dict[str, Any]:
    has_key = bool(os.getenv("OPENAI_API_KEY")) or bool(os.getenv("ANTHROPIC_API_KEY"))
    provider = LLM_PROVIDER
    model = NVIDIA_MODEL if provider == "nvidia" else (OPENAI_MODEL if provider == "openai" else ANTHROPIC_MODEL)
    display = LLM_DISPLAY_NAMES.get(provider, f"{provider}/{model}")
    return {"connected": has_key, "provider": provider, "model": model, "display": display}
