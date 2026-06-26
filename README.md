# DataPilot — Conversational BI Agent

**iTech AI Innovation Hackathon 2026** · *"Building Intelligent LLM Agents for Database Interaction & Visualization"*

**Team — Parth**

Chat in plain English → agent writes & runs SQL → renders charts/diagrams → explains insights. Built with self-healing SQL, real-time streaming, transparent agent traces, glassmorphism UI, and a living pinned dashboard.

---

## Features

| Feature | Status |
|---|---|
| Real-time streaming responses | ✅ Word-level animation via `st.write_stream()` |
| Self-healing SQL retry loop | ✅ Failed queries auto-fix via LLM (3 attempts) |
| Live Agent Trace sidebar | ✅ Every tool call with latency — proves the agent is really working |
| Schema-grounded ER diagrams | ✅ Deterministic from real foreign keys |
| Decision tree diagrams | ✅ Branching decision trees for conditional logic |
| Process flow diagrams | ✅ Order-to-delivery pipelines |
| Pin-to-Dashboard builder | ✅ Any chart → pin → persistent BI dashboard |
| Smart chart recommendation | ✅ Auto-detects time-series, proportions, categories |
| 4 chart types | ✅ Bar, line, pie, scatter (bonus) |
| Glass-box SQL transparency | ✅ Every generated SQL shown in collapsible panel |
| Export charts as PNG / data as CSV | ✅ One-click download under every chart |
| PDF report export | ✅ Full conversation exported as PDF |
| Data Whisperer anomaly scan | ✅ Statistical z-score scan flags outliers |
| Query history & favorites | ✅ Scrollable history + star to save |
| Multi-DB support | ✅ SQLite, PostgreSQL, MySQL, **MongoDB** (bonus) |
| Voice input | ✅ Browser Speech Recognition |
| Read-only SQL guardrail | ✅ Blocks INSERT/UPDATE/DELETE/DROP |
| Glassmorphism UI | ✅ Premium dark/light glass design |
| Multi-language chat | ✅ English, Hindi, Spanish, French, German |
| Data Profiler tab | ✅ Column analysis, null counts, stats per table |
| Auto Insights tab | ✅ One-click revenue/trends report |
| Upload CSV | ✅ Import any CSV as a queryable table |
| Upload CSV | ✅ **Primary method.** Export from Excel/Sheets → upload → query immediately |
| Upload SQLite DB | ✅ Only if you have a `.db` file |
| **Login & Register Portal** | ✅ Multi-user auth with password hashing |
| **Per-User Data Isolation** | ✅ Each user has private uploads |
| **Shared Database** | ✅ Team-accessible common upload area |
| **Ask from Uploaded File Mode** | ✅ Agent focuses only on your uploaded data |
| **My Data Tab** | ✅ Browse all tables, row counts, columns |
| **Smart Query Suggestions** | ✅ Dynamic schema-aware suggestions on empty chat |
| **Data Quality Scanner** | ✅ Null, duplicate, and outlier detection per table |
| **Predictive Forecasting** | ✅ Trend-based forecast (next N periods) from query results |
| **Comparative Analysis** | ✅ Side-by-side segment comparison with % change |
| **Data Storytelling Reports** | ✅ Narrative report combining metrics + insights |
| **Clarifying Questions** | ✅ Agent asks when query is ambiguous |
| **Multi-Hop Context** | ✅ Understands "them", "those", "that" across turns |
| **Cross-DB Joins** | ✅ Query across sample DB + uploads in one SQL |
| Dashboard HTML export | ✅ Download full dashboard as HTML |
| Collaborative share | ✅ Copy conversation to clipboard |
| Docker support | ✅ Dockerfile + docker-compose.yml |
| Unit tests | ✅ 85 tests, all passing |

---

## Architecture

```
User → Login / Register
       │
       ▼
┌──────────────────────────┐   tool calls    ┌──────────────────────────┐
│   Streamlit UI (app.py)   │ ◄─────────────  │   Agent (agent.py)       │
│                           │                 │                          │
│  ┌────────────────────┐   │                 │  ┌────────────────────┐  │
│  │ Chat tab           │   │                 │  │ get_schema         │  │
│  │ My Data tab        │   │                 │  │ execute_query      │  │
│  │ Dashboard tab      │   │                 │  │ generate_chart     │  │
│  │ Profiler tab       │   │                 │  │ generate_flowchart  │  │
│  │ Insights tab       │   │                 │  │ explain_data       │  │
│  │ Sidebar: trace,    │   │                 │  └────────────────────┘  │
│  │ upload, modes      │   │                 │                          │
│  └────────────────────┘   │                 │  Self-healing retry      │
└──────────────────────────┘                  │  User-aware context      │
       │                                      │  (personal/shared/file)  │
       │ Auth: users.db (password hashing)    │                          │
       │ Uploads: uploads/{user}/ or shared/  └──────────────────────────┘
       │ Mermaid/Plotly/PDF/CSV export                          │
       └─────────────────────────────────────────────────────────┘
                                                                  │
                                                                  ▼
                         ┌────────────────────────────────────────────┐
                         │  Database Layer                            │
                         │  SQLite (sample) │ Uploads/{user} │ Shared │
                         │  PostgreSQL │ MySQL │ MongoDB              │
                         └────────────────────────────────────────────┘
```

