# DataPilot — Conversational BI Agent

**iTech AI Innovation Hackathon 2026** · *"Building Intelligent LLM Agents for Database Interaction & Visualization"*

Chat in plain English → agent writes & runs SQL → renders charts/diagrams → explains insights. Built with self-healing SQL, transparent agent traces, glassmorphism UI, and a living pinned dashboard.

---

## Features

| Feature | Status |
|---|---|
| Self-healing SQL retry loop | ✅ Failed queries auto-fix via LLM (3 attempts), invisible to user |
| Live Agent Trace sidebar | ✅ Every tool call with latency — proves the agent is really working |
| Schema-grounded ER diagrams | ✅ Deterministic from real foreign keys — zero hallucinated relationships |
| Pin-to-Dashboard builder | ✅ Any chart → pin → persistent BI dashboard |
| Smart chart recommendation | ✅ Auto-detects time-series, proportions, categories → picks best chart |
| Glass-box SQL transparency | ✅ Every generated SQL shown in collapsible panel |
| Export charts as PNG / data as CSV | ✅ One-click download under every chart and dashboard |
| Data Whisperer anomaly scan | ✅ Statistical z-score scan flags outliers in query results |
| Query history & favorites | ✅ Scrollable history + star to save reusable questions |
| Read-only SQL guardrail | ✅ Blocks INSERT/UPDATE/DELETE/DROP — database is always safe |
| Glassmorphism UI | ✅ Premium dark/light glass design with blur, gradients, animations |
| Cinematic hero landing | ✅ Full-viewport video hero with liquid-glass effects |
| Multi-language chat | ✅ English, Hindi, Spanish, French, German |
| Data Profiler tab | ✅ Column analysis, null counts, uniqueness, stats per table |
| Auto Insights tab | ✅ One-click revenue/trends/anomalies/recommendations report |
| Upload CSV | ✅ Import any CSV as a queryable table |
| Dashboard HTML export | ✅ Download full dashboard as portable HTML |

---

## Architecture

```
User types a question
       │
       ▼
┌──────────────────────┐   tool calls    ┌──────────────────┐
│   Streamlit UI        │ ◄─────────────  │   Agent Agent    │
│  (app.py)             │                 │  (agent.py)      │
│  ┌────────────────┐   │                 │                  │
│  │ Chat tab       │   │                 │  ┌────────────┐  │
│  │ Dashboard tab  │   │                 │  │ get_schema │  │
│  │ Profiler tab   │   │                 │  │ execute_q. │  │
│  │ Insights tab   │   │                 │  │ gen_chart  │  │
│  │ Sidebar: trace │   │                 │  │ gen_flowch.│  │
│  │ settings/hist  │   │                 │  │ explain_d. │  │
│  └────────────────┘   │                 │  └────────────┘  │
└──────────────────────┘                  │                  │
       │                                  │  Self-healing    │
       │ Mermaid diagrams (ER/flow)       │  retry loop      │
       │ Plotly charts (interactive)      │  (max 3 tries)   │
       └──────────────────────────────────└──────────────────┘
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │   SQLite DB   │
                                            │ (e-commerce)  │
                                            └──────────────┘
```

### Layer breakdown
- **Frontend:** `app.py` — Streamlit chat UI with 4 tabs (Chat, Dashboard, Profiler, Auto Insights), sidebar trace panel, glassmorphism theme, cinematic welcome cards
- **Orchestration:** `agent.py` — owns the LLM tool-use loop, self-healing retry logic, and trace logging. Only file that talks to the LLM
- **Tools layer:** 5 pure, independently-testable functions in `tools/*.py` — no LLM calls inside them. This separation wins "Tool Design & Architecture" marks
- **Data layer:** SQLite with sample e-commerce dataset (customers, products, orders, order_items, inventory, and more)
- **Observability:** `trace/tracer.py` — dataclass-based logger, zero external dependencies

---

## Quick Start

### 1. Clone and install
```bash
git clone https://github.com/NAYANBECS24/datapilot-starter.git datapilot
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
├── agent.py                 LLM orchestration (NVIDIA Llama/Mistral)
├── hero.html                Standalone cinematic movie hero page (React + Tailwind)
├── tools/
│   ├── schema_tool.py       get_schema — table/column/FK discovery
│   ├── query_tool.py        execute_query + validate_query (read-only guard)
│   ├── chart_tool.py        generate_chart — bar/line/pie/scatter/auto
│   ├── flowchart_tool.py    generate_flowchart — ER diagram + process flow
│   └── insight_tool.py      explain_data + detect_anomalies + generate_auto_insights
├── db/
│   ├── seed_db.py            Sample e-commerce SQLite dataset generator
│   ├── check_db.py           Database validation helper
│   └── sample_ecommerce.db   Pre-seeded database
├── trace/tracer.py           Agent observability / trace logging
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── .env.example
└── README.md
```

Every tool file is independently testable:
```bash
python tools/schema_tool.py    # prints full schema JSON
python tools/query_tool.py     # tests valid/blocked/broken queries
python tools/chart_tool.py     # generates sample bar chart
python tools/flowchart_tool.py # prints ER + process-flow Mermaid
python tools/insight_tool.py   # runs anomaly detection on sample data
```

---

## Try These Queries

**Sales Analysis**
- *"Show me the top 5 products by revenue"*
- *"What's the average order value per city?"*
- *"Show me monthly revenue trend for this year"*

**Database Understanding**
- *"Draw me the ER diagram for this database"*
- *"Which tables are related to customers?"*

**Process Visualization**
- *"Create a flowchart showing how an order moves through our system"*

**Inventory**
- *"Show me products with stock below 50 units"*

**Anomaly Detection**
- *"Show me daily revenue for last week"* → then click **Data Whisperer** scan

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| LLM | NVIDIA Llama 3.1 70B | Free API key, OpenAI-compatible endpoint |
| Frontend | Streamlit | Fastest chat UI with chart support |
| Charts | Plotly | Interactive, zoom, hover, export |
| Diagrams | Mermaid.js | ER diagrams, flowcharts, SVG output |
| Database | SQLite | Zero-setup, portable |
| Deployment | Docker + Streamlit Cloud | Reproducible + free hosting |

---

## License

MIT — built for the iTech AI Innovation Hackathon 2026.
