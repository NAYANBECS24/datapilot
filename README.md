# Eunoia — Conversational BI Agent

**iTech AI Innovation Hackathon 2026** · *"Building Intelligent LLM Agents for Database Interaction & Visualization"*

**Team — Parth**

Chat in plain English → agent writes & runs SQL → renders charts/diagrams → explains insights. Built with self-healing SQL, real-time streaming, transparent agent traces, glassmorphism UI, and a living pinned dashboard.

[![Tests](https://img.shields.io/badge/tests-86%20passing-brightgreen)](https://github.com/NAYANBECS24/datapilot)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Live App](https://img.shields.io/badge/live-app-blueviolet)](https://datapilot-cxlnroofhvbh95qbkyhccg.streamlit.app/)

---

## Features

| Category | Feature | Status |
|---|---|---|
| **Core** | Natural language → SQL agent | ✅ |
| | Real-time streaming responses | ✅ Word-level animation via `st.write_stream()` |
| | Self-healing SQL retry loop | ✅ Failed queries auto-fix via LLM (3 attempts) |
| | SQL truncation detection | ✅ Catches incomplete JOINs & unbalanced parens before SQLite |
| | Live Agent Trace sidebar | ✅ Every tool call with latency — proves the agent is really working |
| | Glass-box SQL transparency | ✅ Every generated SQL shown in collapsible panel |
| | Chat Persistence & Multi-Chat Sessions | ✅ Auto-saves every conversation, new/load/delete from sidebar |
| **Charts & Visuals** | 7 chart types | ✅ Bar, line, pie, scatter, choropleth, scatter_mapbox, auto |
| | Forecast auto-chart | ✅ `forecast_data` returns a Plotly figure, auto-displayed in chat |
| | Smart chart recommendation | ✅ Auto-detects time-series, proportions, categories, location data |
| | Geographic Maps | ✅ Choropleth (country/state) + scatter_mapbox (lat/lon) |
| | Schema-grounded ER diagrams | ✅ Deterministic from real foreign keys |
| | Decision tree diagrams | ✅ Branching decision trees for conditional logic |
| | Process flow diagrams | ✅ Order-to-delivery pipelines |
| **ML & Analytics** | ML Forecasting | ✅ LinearRegression with 95% CI, R² score, standard error |
| | Predictive Forecasting | ✅ Trend-based forecast (next N periods) via numpy polyfit |
| | Data Quality Scanner | ✅ Null, duplicate, and outlier (z-score ±2σ) detection per table |
| | Anomaly Detection | ✅ Statistical z-score scan flags outliers in any series |
| | Comparative Analysis | ✅ Side-by-side segment comparison with % change |
| | Data Storytelling Reports | ✅ Narrative combining metrics + insights |
| **Data Upload** | Upload CSV | ✅ Import any CSV as a queryable table |
| | Upload Excel (.xlsx/.xls) | ✅ Direct upload — no conversion needed |
| | Upload SQLite DB | ✅ Import entire `.db` files |
| | RAG Document Search | ✅ Upload PDF/TXT/MD → ChromaDB vector search (ONNX, no API needed) |
| | Data Preview on Upload | ✅ Preview first 5 rows after every import |
| **Auth & Isolation** | Login & Register Portal | ✅ Multi-user auth with SHA-256 password hashing |
| | Per-User Data Isolation | ✅ Each user has private `uploads/{username}/uploads.db` |
| | Shared Database mode | ✅ Team-accessible common upload area |
| | Ask from Uploaded File mode | ✅ Agent focuses only on your uploaded data |
| **UI/UX** | Dashboard Builder (NL) | ✅ Describe a dashboard → auto-plans 2–4 charts → renders in 2-column grid |
| | Pin-to-Dashboard | ✅ Any chart → pin → persistent BI dashboard |
| | Dashboard HTML export | ✅ Download full dashboard as HTML |
| | Schema Visual Browser | ✅ Tree view with tables, columns, keys, relationships |
| | One-Click Chart Presets | ✅ Bar/Line/Pie/Scatter buttons for every table in My Data |
| | Smart Query Suggestions | ✅ Dynamic schema-aware suggestions on empty chat |
| | SQL Editor Mode | ✅ Edit any generated SQL and re-run instantly |
| | SQL Explain | ✅ LLM explains any SQL query in plain English |
| | Export charts as PNG / data as CSV | ✅ One-click download under every chart |
| | PDF report export | ✅ Full conversation exported as PDF |
| | Markdown conversation export | ✅ Copy/share conversations |
| | Glassmorphism UI | ✅ Premium dark/light glass design with animations |
| | Multi-language chat | ✅ English, Hindi, Spanish, French, German |
| | Voice input | ✅ Browser Speech Recognition (Chrome, Edge, Safari) |
| **Infrastructure** | Multi-DB support | ✅ SQLite, PostgreSQL, MySQL, MongoDB |
| | Read-only SQL guardrail | ✅ Blocks INSERT/UPDATE/DELETE/DROP/ALTER |
| | Robust JSON serialization | ✅ Numpy arrays, Plotly figures, ndarrays all safely serialized |
| | GitHub Actions CI | ✅ Auto-runs 86 tests on every push |
| | Docker support | ✅ Dockerfile + docker-compose.yml |

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

## Architecture

```
User → Login / Register
       │
       ▼
┌──────────────────────────────┐   tool calls    ┌──────────────────────────────┐
│   Streamlit UI (app.py)       │ ◄─────────────  │   Agent (agent.py)           │
│                              │                 │                              │
│  ┌────────────────────────┐  │                 │  ┌────────────────────────┐  │
│  │ 💬 Chat                │  │                 │  │ get_schema              │  │
│  │ 🗂️ My Data              │  │                 │  │ execute_query           │  │
│  │ 📌 Dashboard (pinned)   │  │                 │  │ generate_chart          │  │
│  │ 📊 Data Profiler        │  │                 │  │ generate_flowchart      │  │
│  │ 🤖 Auto Insights        │  │                 │  │ explain_data            │  │
│  │ 📄 Documents            │  │                 │  │ forecast_data           │  │
│  │ 📈 Dashboards (NL)      │  │                 │  │ compare_data            │  │
│  │                        │  │                 │  │ retrieve_context (RAG)  │  │
│  │ Sidebar:                │  │                 │  │ scan_quality            │  │
│  │ trace, upload, modes    │  │                 │  │ generate_report         │  │
│  └────────────────────────┘  │                 │  │ auto_ml_forecast        │  │
│                              │                 │  │ build_dashboard         │  │
│  Auth: users.db (SHA-256)    │                 │  └────────────────────────┘  │
│  Uploads: uploads/{user}/    │                 │                              │
│  Mermaid / Plotly / PDF/CSV  │                 │  Self-healing retry          │
└──────────────────────────────┘                 │  User-aware context          │
        │                                        │  (personal/shared/file)      │
        └────────────────────────────────────────┴──────────────────────────────┘
                                                             │
                                                             ▼
                        ┌───────────────────────────────────────────────────────┐
                        │  Database Layer                                       │
                        │  SQLite (sample_ecommerce.db) │ Uploads/{user}/       │
                        │  Uploads/shared/ │ PostgreSQL │ MySQL │ MongoDB       │
                        └───────────────────────────────────────────────────────┘
```

### Layer breakdown
- **Auth:** `auth/auth.py` — password hashing (SHA-256), user registration/login, per-user upload directories with login persistence across page reloads
- **Frontend:** `app.py` — Streamlit with 7 tabs, sidebar trace/logs, upload (CSV/Excel/DB/Docs), multi-chat sessions, file manager, SQL editor, chart presets, theme toggle, voice input
- **Orchestration:** `agent.py` — LLM tool-use loop with multi-provider support (NVIDIA/OpenAI/Anthropic), streaming, self-healing SQL retry, user-aware context (personal/shared/file mode), clarifying questions, multi-hop reasoning, cross-DB joins
- **Tools (12):** 12 pure function tools in `tools/*.py` — schema discovery, SQL execution, charting (7 types + auto-recommend), flowcharts (ER/process/decision), insights, forecasting, comparison, data quality scanning, report generation, ML forecasting, RAG document search, dashboard builder
- **Database abstraction:** `tools/db_manager.py` — unified interface for SQLite, PostgreSQL, MySQL, MongoDB
- **Data layer:** SQLite sample e-commerce DB (12,456 rows, 9 tables) + per-user `uploads/{username}/uploads.db` + shared `uploads/shared/uploads.db`
- **Observability:** `trace/tracer.py` — dataclass-based agent trace logger with step/event tracking

---

## Project Structure
```
eunoia/
├── app.py                   Streamlit UI (7 tabs, sidebar, auth gate, uploads)
├── agent.py                 LLM orchestration (tool loop, streaming, retry, 12 tools)
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── auth/
│   ├── __init__.py
│   └── auth.py              Login/register with SHA-256, auto-seed defaults, per-user dirs
├── example_data/
│   ├── employee_sales.csv    Sample employee sales performance data
│   ├── customer_feedback.csv Sample customer feedback & ratings
│   └── store_inventory.csv   Sample store inventory data
├── tools/
│   ├── __init__.py
│   ├── db_manager.py        Multi-DB abstraction (SQLite/PostgreSQL/MySQL/MongoDB)
│   ├── schema_tool.py       Schema discovery — tables, columns, FKs + upload merging
│   ├── query_tool.py        SQL execution, validation, CSV/Excel/DB upload, per-user paths
│   ├── chart_tool.py        generate_chart — bar/line/pie/scatter/choropleth/scatter_mapbox/auto
│   ├── flowchart_tool.py    generate_flowchart — ER/process-flow/decision-tree diagrams
│   ├── insight_tool.py      explain_data + detect_anomalies + generate_auto_insights
│   ├── analytics_tool.py    generate_forecast (polyfit) + compare_segments
│   ├── quality_tool.py      scan_quality — nulls/duplicates/outliers (±2σ)
│   ├── report_tool.py       generate_report — data storytelling narrative
│   ├── rag_tool.py          upload_document + retrieve_context + list/delete/clear docs
│   ├── ml_tool.py           auto_ml_forecast — LinearRegression with 95% CI
│   └── dashboard_tool.py    build_dashboard + plan_dashboard_llm — NL multi-chart builder
├── db/
│   ├── seed_db.py           Sample e-commerce dataset generator (12,456 rows)
│   ├── check_db.py          Database validation helper
│   └── sample_ecommerce.db  Pre-seeded SQLite database (9 tables)
├── uploads/
│   ├── shared/              Common upload area (all users)
│   └── {username}/          Private per-user upload area (+ rag/ + chats/)
├── trace/
│   └── tracer.py            Agent observability / trace logging (timed, events)
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
python tools/chart_tool.py       # generates all 7 chart types
python tools/flowchart_tool.py   # prints ER + process-flow + decision-tree Mermaid
python tools/insight_tool.py     # runs anomaly detection + auto insights on sample data
python tools/ml_tool.py          # trains forecast model on order_items table
python -m pytest tests/ -v       # 86 tests, all passing
```

---

## Login & Multi-User Portal

Eunoia starts with a login/register screen. Users must sign up before accessing the app.

- **Login page:** Full-screen animated CSS wallpaper (gradient background, data grid overlay, chart bars, line chart, floating dots) with glassmorphism card (`backdrop-filter: blur(24px)`)
- **Registration:** Username (min 3 chars) + password (min 4 chars), stored with SHA-256 hashing in `auth/users.db`
- **Login persistence:** Username stored in `st.query_params["user"]` — survives page reloads until explicit Logout
- **Default users:** `admin/admin123` and `nayan/nayan` auto-seeded on fresh deploy
- **Session:** Logout clears all session state
- **Footer:** "Team — Parth" displayed on both login and main pages

---

## Per-User Data Isolation

| Upload Mode | Storage Path | Access |
|---|---|---|
| **Personal** | `uploads/{username}/uploads.db` | Only that user |
| **Shared** | `uploads/shared/uploads.db` | All users |

Toggle between **Personal** and **Shared** mode in the sidebar. The schema tool auto-discovers both:
- Tables prefixed with `my.` → personal uploads
- Tables prefixed with `uploads.` → shared uploads

User-specific data also includes:
- RAG vector stores at `uploads/{username}/rag/chroma/`
- Chat persistence at `uploads/{username}/chats/{chat_id}.json`

---

## Tabs Overview

### 💬 Chat
The main interface. Type natural language questions → agent plans tool calls → streams answers word-by-word with real-time chart/diagram rendering. Features:
- Welcome hero with schema-aware query suggestions
- Collapsible SQL panels per query (with Edit/Explain buttons)
- Chart/diagram rendered inline
- Pin-to-Dashboard for any chart
- Export: PNG, CSV, Markdown, PDF
- Query history & favorites sidebar

### 🗂️ My Data
Schema visual browser showing all data sources:
- **Sample E-Commerce DB** — 9 tables, 12,456 rows
- **My Uploads** — personal CSV/Excel/DB uploads
- **Shared Uploads** — team-accessible common data

Each table shows: row count, column tree with types, primary keys, foreign keys. Features:
- **🔍 Preview** — collapsible first 10 rows
- **One-click chart presets** — Bar/Line/Pie/Scatter buttons
- **❌ Delete** — per-table and "Clear All" buttons
- **Upload Guide** tab with format reference

### 📌 Dashboard
Persistent BI dashboard built from pinned charts. Drag/drop reorder, HTML export, full-page print-ready view.

### 📊 Data Profiler
- **Column Analysis** — type, null count, unique count, min/max/mean per table
- **Data Quality Scanner** — `scan_quality` checks all tables for nulls, duplicates, outliers

### 🤖 Auto Insights
- **Auto Insights** — one-click revenue/trends/anomalies report
- **Data Storytelling** — focus-area driven narrative report with metrics + insights

### 📄 Documents
Uploaded PDF/TXT/MD file browser with:
- File listing (name, size KB)
- **🔍 Chunks** — view first 10 indexed chunks with inline preview
- Per-document delete + Clear All

### 📈 Dashboards
Two AI-powered tools:
- **ML Forecast** — pick table + numeric column → LinearRegression forecast with 95% CI
- **NL Dashboard Builder** — describe a dashboard → LLM plans 2–4 charts → renders in 2-column grid

---

## Uploading Data

### CSV
1. **Sidebar → Upload CSV** — select a `.csv` file
2. Optionally rename the table (defaults to filename)
3. Table appears in My Data under "My Uploads"
4. Ask questions in chat — the agent will discover and query it

### Excel (.xlsx / .xls)
Same flow as CSV. Optionally specify a sheet name. Uses openpyxl.

### SQLite Database
1. **Sidebar → Upload SQLite DB**
2. Optionally label it
3. All tables from the database are imported and available
4. Tables appear with `my.` prefix for personal mode

### Documents (PDF / TXT / MD)
1. **Sidebar → Upload Document**
2. Text is chunked (600 chars, 80 overlap) → embedded via ChromaDB ONNX (`all-MiniLM-L6-v2`)
3. Ask: *"What does the report say about X?"* → agent calls `retrieve_context` → answers with filename citations

---

## Example Data for Upload Testing

Eunoia comes with sample CSV files in the `example_data/` folder you can upload to test the system:

| File | Description | Sample Queries |
|---|---|---|
| `employee_sales.csv` | Employee sales performance by quarter | *"Show me top sales employees by region"*, *"Who had the highest sales in Q3?"* |
| `customer_feedback.csv` | Product reviews and ratings | *"What's the average rating per product category?"*, *"Show me unresolved complaints"* |
| `store_inventory.csv` | Store stock levels and suppliers | *"Which products are below reorder level?"*, *"Show me total stock value by category"* |

Upload any of these via **Sidebar → Upload CSV** and query them instantly.

---

## RAG — Document Search (Retrieval-Augmented Generation)

Eunoia searches **unstructured documents** using vector embeddings — no external API needed.

**How it works:**
1. Upload a PDF/TXT/MD file via **Sidebar → Upload Document**
2. Text is chunked (600 chars, 80 char overlap) and embedded using ChromaDB's built-in ONNX `all-MiniLM-L6-v2`
3. The agent's `retrieve_context` tool searches the per-user vector store for relevant passages
4. Results are grounded in your documents — the agent cites source filenames

**Example queries:**
- *"What does the Q3 report say about revenue growth?"*
- *"Summarize the key findings from the annual report"*
- *"Show sales data from the database and compare with the forecast in the PDF"*

---

## SQL Editor Mode

Every generated SQL query has an **✏️ Edit** button. Click to open a text editor with the SQL pre-filled — modify, then click **▶️ Run** to execute immediately. Results render in a DataFrame below the editor.

## SQL Explain

Every SQL query also has a **💡 Explain SQL** button. Click for a plain-English explanation from the LLM — great for learning SQL or understanding complex joins.

---

## Chat Persistence & Multi-Chat Sessions

Every conversation is **auto-saved** to disk after each turn. Chats survive page refreshes and browser restarts.

The sidebar's **Chat Sessions** panel lets you:
- **➕ New Chat** — start fresh while preserving history
- **💾 Save** — manually save at any point
- Click any saved chat to load it (title + message count shown)
- **🗑️** — delete old sessions

Chats are named automatically from the first user message. Stored at `uploads/{username}/chats/{chat_id}.json`.

---

## ML Forecasting

Train a **LinearRegression** model on any table and numeric column, then forecast with 95% confidence intervals.

- Available in the **Dashboards** tab under "ML Forecast"
- Also callable from chat via the `auto_ml_forecast` agent tool
- Returns: R² score, standard error, forecast table, and interactive Plotly chart with actuals + forecast + CI band
- Auto-detects date frequency (daily/weekly/monthly/quarterly/yearly)
- Uses scikit-learn: `pip install scikit-learn`

**Example:** *"Predict sales for the next 6 months"* → agent calls `auto_ml_forecast` → returns forecast plot + metrics.

---

## Geographic Maps

Two new map chart types in the agent's toolkit:

| Type | When | Requirements |
|---|---|---|
| **Choropleth** | Country/state/region data | Location column → color value |
| **Scatter mapbox** | Lat/Lon coordinates | Latitude + longitude + optional size |

- Auto-detected by column name (country, state, region, lat, latitude)
- OpenStreetMap tiles via Plotly's `carto-positron` style
- Available in chat via `generate_chart(chart_type="choropleth" | "scatter_mapbox")`

**Example:** *"Show revenue by country on a map"* → agent queries → calls `generate_chart(data, chart_type="choropleth", x="country", y="revenue")`

---

## NL Dashboard Builder

Describe a dashboard in natural language — Eunoia plans 2–4 diverse charts and renders them in a responsive 2-column grid.

- Available in the **Dashboards** tab
- Backend: `plan_dashboard_llm()` → LLM generates structured chart specs → `build_dashboard()` executes SQL + renders Plotly charts
- Also callable directly from chat via the `build_dashboard` agent tool

**Example prompts:**
- *"Show me monthly revenue, revenue by category, top products, and order status breakdown"*
- *"Give me a sales overview with revenue trends, category breakdown, and top customers"*
- *"Show customer distribution by city on a map with revenue per product category"*

---

## Agent Intelligence

### Clarifying Questions
When a query is ambiguous (e.g., *"Show me sales"* without a time period), the agent asks a short clarifying question instead of guessing.

### Multi-Hop Context
The agent tracks pronouns across turns. *"Show top customers"* → *"Which are from Mumbai?"* → understands "which" = top customers.

### Cross-DB Joins
The sample DB and uploads DB are SQLite-attached. The agent can write queries that `JOIN` across both — e.g., `SELECT * FROM orders JOIN uploads.my_table`.

### Self-Healing SQL
If `execute_query` returns an error, the agent automatically retries with a corrected SQL query (up to 3 attempts). SQL truncation is caught before reaching the database — `validate_query` checks for unbalanced parentheses and incomplete JOIN clauses, returning actionable error messages the LLM can fix.

---

## Smart Query Suggestions

When the chat is empty, Eunoia reads the actual database schema and generates relevant questions dynamically (e.g., "Show me revenue by Electronics" if the Electronics category exists). Falls back to 8 static examples if the schema read fails.

---

## Try These Queries

### Sales Analysis
- *"Show me the top 5 products by revenue"*
- *"What's the average order value per city?"*
- *"Show me monthly revenue trend for this year"*
- *"Show me revenue breakdown by product category"*

### Database Understanding
- *"Draw me the ER diagram for this database"*
- *"Which tables are related to customers?"*
- *"What's the schema of the orders table?"*

### Process & Decision Visualization
- *"Create a flowchart showing how an order moves through our system"*
- *"Create a decision tree for prioritizing which products to restock based on sales velocity and profit margin"*

### ML Forecasting
- *"Predict revenue for the next 6 months"*
- *"Forecast order volume from order_items"*
- *"Show me monthly orders and predict next quarter"*

### Geographic Maps
- *"Show me revenue by country on a map"*
- *"Plot customers by city on a map"*

### Dashboards
- *"Build me a dashboard with monthly revenue, category breakdown, top products, and order status"*
- *"Show me a sales overview with trends, categories, and customer stats"*

### Anomaly Detection
- *"Show me daily revenue for last week"* → then click **Data Whisperer** scan in sidebar
- *"Scan for anomalies in monthly revenue"*

### Inventory
- *"Show me products with stock below 50 units"*
- *"Which customers have placed the most orders?"*

### Comparative
- *"Compare this quarter's sales to last quarter"*
- *"Compare revenue by category between Q1 and Q2"*

### Data Quality
- *"Scan the database for data quality issues"*

### Documents (RAG)
- *"What does the uploaded report say about revenue growth?"*
- *"Summarize the key findings from the uploaded document"*

### Uploaded Data (try with example_data CSVs)
- *"Show me top sales employees by region"*
- *"Which products are below reorder level?"*
- *"What's the average rating per product category?"*
- *"Show me unresolved customer complaints"*

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| LLM | NVIDIA (default) / OpenAI / Anthropic | Multiple providers via `LLM_PROVIDER` env var |
| Frontend | Streamlit | Fastest chat UI with chart + streaming support |
| Charts | Plotly | Interactive, zoom, hover, PNG export, 7 chart types |
| Diagrams | Mermaid.js | ER diagrams, process flows, decision trees |
| Database | SQLite + PostgreSQL + MySQL + MongoDB | Multi-DB via connection string |
| Embeddings | ChromaDB (ONNX all-MiniLM-L6-v2) | Zero external API calls, fully offline RAG |
| ML | scikit-learn (LinearRegression) | Simple, fast, interpretable forecasting |
| PDF | fpdf2 | Conversation report export |
| Deployment | Docker + Streamlit Cloud | Reproducible + free hosting |

---

## Streaming Responses

Eunoia streams responses word-by-word for a ChatGPT-like experience:
- Tool calls run under a spinner (typically 1–3 seconds)
- Final reply streams with 15ms word-level animation via `st.write_stream()`
- Charts, diagrams, and SQL render immediately after streaming completes

---

## Multi-Database Support

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

Enable **Voice Input** in Settings (`🎤 Voice ON`). Click **Start** and speak your query — the browser's built-in Speech Recognition transcribes and submits it automatically. Works in Chrome, Edge, and Safari.

---

## LLM Providers

| Provider | Env Variable(s) | Default Model |
|---|---|---|
| NVIDIA (free, default) | `OPENAI_API_KEY=nvapi-...`<br>`NVIDIA_MODEL=...` (optional) | `meta/llama-3.1-70b-instruct` |
| OpenAI | `OPENAI_API_KEY=sk-...` + `LLM_PROVIDER=openai` | `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY=sk-ant-...` + `LLM_PROVIDER=anthropic` | `claude-3-5-haiku-latest` |

---

## Export Options

| Format | Where | How |
|---|---|---|
| PNG | Under each chart | ⬇ PNG button |
| CSV | Under each chart | ⬇ CSV button |
| Markdown | Chat tab | 📥 Markdown copy button |
| PDF | Chat tab | 📕 PDF Report button (whole conversation) |
| HTML | Dashboard tab | 📥 Export HTML button (pinned charts) |
| Profile CSV | Profiler tab | ⬇ Profile CSV button |
| Insight JSON | Auto Insights tab | ⬇ JSON button |

---

## Deployment

### Streamlit Community Cloud (free)

**Live app:** [datapilot-cxlnroofhvbh95qbkyhccg.streamlit.app](https://datapilot-cxlnroofhvbh95qbkyhccg.streamlit.app/)

1. Push this repo to GitHub:
```bash
git remote add origin https://github.com/NAYANBECS24/datapilot.git
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

## License

MIT — built for the iTech AI Innovation Hackathon 2026.  
**Team — Parth**
