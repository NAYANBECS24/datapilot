# DataPilot — Conversational BI Agent

**iTech AI Innovation Hackathon 2026** · *"Building Intelligent LLM Agents for Database Interaction & Visualization"*

Chat in plain English → agent writes & runs SQL → renders charts/diagrams → explains insights. Built with self-healing SQL, real-time streaming, transparent agent traces, glassmorphism UI, and a living pinned dashboard.

---

## Features

| Feature | Status |
|---|---|
| Real-time streaming responses | ✅ Word-level animation via `st.write_stream()` |
| Self-healing SQL retry loop | ✅ Failed queries auto-fix via LLM (3 attempts) |
| Live Agent Trace sidebar | ✅ Every tool call with latency — proves the agent is really working |
| Schema-grounded ER diagrams | ✅ Deterministic from real foreign keys — zero hallucinated relationships |
| Decision tree diagrams | ✅ Branching decision trees for conditional logic |
| Process flow diagrams | ✅ Order-to-delivery pipelines |
| Pin-to-Dashboard builder | ✅ Any chart → pin → persistent BI dashboard |
| Smart chart recommendation | ✅ Auto-detects time-series, proportions, categories → picks best chart |
| 4 chart types | ✅ Bar, line, pie, scatter (bonus) |
| Glass-box SQL transparency | ✅ Every generated SQL shown in collapsible panel |
| Export charts as PNG / data as CSV | ✅ One-click download under every chart and dashboard |
| PDF report export | ✅ Full conversation exported as PDF |
| Data Whisperer anomaly scan | ✅ Statistical z-score scan flags outliers |
| Query history & favorites | ✅ Scrollable history + star to save reusable questions |
| Multi-DB support | ✅ SQLite, PostgreSQL, MySQL, **MongoDB** (bonus) |
| Voice input | ✅ Browser Speech Recognition (Chrome/Edge/Safari) |
| Read-only SQL guardrail | ✅ Blocks INSERT/UPDATE/DELETE/DROP |
| Glassmorphism UI | ✅ Premium dark/light glass design with blur, gradients, animations |
| Multi-language chat | ✅ English, Hindi, Spanish, French, German |
| Data Profiler tab | ✅ Column analysis, null counts, uniqueness, stats per table |
| Auto Insights tab | ✅ One-click revenue/trends/anomalies/recommendations report |
| Upload CSV | ✅ Import any CSV as a queryable table |
| Dashboard HTML export | ✅ Download full dashboard as portable HTML |
| Collaborative share | ✅ Copy conversation to clipboard |
| Docker support | ✅ Dockerfile + docker-compose.yml |
| Unit tests | ✅ 85 tests, all passing |

---

## Architecture

```
User types a question
       │
       ▼
┌──────────────────────┐   tool calls    ┌──────────────────────┐
│   Streamlit UI        │ ◄─────────────  │   Agent (agent.py)   │
│  (app.py)             │                 │                      │
│  ┌────────────────┐   │                 │  ┌────────────────┐  │
│  │ Chat tab       │   │                 │  │ get_schema     │  │
│  │ Dashboard tab  │   │                 │  │ execute_query  │  │
│  │ Profiler tab   │   │                 │  │ generate_chart │  │
│  │ Insights tab   │   │                 │  │ generate_flow..│  │
│  │ Sidebar: trace │   │                 │  │ explain_data   │  │
│  │ settings/hist  │   │                 │  └────────────────┘  │
│  └────────────────┘   │                 │                      │
└──────────────────────┘                  │  Self-healing        │
       │                                  │  retry loop          │
       │ Mermaid diagrams (ER/flow/tree)  │  (max 3 tries)       │
       │ Plotly charts (interactive)      │  Streaming output    │
       │ PDF/Markdown/CSV/PNG export      │                      │
       └──────────────────────────────────┴──────────────────────┘
                                                    │
                                                    ▼
                    ┌──────────────────────────────────────────┐
                    │  Database Layer                          │
                    │  SQLite │ PostgreSQL │ MySQL │ MongoDB    │
                    │  (selectable via connection string)       │
                    └──────────────────────────────────────────┘
```