### Layer breakdown
- **Auth:** `auth/auth.py` — password hashing (SHA-256), user registration/login, per-user upload directories
- **Frontend:** `app.py` — Streamlit with 5 tabs (Chat, My Data, Dashboard, Profiler, Auto Insights), sidebar trace, upload modes, dark/light theme
- **Orchestration:** `agent.py` — LLM tool-use loop with user-aware context (personal/shared/file mode), self-healing retry, multi-provider
- **Tools layer:** 5 pure functions in `tools/*.py` — no LLM calls inside them
- **Database abstraction:** `tools/db_manager.py` — unified interface for SQLite, PostgreSQL, MySQL, MongoDB
- **Data layer:** SQLite sample e-commerce DB + per-user `uploads/{username}/uploads.db` + shared `uploads/shared/uploads.db`
- **Observability:** `trace/tracer.py` — dataclass-based logger

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

**Live demo:** [datapilot-cxlnroofhvbh95qbkyhccg.streamlit.app](https://datapilot-cxlnroofhvbh95qbkyhccg.streamlit.app/)

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
├── auth/
│   ├── __init__.py
│   └── auth.py              Login/register, password hashing, user management
├── .streamlit/
│   ├── config.toml          Streamlit Cloud server config
│   └── secrets.toml.example Template for cloud secrets
├── tools/
│   ├── db_manager.py        Multi-DB abstraction (SQLite/PostgreSQL/MySQL/MongoDB)
│   ├── schema_tool.py       get_schema — table/column/FK discovery + upload merging
│   ├── query_tool.py        execute_query + validate_query + CSV/DB upload + per-user paths
│   ├── chart_tool.py        generate_chart — bar/line/pie/scatter/auto
│   ├── flowchart_tool.py    generate_flowchart — ER diagram + process flow + decision tree
│   ├── insight_tool.py      explain_data + detect_anomalies + generate_auto_insights
│   ├── analytics_tool.py    generate_forecast + compare_segments
│   ├── quality_tool.py      scan_quality — nulls/duplicates/outliers
│   └── report_tool.py       generate_report — data storytelling narrative
├── db/
│   ├── seed_db.py           Sample e-commerce SQLite dataset generator
│   ├── check_db.py          Database validation helper
│   └── sample_ecommerce.db  Pre-seeded database (12,456 rows, 9 tables)
├── uploads/                 Per-user and shared upload directories
│   ├── shared/              Common upload area (all users)
│   └── {username}/          Private per-user upload area
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

## Login & Multi-User Portal

DataPilot starts with a login/register screen. Users must sign up before accessing the app.

- **Registration:** Username (min 3 chars) + password (min 4 chars), stored with SHA-256 hashing
- **Login:** Authenticates against `auth/users.db`
- **Session:** Persists per browser session; logout clears all session state
- **Footer:** Team name displayed on both login and main pages

---

## Per-User Data Isolation

Every user gets their own private upload space:

| Upload Mode | Storage Path | Access |
|---|---|---|
| **Personal** | `uploads/{username}/uploads.db` | Only that user |
| **Shared** | `uploads/shared/uploads.db` | All users |

Toggle between **Personal** and **Shared** mode in the sidebar. The schema tool auto-discovers both:
- Tables prefixed with `my.` → personal uploads
- Tables prefixed with `uploads.` → shared uploads

---

## My Data Tab

The **My Data** tab (2nd tab) shows every available data source in one place:

- **Sample E-Commerce DB** — 9 tables, 12,456 rows
- **My Uploads** — your personal CSV/DB uploads
- **Shared Uploads** — team-accessible common data

Each table shows: name, row count, column list (expandable via popover), and file path.

---

## Ask from Uploaded File Mode

Toggle **"Ask from Uploaded File"** in the sidebar to switch the agent into file-only mode:

- The agent ignores the sample e-commerce database
- It only queries tables from your uploaded data (`my.*` or `uploads.*`)
- Perfect for: *"Upload your Excel → switch mode → ask questions about it"*
- The system prompt dynamically changes to guide the agent's focus

---

## Smart Query Suggestions

When the chat is empty, DataPilot reads the actual database schema and generates relevant questions dynamically (e.g., "Show me revenue by Electronics" if the Electronics category exists). Falls back to 8 static examples if the schema read fails.

---

## Predictive Forecasting

New tool: `forecast_data` — uses numpy polyfit to predict future values from time-series data.

**Example:** *"Forecast revenue for next 5 months"* → agent queries monthly revenue → calls `forecast_data` → returns projected values with trend direction (up/down/flat).

---

## Comparative Analysis

New tool: `compare_data` — compares two query result sets side-by-side with absolute and percent change.

**Example:** *"Compare this quarter's sales to last quarter"* → agent queries both periods → calls `compare_data` → shows total, avg, max, min, top categories for each segment + % change.

---

## Data Storytelling Reports

New tool + UI: `generate_report` combines summary statistics, top categories, and chart references into a single narrative.

- Available in the **Auto Insights** tab under "Data Storytelling Report"
- Type a focus area (e.g. "sales performance") → generates a structured story
- Includes key metrics, insights, and a list of visualizations included

---

## Data Quality Scanner

New tool + UI: `scan_quality` checks every table for:

| Check | What It Finds |
|---|---|
| **Null values** | Columns with missing data and counts |
| **Duplicate rows** | Exact row duplicates |
| **Outlier values** | Values exceeding ±2σ (z-score) in numeric columns |

Available in the **Data Profiler** tab under "Data Quality Scanner" → click "Scan Quality".

---

## Clarifying Questions, Multi-Hop Context & Cross-DB Joins

These are built into the agent's system prompt (no separate UI):

- **Clarifying:** *"Show me sales"* → *"Which time period?"* instead of guessing
- **Multi-Hop:** *"Show top customers"* → *"Which are from Mumbai?"* → understands "which" = top customers
- **Cross-DB Joins:** The sample DB and uploads DB are SQLite-attached — agent can write `JOIN uploads.my_table` in a single query

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

## License

MIT — built for the iTech AI Innovation Hackathon 2026.  
**Team — Parth**