### Layer breakdown
- **Frontend:** `app.py` — Streamlit chat UI with 4 tabs (Chat, Dashboard, Profiler, Auto Insights), sidebar trace panel, dark/light theme, voice input, streaming responses
- **Orchestration:** `agent.py` — LLM tool-use loop with streaming support, self-healing retry logic, multi-provider support (NVIDIA/OpenAI/Anthropic), trace logging
- **Tools layer:** 5 pure, independently-testable functions in `tools/*.py` — no LLM calls inside them
- **Database abstraction:** `tools/db_manager.py` — unified interface for SQLite, PostgreSQL, MySQL, and MongoDB
- **Data layer:** SQLite with sample e-commerce dataset (customers, products, orders, order_items, inventory, suppliers, reviews, payments, shipping)
- **Observability:** `trace/tracer.py` — dataclass-based logger, zero external dependencies

---

## Quick Start

### 1. Clone and install
```bash
git clone https://github.com/NAYANBECS24/datapilot.git
cd datapilot
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up environment
```bash
cp .env.example .env
```

Edit `.env` and add your NVIDIA API key:

```
OPENAI_API_KEY=nvapi-...
NVIDIA_MODEL=meta/llama-3.1-70b-instruct
```

Get a free key at [build.nvidia.com](https://build.nvidia.com).

### 3. Seed the database
```bash
python db/seed_db.py
```

### 4. Launch
```bash
streamlit run app.py
```

Open **http://localhost:8501**

---

## Docker (alternative)
```bash
docker compose up --build
# visit http://localhost:8501
```

---

## Project Structure
```
datapilot/
├── app.py                   Streamlit frontend (chat, dashboard, profiler, insights)
├── agent.py                 LLM orchestration with streaming + multi-provider
├── .streamlit/
│   ├── config.toml          Streamlit Cloud server config
│   └── secrets.toml.example Template for cloud secrets
├── tools/
│   ├── db_manager.py        Multi-DB abstraction (SQLite/PostgreSQL/MySQL/MongoDB)
│   ├── schema_tool.py       get_schema — table/column/FK discovery
│   ├── query_tool.py        execute_query + validate_query (read-only guard) + CSV upload
│   ├── chart_tool.py        generate_chart — bar/line/pie/scatter/auto
│   ├── flowchart_tool.py    generate_flowchart — ER diagram + process flow + decision tree
│   └── insight_tool.py      explain_data + detect_anomalies + generate_auto_insights
├── db/
│   ├── seed_db.py           Sample e-commerce SQLite dataset generator
│   ├── check_db.py          Database validation helper
│   └── sample_ecommerce.db  Pre-seeded database (12,456 rows, 9 tables)
├── trace/
│   └── tracer.py            Agent observability / trace logging
├── tests/
│   ├── test_chart_tool.py
│   ├── test_flowchart_tool.py
│   ├── test_insight_tool.py
│   ├── test_query_tool.py
│   ├── test_schema_tool.py
│   └── test_tracer.py
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

Every tool file is independently testable:
```bash
python tools/schema_tool.py      # prints full schema JSON
python tools/query_tool.py       # tests valid/blocked/broken queries
python tools/chart_tool.py       # generates sample bar chart
python tools/flowchart_tool.py   # prints ER + process-flow + decision-tree Mermaid
python tools/insight_tool.py     # runs anomaly detection on sample data
python -m pytest tests/ -v       # 85 tests
```

---

## Try These Queries

**Sales Analysis**
- *"Show me the top 5 products by revenue"*
- *"What's the average order value per city?"*
- *"Show me monthly revenue trend for this year"*
- *"Show me revenue breakdown by product category"*

**Database Understanding**
- *"Draw me the ER diagram for this database"*
- *"Which tables are related to customers?"*
- *"What's the schema of the orders table?"*

**Process & Decision Visualization**
- *"Create a flowchart showing how an order moves through our system"*
- *"Create a decision tree for prioritizing which products to restock based on sales velocity and profit margin"*

**Inventory**
- *"Show me products with stock below 50 units"*
- *"Which customers have placed the most orders?"*

**Anomaly Detection**
- *"Show me daily revenue for last week"* → then click **Data Whisperer** scan in sidebar

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| LLM | NVIDIA (default) / OpenAI / Anthropic | Multiple providers via `LLM_PROVIDER` env var |
| Frontend | Streamlit | Fastest chat UI with chart + streaming support |
| Charts | Plotly | Interactive, zoom, hover, PNG export |
| Diagrams | Mermaid.js | ER diagrams, flowcharts, decision trees |
| Database | SQLite + PostgreSQL + MySQL + MongoDB | Multi-DB via connection string |
| PDF | fpdf2 | Conversation report export |
| Deployment | Docker + Streamlit Cloud | Reproducible + free hosting |

---

## Streaming Responses

DataPilot streams responses word-by-word for a ChatGPT-like experience:
- Tool calls run under a spinner (typically 1–3 seconds)
- Final reply streams with 15ms word-level animation via `st.write_stream()`
- Charts, diagrams, and SQL render immediately after streaming completes

---

## Multi-Database Support

DataPilot connects to 4 database types simultaneously:

| Type | Connection String |
|---|---|
| **SQLite** (default) | `sqlite:///path/to/database.db` |
| **PostgreSQL** | `postgresql://user:password@host:5432/dbname` |
| **MySQL** | `mysql://user:password@host:3306/dbname` |
| **MongoDB** | `mongodb://user:password@host:27017/dbname` |

Set via `DATABASE_URL` in `.env` or the **Settings → Database Connection** field in the UI.

Install optional drivers:
```bash
pip install psycopg2-binary    # PostgreSQL support
pip install pymysql            # MySQL support
pip install pymongo            # MongoDB support
```

---

## Voice Input

Enable **Voice Input** in Settings (`🎤 Voice ON`). Click **Start** and speak your query — the browser's built-in Speech Recognition will transcribe and submit it automatically. Works in Chrome, Edge, and Safari.

---

## LLM Providers

| Provider | Env Variable | Default Model |
|---|---|---|
| NVIDIA (free, default) | `OPENAI_API_KEY=nvapi-...` | `meta/llama-3.1-70b-instruct` |
| OpenAI | `OPENAI_API_KEY=sk-...` + `LLM_PROVIDER=openai` | `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY=sk-ant-...` + `LLM_PROVIDER=anthropic` | `claude-3-5-haiku-latest` |

---

## Export Options

| Format | Where | How |
|---|---|---|
| PNG | Under each chart | ⬇ PNG button |
| CSV | Under each chart | ⬇ CSV button |
| Markdown | Chat tab | 📥 Markdown button |
| PDF | Chat tab | 📕 PDF Report button |
| HTML | Dashboard tab | 📥 Export HTML button |
| Profile CSV | Profiler tab | ⬇ Profile CSV button |
| Insight JSON | Auto Insights tab | ⬇ JSON button |

---

## Deployment

### Streamlit Community Cloud (free)

1. Push this repo to GitHub:
```bash
git remote add origin https://github.com/YOUR_USERNAME/datapilot.git
git push -u origin master
```

2. Go to [streamlit.io/cloud](https://streamlit.io/cloud)

3. Click **New app** → select your repo → set main file to `app.py`

4. Under **Advanced settings → Secrets**, paste:
```toml
OPENAI_API_KEY = "nvapi-..."    # your NVIDIA API key
```

5. Deploy — your app will be live at `https://<name>.streamlit.app` in ~2 minutes

### Docker
```bash
docker compose up --build
# visit http://localhost:8501
```

---

## Evaluation Criteria Coverage

| Criteria | Weight | How DataPilot Addresses It |
|---|---|---|
| Functionality | 30% | All 5 required tools working, accurate SQL generation, 4 chart types, 3 diagram types, multi-turn conversations |
| Tool Design & Architecture | 25% | Clean function schemas with typed params, modular tools/agent split, extensible multi-DB abstraction, no LLM calls in tools |
| Visualization Quality | 20% | Plotly interactive charts with auto-detection, Mermaid diagrams, glassmorphism dark/light theme |
| User Experience | 15% | Streaming responses, animated UI, voice input, multi-language, anomaly scanner, dashboard builder |
| Innovation & Creativity | 10% | Self-healing SQL retry, decision trees, MongoDB support, PDF export, trace sidebar, collaborative share |

---

## License

MIT — built for the iTech AI Innovation Hackathon 2026.
