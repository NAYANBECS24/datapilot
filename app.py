import base64
import io
import json
import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

from agent import LANGUAGES, run_agent_turn, get_llm_status
from trace.tracer import AgentTracer
from tools.insight_tool import detect_anomalies, generate_auto_insights
from tools.query_tool import execute_query, csv_to_table, list_uploaded_tables, clear_uploads, import_db_file, drop_table, list_uploaded_files, _uploads_dir
from tools.schema_tool import get_schema
from tools.db_manager import DatabaseManager, validate_query
from auth.auth import register, login, get_user

st.set_page_config(
    page_title="DataPilot · Conversational BI Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-seed database if not present (works on Streamlit Cloud)
_db_path = os.path.join(os.path.dirname(__file__), "db", "sample_ecommerce.db")
if not os.path.exists(_db_path):
    try:
        from db.seed_db import main as seed_db
        seed_db()
    except Exception as e:
        pass

_DEFAULT = {
    "messages": [],
    "pinned": [],
    "trace_log": [],
    "query_history": [],
    "favorites": [],
    "dark_mode": True,
    "show_sql": True,
    "language": "en",
    "auto_insights": None,
    "db_conn_str": os.getenv("DATABASE_URL", ""),
    "voice_mode": False,
    "user": None,
    "auth_page": "login",
    "upload_mode": "personal",
    "file_mode": False,
}
for k, v in _DEFAULT.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.user:
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * {{ font-family: 'Inter', sans-serif; }}
        body {{ background: #0a0c14; }}
    </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center;font-weight:800;font-size:3rem;background:linear-gradient(135deg,#00d4aa,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>DataPilot</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#7a7d91;margin-bottom:2rem;'>Conversational BI Agent · iTech AI Hackathon 2026</p>", unsafe_allow_html=True)

        tab_log, tab_reg = st.tabs(["🔑 Login", "📝 Register"])
        with tab_log:
            with st.form("login_form"):
                lun = st.text_input("Username", placeholder="Enter your username")
                lpw = st.text_input("Password", type="password", placeholder="Enter your password")
                if st.form_submit_button("Login", use_container_width=True, type="primary"):
                    r = login(lun, lpw)
                    if r["success"]:
                        st.session_state.user = r["username"]
                        st.rerun()
                    else:
                        st.error(r["error"])
        with tab_reg:
            with st.form("register_form"):
                run = st.text_input("Choose a username", placeholder="Min 3 characters")
                rpw = st.text_input("Choose a password", type="password", placeholder="Min 4 characters")
                if st.form_submit_button("Register", use_container_width=True, type="primary"):
                    r = register(run, rpw)
                    if r["success"]:
                        st.success("Registered! Login now.")
                        st.session_state.auth_page = "login"
                    else:
                        st.error(r["error"])
    st.markdown('<div class="login-footer">🤖 Team — <strong>Parth</strong> · iTech AI Innovation Hackathon 2026</div>', unsafe_allow_html=True)
    st.stop()

mode = "dark" if st.session_state.dark_mode else "light"

_bg = "#0a0c14" if mode == "dark" else "#f4f5f9"
_bg2 = "#0f111b" if mode == "dark" else "#ffffff"
_text = "#e2e4ea" if mode == "dark" else "#1a1a2e"
_text2 = "#7a7d91" if mode == "dark" else "#6b6f82"
_accent = "#00d4aa"
_accent2 = "#7c3aed"
_accent_grad = "linear-gradient(135deg, #00d4aa, #7c3aed)"
_card_bg = "rgba(16, 18, 30, 0.88)" if mode == "dark" else "rgba(255, 255, 255, 0.92)"
_card_border = "rgba(255,255,255,0.05)" if mode == "dark" else "rgba(0,0,0,0.05)"
_input_bg = "rgba(22, 25, 42, 0.96)" if mode == "dark" else "rgba(255,255,255,0.96)"
_shadow = "0 8px 32px rgba(0,0,0,0.5)" if mode == "dark" else "0 8px 32px rgba(0,0,0,0.06)"

theme_css = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

    * {{ font-family: 'Inter', -apple-system, sans-serif; }}
    .stApp {{ background: {_bg}; color: {_text}; }}

    .main .block-container {{ padding: 1rem 2rem 8rem !important; max-width: 1160px; }}

    .gradient-bar {{
        position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
        height: 3px;
        background: {_accent_grad};
        box-shadow: 0 0 24px rgba(0,212,170,0.4);
    }}

    h1, h2, h3, h4 {{ color: {_text} !important; font-weight: 700 !important; letter-spacing: -0.02em; }}
    h1 {{ font-size: 1.8rem !important; }}
    p, li, .stMarkdown {{ color: {_text} !important; line-height: 1.6; }}

    .glass {{
        background: {_card_bg};
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid {_card_border};
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.6rem;
        transition: all 0.2s ease;
    }}
    .glass-hover:hover {{ border-color: rgba(0,212,170,0.15); }}

    .badge {{
        display: inline-flex; align-items: center; gap: 4px;
        padding: 2px 10px; border-radius: 20px; font-size: 10px; font-weight: 600;
    }}
    .badge-green {{ background: rgba(0,212,170,0.12); color: {_accent}; }}
    .badge-purple {{ background: rgba(124,58,237,0.12); color: {_accent2}; }}
    .badge-blue {{ background: rgba(59,130,246,0.12); color: #3b82f6; }}
    .badge-amber {{ background: rgba(245,158,11,0.12); color: #f59e0b; }}

    .status-dot {{
        display: inline-block; width: 7px; height: 7px; border-radius: 50%;
        margin-right: 6px; animation: pulse 2s infinite;
    }}
    .status-dot.online {{ background: {_accent}; box-shadow: 0 0 8px rgba(0,212,170,0.4); }}
    .status-dot.offline {{ background: #6b7280; }}

    ::-webkit-scrollbar {{ width: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: {'rgba(255,255,255,0.08)' if mode == 'dark' else 'rgba(0,0,0,0.08)'}; border-radius: 3px; }}

    footer, #MainMenu, header[data-testid="stHeader"], div[data-testid="stDecoration"], div[data-testid="stToolbar"], .st-emotion-cache-1kyxreq {{ display: none !important; }}

    /* ── WELCOME / ONBOARDING ── */
    .welcome-hero {{
        text-align: center; padding: 2rem 1rem 1.5rem;
        max-width: 700px; margin: 0 auto;
    }}
    .welcome-hero h1 {{
        font-size: 2.4rem !important; font-weight: 800 !important;
        background: {_accent_grad}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }}
    .welcome-hero p {{ font-size: 15px; color: {_text2}; margin-bottom: 0; }}
    .welcome-stats {{
        display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;
        margin: 1rem auto 0;
    }}
    .welcome-stat {{
        background: {_card_bg}; border: 1px solid {_card_border}; border-radius: 12px;
        padding: 0.5rem 1rem; text-align: center; min-width: 80px;
    }}
    .welcome-stat-val {{ font-size: 20px; font-weight: 700; color: {_accent}; }}
    .welcome-stat-lbl {{ font-size: 10px; color: {_text2}; text-transform: uppercase; letter-spacing: 0.05em; }}

    .welcome-cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 10px; max-width: 820px; margin: 1.5rem auto 0;
    }}
    .welcome-card {{
        background: {_card_bg};
        backdrop-filter: blur(16px);
        border: 1px solid {_card_border};
        border-radius: 14px;
        padding: 1rem 1.1rem;
        cursor: pointer;
        transition: all 0.25s ease;
        text-align: left;
    }}
    .welcome-card:hover {{
        border-color: {_accent};
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,212,170,0.08);
    }}
    .welcome-card-icon {{ font-size: 24px; margin-bottom: 6px; }}
    .welcome-card-title {{ font-size: 14px; font-weight: 600; color: {_text}; }}
    .welcome-card-desc {{ font-size: 12px; color: {_text2}; margin-top: 2px; }}

    /* ── CHAT MESSAGES ── */
    .msg-row {{ display: flex; margin-bottom: 0.85rem; animation: fadeIn 0.3s ease; }}
    .msg-row.user {{ justify-content: flex-end; }}
    .msg-row.assistant {{ justify-content: flex-start; }}

    .msg-bubble {{
        max-width: 88%; padding: 1rem 1.35rem; line-height: 1.65;
        font-size: 15px;
    }}
    .msg-bubble.user {{
        background: linear-gradient(135deg, {_accent}, #00b894);
        color: #000; font-weight: 500;
        border-radius: 20px 20px 6px 20px;
        box-shadow: 0 4px 20px rgba(0,212,170,0.25);
    }}
    .msg-bubble.assistant {{
        background: {_card_bg};
        backdrop-filter: blur(16px);
        border: 1px solid {_card_border};
        border-radius: 20px 20px 20px 6px;
        box-shadow: {_shadow};
    }}
    .msg-avatar {{
        width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
        background: {_accent_grad};
        display: flex; align-items: center; justify-content: center;
        font-size: 17px; margin-right: 10px; margin-top: 3px;
    }}

    .msg-time {{ font-size: 11px; color: {_text2}; margin-top: 6px; padding-left: 3px; }}

    .content-section {{ margin-top: 0.5rem; }}
    .content-label {{
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
        padding: 3px 10px; border-radius: 6px; margin-bottom: 6px;
    }}
    .content-label.sql {{ background: rgba(59,130,246,0.1); color: #3b82f6; }}
    .content-label.chart {{ background: rgba(0,212,170,0.1); color: {_accent}; }}
    .content-label.diagram {{ background: rgba(245,158,11,0.1); color: #f59e0b; }}

    /* ── ACTION BAR (under charts) ── */
    .action-bar {{
        display: flex; gap: 6px; flex-wrap: wrap;
        padding: 0.5rem 0 0;
    }}
    .action-btn {{
        display: inline-flex; align-items: center; gap: 4px;
        padding: 5px 12px; font-size: 12px; font-weight: 500;
        background: {'rgba(255,255,255,0.04)' if mode == 'dark' else 'rgba(0,0,0,0.03)'};
        border: 1px solid {_card_border}; border-radius: 8px;
        color: {_text2} !important; text-decoration: none !important;
        cursor: pointer; transition: all 0.2s ease;
    }}
    .action-btn:hover {{
        border-color: {_accent}; color: {_accent} !important;
        background: rgba(0,212,170,0.06);
    }}
    .action-btn.danger:hover {{ border-color: #ef4444; color: #ef4444 !important; }}

    /* ── CHAT INPUT / SUGGESTIONS ── */
    .suggestions-strip {{
        display: flex; flex-wrap: wrap; gap: 6px;
        margin-bottom: 0.5rem; padding: 0 2px;
    }}
    .suggestion-pill {{
        display: inline-flex; align-items: center; gap: 4px;
        padding: 5px 12px; font-size: 12px;
        background: {_card_bg};
        border: 1px solid {_card_border}; border-radius: 20px;
        color: {_text2}; cursor: pointer;
        transition: all 0.2s ease;
        white-space: nowrap;
    }}
    .suggestion-pill:hover {{
        border-color: {_accent}; color: {_accent};
        background: rgba(0,212,170,0.06);
        transform: translateY(-1px);
    }}

    .stChatInputContainer {{
        border: none !important; background: transparent !important;
        padding: 0.5rem 0 !important;
    }}
    div[data-testid="stChatInput"] {{
        border: 1px solid {_card_border} !important;
        background: {_input_bg} !important;
        backdrop-filter: blur(20px);
        border-radius: 18px !important;
        box-shadow: 0 8px 40px rgba(0,0,0,0.3) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    div[data-testid="stChatInput"]:focus-within {{
        border-color: {_accent} !important;
        box-shadow: 0 8px 40px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,212,170,0.15) !important;
    }}
    div[data-testid="stChatInput"] textarea {{
        background: transparent !important;
        color: {_text} !important;
        font-size: 15px !important;
        padding: 1rem 0.75rem !important;
        min-height: 56px !important;
    }}

    /* ── TYPING ── */
    .typing-indicator {{
        display: flex; align-items: center; gap: 6px;
    }}
    .typing-dots {{ display: flex; gap: 3px; }}
    .typing-dots span {{
        width: 7px; height: 7px; border-radius: 50%;
        background: {_accent}; display: inline-block;
        animation: bounce 1.4s ease-in-out infinite;
    }}
    .typing-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: 0.4s; }}

    /* ── BUTTONS ── */
    .stButton > button {{
        border-radius: 10px !important; font-weight: 500 !important; font-size: 13px !important;
        transition: all 0.2s ease !important;
        border: 1px solid {_card_border} !important;
        background: {_card_bg} !important;
        color: {_text} !important;
    }}
    .stButton > button:hover {{
        border-color: {_accent} !important;
        box-shadow: 0 0 20px rgba(0,212,170,0.1) !important;
    }}

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {_card_bg};
        backdrop-filter: blur(16px);
        border-radius: 12px;
        padding: 4px;
        border: 1px solid {_card_border};
        margin-bottom: 1rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 9px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 5px 14px !important;
        color: {_text2} !important;
    }}
    .stTabs [aria-selected="true"] {{
        background: {_accent_grad} !important;
        color: #000 !important;
        font-weight: 600 !important;
    }}

    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] > div:nth-child(1) {{
        background: {_card_bg};
        backdrop-filter: blur(16px);
        border-right: 1px solid {_card_border};
    }}
    section[data-testid="stSidebar"] .sidebar-content {{ background: transparent; }}

    .stSidebar .stExpander {{
        background: transparent !important; border: none !important;
    }}
    .stSidebar div[data-testid="stExpander"] {{
        border: none !important; background: transparent !important;
    }}
    .stSidebar .stExpander > div:first-child > div:first-child {{
        font-weight: 600 !important; font-size: 12px !important;
        color: {_text2} !important; letter-spacing: 0.02em;
    }}
    .stSidebar hr {{ border-color: {_card_border} !important; margin: 0.5rem 0; }}

    /* ── SIDEBAR TRACE ── */
    .trace-line {{
        position: relative; padding: 5px 0 5px 16px; margin-bottom: 2px;
        animation: fadeIn 0.25s ease;
    }}
    .trace-line::before {{
        content: ''; position: absolute; left: 5px; top: 8px; bottom: 4px;
        width: 1.5px;
        background: {'rgba(255,255,255,0.06)' if mode == 'dark' else 'rgba(0,0,0,0.06)'};
    }}
    .trace-dot {{
        position: absolute; left: -9px; top: 9px;
        width: 8px; height: 8px; border-radius: 50%;
        border: 2px solid {_bg2};
    }}
    .trace-dot.ok {{ background: {_accent}; }}
    .trace-dot.err {{ background: #ef4444; }}
    .trace-name {{ font-size: 11px; font-weight: 600; color: {_text}; }}
    .trace-detail {{ font-size: 10px; color: {_text2}; font-family: 'JetBrains Mono', monospace; }}
    .trace-meta {{ font-size: 9px; color: {_text2}; margin-top: 1px; }}

    /* ── SIDEBAR STATS ── */
    .sb-stats {{ display: flex; gap: 5px; margin: 0.4rem 0; }}
    .sb-stat {{
        flex: 1; text-align: center; padding: 5px 0;
        background: {'rgba(255,255,255,0.02)' if mode == 'dark' else 'rgba(0,0,0,0.02)'};
        border-radius: 8px; border: 1px solid {_card_border};
    }}
    .sb-stat-val {{ font-size: 15px; font-weight: 700; color: {_accent}; }}
    .sb-stat-lbl {{ font-size: 8px; color: {_text2}; text-transform: uppercase; letter-spacing: 0.06em; }}

    /* ── DASHBOARD ── */
    .dash-item {{
        background: {_card_bg};
        backdrop-filter: blur(16px);
        border: 1px solid {_card_border};
        border-radius: 14px;
        padding: 0.6rem;
        margin-bottom: 0.75rem;
        transition: all 0.25s ease;
    }}
    .dash-item:hover {{
        border-color: rgba(0,212,170,0.15);
        box-shadow: 0 6px 24px rgba(0,0,0,0.15);
    }}
    .dash-item-title {{
        font-size: 12px; font-weight: 600; color: {_text};
        padding: 0 0.4rem 0.4rem; border-bottom: 1px solid {_card_border};
        margin-bottom: 0.4rem;
    }}

    /* ── SELECT / CODE ── */
    .stSelectbox > div > div {{
        background: {'rgba(255,255,255,0.03)' if mode == 'dark' else 'rgba(0,0,0,0.03)'} !important;
        border: 1px solid {_card_border} !important;
        border-radius: 10px !important; color: {_text} !important;
    }}
    .stCodeBlock {{
        background: {'rgba(0,0,0,0.25)' if mode == 'dark' else 'rgba(0,0,0,0.03)'} !important;
        border-radius: 10px !important;
        border: 1px solid {_card_border} !important;
    }}
    .stCodeBlock code {{ font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important; }}

    .stAlert {{
        background: {_card_bg} !important;
        border: 1px solid {_card_border} !important;
        border-radius: 12px !important;
    }}

    .stPlotlyChart {{ background: transparent !important; border-radius: 10px; padding: 2px; }}
    .js-plotly-plot .plotly .main-svg {{ background: transparent !important; }}

    .metric-card {{
        background: {_card_bg}; border: 1px solid {_card_border}; border-radius: 12px;
        padding: 0.8rem; text-align: center;
    }}
    .metric-val {{
        font-size: 24px; font-weight: 700;
        background: {_accent_grad}; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .metric-lbl {{ font-size: 10px; color: {_text2}; margin-top: 3px; }}

    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes bounce {{ 0%,60%,100% {{ transform: translateY(0); }} 30% {{ transform: translateY(-7px); }} }}
    @keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
    .app-footer {{
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
        text-align: center; padding: 8px; font-size: 12px;
        background: {_bg2}; color: {_text2};
        border-top: 1px solid {_card_border};
    }}
    .login-footer {{
        text-align: center; padding: 20px; font-size: 12px; color: #7a7d91;
    }}
</style>
<div class="gradient-bar"></div>
"""
st.markdown(theme_css, unsafe_allow_html=True)

team_footer = '<div class="app-footer">🤖 Team — <strong>Parth</strong> · iTech AI Innovation Hackathon 2026</div>'
st.markdown(team_footer, unsafe_allow_html=True)

# ── HELPERS ──────────────────────────────────────────────────────────────

def render_mermaid(code: str) -> None:
    html = f"""<html><head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true,theme:"{'dark' if mode == 'dark' else 'neutral'}"}});</script>
<style>body{{margin:0;display:flex;justify-content:center;background:transparent}}.mermaid{{max-width:100%}}</style>
</head><body><div class="mermaid">{code}</div></body></html>"""
    st.html(html)


def fig_to_png_bytes(fig_dict: dict) -> bytes:
    fig = go.Figure(fig_dict)
    fig.update_layout(template="plotly_dark" if mode == "dark" else "plotly_white")
    buf = io.BytesIO()
    fig.write_image(buf, format="png", width=800, height=450, scale=2)
    return buf.getvalue()


def apply_chart_theme(fig):
    fig.update_layout(
        template="plotly_dark" if mode == "dark" else "plotly_white",
        font=dict(family="Inter, sans-serif", size=11),
        margin=dict(l=16, r=16, t=36, b=16),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _now() -> str:
    return datetime.now().strftime("%I:%M %p")


def _word_stream(text: str):
    words = text.split(" ")
    for i in range(0, len(words), 3):
        yield " ".join(words[i:i + 3]) + " "
        time.sleep(0.015)


def _get_font_path() -> str:
    paths = [
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    cache_dir = os.path.join(os.path.dirname(__file__), ".fonts")
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, "DejaVuSans.ttf")
    if not os.path.exists(cached):
        import urllib.request
        urls = [
            "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf",
            "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@master/ttf/DejaVuSans.ttf",
        ]
        downloaded = False
        for url in urls:
            try:
                urllib.request.urlretrieve(url, cached)
                downloaded = True
                break
            except Exception:
                continue
        if not downloaded:
            return None
    return cached


def _generate_pdf_report(messages: list) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    font_path = _get_font_path()
    if font_path:
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "", 16)
    else:
        pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(0, 212, 170)
    pdf.cell(0, 12, "DataPilot - Conversation Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(200, 200, 200)
    _fnt = "DejaVu" if font_path else "Helvetica"
    pdf.set_font(_fnt, "", 8)
    pdf.cell(0, 6, f"Generated {datetime.now().strftime('%b %d, %Y at %I:%M %p')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    for m in messages:
        if m["role"] == "user":
            pdf.set_fill_color(0, 212, 170)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(_fnt, "", 11)
            pdf.multi_cell(0, 7, f"You: {m.get('content', '')}", fill=True)
        else:
            pdf.set_fill_color(20, 22, 36)
            pdf.set_text_color(220, 220, 220)
            pdf.set_font(_fnt, "", 11)
            reply = m.get("reply", "")
            pdf.multi_cell(0, 7, f"DataPilot: {reply}", fill=True)
            for q in m.get("sql_queries", []):
                pdf.set_font("Courier", "", 8)
                pdf.set_text_color(100, 150, 255)
                pdf.multi_cell(0, 5, f"SQL: {q['sql']}")
        pdf.ln(3)

    return pdf.output()


SCHEMA_CACHE = None
def _get_schema():
    global SCHEMA_CACHE
    if SCHEMA_CACHE is None:
        SCHEMA_CACHE = get_schema(_db_path)
    return SCHEMA_CACHE

def _invalidate_schema_cache():
    global SCHEMA_CACHE
    SCHEMA_CACHE = None

def _stats():
    s = _get_schema()
    if s.get("success"):
        t = s["schema"]["tables"]
        return len(t), sum(len(c["columns"]) for c in t.values()), len(s["schema"].get("relationships", [])),
    return 0, 0, 0


# ── WELCOME SUGGESTIONS ──

@st.cache_data(show_spinner=False)
def _smart_suggestions() -> List[tuple]:
    try:
        s = get_schema(db_path=_db_path)
        if not s.get("success"):
            return _STATIC_CARDS
        tables = s["schema"]["tables"]
        cats = set()
        for tname, tinfo in tables.items():
            for c in tinfo.get("columns", []):
                if c.get("name") == "category":
                    try:
                        conn = sqlite3.connect(_db_path)
                        for r in conn.execute(f'SELECT DISTINCT category FROM "{tname}" WHERE category IS NOT NULL LIMIT 4'):
                            cats.add(str(r[0]))
                        conn.close()
                    except Exception:
                        pass

        cats_list = list(cats)[:3]
        dynamic = []
        if cats_list:
            dynamic.append(("📊", f"Category Breakdown", f"Show me revenue breakdown by {cats_list[0]}"))
            dynamic.append(("📊", "All Categories", "Show me revenue by product category"))
        dynamic.append(("🔮", "Forecast Revenue", "Forecast revenue for next 5 months"))
        dynamic.append(("📋", "Data Quality", "Scan the database for data quality issues"))
        if len(cats_list) > 1:
            dynamic.append(("📊", "Compare Categories", f"Compare sales between {cats_list[0]} and {cats_list[1]}"))
        return dynamic + _STATIC_CARDS[:4]
    except Exception:
        return _STATIC_CARDS

_STATIC_CARDS = [
    ("📊", "Top Products", "Show me the top 5 products by revenue"),
    ("📈", "Monthly Trend", "Show me monthly revenue trend for this year"),
    ("🏙️", "City Analysis", "What is the average order value per city?"),
    ("📦", "Low Stock", "Show me products with stock below 50 units"),
    ("👥", "Top Customers", "Which customers have placed the most orders?"),
    ("📐", "ER Diagram", "Draw me the ER diagram for this database"),
    ("🔄", "Order Flow", "Create a flowchart of how an order moves through our system"),
    ("🌳", "Decision Tree", "Create a decision tree for prioritizing which products to restock based on sales velocity and profit margin"),
]

WELCOME_CARDS = _smart_suggestions()
SUGGESTION_CHIPS = [c[2] for c in WELCOME_CARDS]


# ── SIDEBAR ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:0.15rem 0;">'
        f'<div style="width:36px;height:36px;border-radius:10px;background:{_accent_grad};'
        f'display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">📊</div>'
        f'<div><span style="font-size:17px;font-weight:700;">Data</span><span style="font-size:17px;font-weight:700;color:{_accent};">Pilot</span>'
        f'<span class="badge badge-green" style="margin-left:6px;font-size:9px;">v2</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    llm_status = get_llm_status()
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;font-size:11px;margin:4px 0 10px;color:{_text2};">'
        f'<span class="status-dot {"online" if llm_status["connected"] else "offline"}"></span>'
        f'{"Ready · " + llm_status["display"] if llm_status["connected"] else "API key needed"}'
        f'</div>',
        unsafe_allow_html=True,
    )

    t, c, f = _stats()
    st.markdown(
        f'<div class="sb-stats">'
        f'<div class="sb-stat"><div class="sb-stat-val">{t}</div><div class="sb-stat-lbl">Tables</div></div>'
        f'<div class="sb-stat"><div class="sb-stat-val">{c}</div><div class="sb-stat-lbl">Columns</div></div>'
        f'<div class="sb-stat"><div class="sb-stat-val">{f}</div><div class="sb-stat-lbl">Relations</div></div>'
        f'<div class="sb-stat"><div class="sb-stat-val">{len(st.session_state.pinned)}</div><div class="sb-stat-lbl">Pinned</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander("👤 Account", expanded=True):
        st.markdown(f'<span style="font-size:13px;">Logged in as <strong>{st.session_state.user}</strong></span>', unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    u1, u2 = st.columns(2)
    with u1:
        st.session_state.upload_mode = "personal" if st.button(
            "👤 Personal" if st.session_state.upload_mode != "personal" else "✅ Personal",
            use_container_width=True,
            key="mode_personal",
        ) else st.session_state.upload_mode
    with u2:
        st.session_state.upload_mode = "shared" if st.button(
            "🌐 Shared" if st.session_state.upload_mode != "shared" else "✅ Shared",
            use_container_width=True,
            key="mode_shared",
        ) else st.session_state.upload_mode

    st.session_state.file_mode = st.toggle(
        "📁 Ask from Uploaded File",
        value=st.session_state.file_mode,
        help="Focus the agent on your uploaded data. Ask questions only about your uploaded files.",
    )

    _current_user = st.session_state.user if st.session_state.upload_mode == "personal" else ""
    _upload_label = f" ({st.session_state.user})" if _current_user else " (shared)"

    st.divider()

    with st.expander("🔍 Agent Trace", expanded=True):
        if st.session_state.trace_log:
            items = []
            for ev in st.session_state.trace_log:
                dot = "ok" if ev["success"] else "err"
                icon = "✅" if ev["success"] else "❌"
                detail = ""
                if ev["detail"]:
                    detail = f'<div style="font-size:10px;color:#ef4444;margin-top:1px;">⚠️ {ev["detail"][:55]}</div>'
                items.append(
                    f'<div class="trace-line">'
                    f'<div class="trace-dot {dot}"></div>'
                    f'<div class="trace-name">{icon} {ev["tool_name"]}</div>'
                    f'<div class="trace-detail">{ev["input_summary"][:40]}</div>'
                    f'{detail}'
                    f'<div class="trace-meta">step {ev["step"]} · {ev["latency_ms"]}ms</div>'
                    f'</div>'
                )
            st.markdown(f'<div style="padding-left:12px;">{"".join(items)}</div>', unsafe_allow_html=True)
        else:
            st.caption("Ask a question to see the agent work.")

    with st.expander("⚙️ Settings", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🌙 Dark" if not st.session_state.dark_mode else "☀️ Light", use_container_width=True):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
        with c2:
            lbl = "🔍 SQL ON" if st.session_state.show_sql else "🔍 SQL OFF"
            if st.button(lbl, use_container_width=True):
                st.session_state.show_sql = not st.session_state.show_sql
        with c3:
            lbl2 = "🎤 Voice ON" if st.session_state.voice_mode else "🎤 Voice OFF"
            if st.button(lbl2, use_container_width=True):
                st.session_state.voice_mode = not st.session_state.voice_mode

        if not llm_status["connected"]:
            st.caption("LLM API Key")
            api_key = st.text_input(
                "NVIDIA API Key",
                type="password",
                placeholder="nvapi-...",
                label_visibility="collapsed",
                key="api_key_input",
            )
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                st.success("Key set! Ask a question below.")
                st.rerun()

        selected_lang = st.selectbox(
            "Language",
            options=list(LANGUAGES.keys()),
            format_func=lambda k: {"en": "English", "hi": "हिन्दी", "es": "Español", "fr": "Français", "de": "Deutsch"}.get(k, k),
            index=list(LANGUAGES.keys()).index(st.session_state.language),
            label_visibility="collapsed",
        )
        if selected_lang != st.session_state.language:
            st.session_state.language = selected_lang
            st.rerun()

        st.caption("Database Connection")
        default_db_url = f"sqlite:///{_db_path}"
        db_url = st.text_input(
            "Connection string",
            value=st.session_state.db_conn_str or default_db_url,
            label_visibility="collapsed",
            placeholder="sqlite:///path/to/db or postgresql://user:pass@host/db",
        )
        if db_url != st.session_state.db_conn_str:
            st.session_state.db_conn_str = db_url
            st.session_state.auto_insights = None
            _invalidate_schema_cache()
            st.toast("Database connection updated")

        db_type = "SQLite"
        if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
            db_type = "PostgreSQL"
        elif db_url.startswith("mysql://"):
            db_type = "MySQL"
        st.markdown(f'<span style="font-size:10px;color:{_text2};">Connected: {db_type}</span>', unsafe_allow_html=True)

    with st.expander("📁 Upload CSV" + _upload_label, expanded=False):
        st.caption("Upload a CSV file → becomes a queryable table → ask questions in chat")
        uploaded_csv = st.file_uploader("Choose CSV", type=["csv"], label_visibility="collapsed", key="csv_upload")
        if uploaded_csv:
            tbl = st.text_input("Table name", value=uploaded_csv.name.replace(".csv", "").replace(" ", "_").lower())
            if st.button("Import CSV", use_container_width=True):
                import tempfile
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                tmp.write(uploaded_csv.getbuffer())
                tmp.close()
                r = csv_to_table(tmp.name, tbl, username=_current_user)
                os.unlink(tmp.name)
                if r["success"]:
                    st.success(f"Imported {r['row_count']} rows")
                    st.session_state.auto_insights = None
                else:
                    st.error(r["error"])

    with st.expander("🗄️ Upload SQLite DB" + _upload_label, expanded=False):
        st.caption("Upload a `.db` / `.sqlite` / `.sqlite3` file → all tables become queryable")
        uploaded_db = st.file_uploader("Choose .db file", type=["db", "sqlite", "sqlite3"], label_visibility="collapsed", key="db_upload")
        if uploaded_db:
            label = st.text_input("Label (optional)", value=uploaded_db.name.replace(".db", "").replace(".sqlite", "").replace(" ", "_").lower())
            if st.button("Import DB", use_container_width=True):
                import tempfile
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                tmp.write(uploaded_db.getbuffer())
                tmp.close()
                r = import_db_file(tmp.name, label, username=_current_user)
                os.unlink(tmp.name)
                if r["success"]:
                    for t in r["tables"]:
                        st.success(f"Imported '{t['original']}' → '{t['as']}' ({t['row_count']} rows)")
                    st.session_state.auto_insights = None
                else:
                    st.error(r["error"])

    with st.popover("📂 My Uploaded Files", help="See and manage uploaded files"):
        st.caption(f"Files in {_upload_label.strip()}")
        flist = list_uploaded_files(username=_current_user)
        if flist.get("success") and flist["files"]:
            for f in flist["files"]:
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"`{f['name']}` ({f['size_kb']} KB)")
                with c2:
                    fp = f["path"]
                    if st.button("🗑️", key=f"sbf_{fp}", help="Delete file"):
                        try:
                            os.remove(fp)
                            st.rerun()
                        except Exception:
                            pass
        else:
            st.caption("No uploaded files yet.")

    if st.button("🗑️ Clear Uploads" + _upload_label, use_container_width=True, type="secondary"):
        clear_uploads(username=_current_user)
        st.session_state.auto_insights = None
        st.rerun()

    with st.expander("🔔 Data Whisperer", expanded=False):
        st.caption("Scan last results for statistical outliers.")
        last = None
        for m in reversed(st.session_state.messages):
            if m["role"] == "assistant" and m.get("data_rows"):
                last = m
                break
        if last and st.button("Scan anomalies", use_container_width=True):
            rows = last["data_rows"]
            cols = last["data_cols"]
            if rows and cols:
                num = [c for c in cols if any(isinstance(r.get(c), (int, float)) for r in rows[:5])]
                lab = [c for c in cols if c not in num]
                r = detect_anomalies(rows, value_key=num[-1] if num else cols[-1], label_key=lab[0] if lab else cols[0])
                if r.get("anomalies"):
                    for a in r["anomalies"]:
                        st.markdown(f"- **{a['label']}**: {a['direction']} (z={a['z_score']})")
                else:
                    st.success("No anomalies found.")
        else:
            st.caption("Run a query first.")

    with st.expander("🔗 Share", expanded=False):
        st.caption("Share this conversation with your team.")
        share_lines = []
        for m in st.session_state.messages:
            role = "You" if m["role"] == "user" else "DataPilot"
            c = m.get("reply") if m["role"] == "assistant" else m.get("content", "")
            if c:
                share_lines.append(f"{role}: {c[:200]}")
        share_text = "\n\n".join(share_lines) if share_lines else "No conversation yet."
        if st.button("📋 Copy to Clipboard", use_container_width=True):
            st.toast("📋 Copied to clipboard!")
            st.markdown(
                f'<textarea id="share-box" style="position:fixed;left:-9999px;">{share_text}</textarea>'
                f'<script>navigator.clipboard.writeText(document.getElementById("share-box").value)</script>',
                unsafe_allow_html=True,
            )

    with st.expander("📜 History", expanded=False):
        if st.session_state.query_history:
            for i, q in enumerate(reversed(st.session_state.query_history[-6:])):
                c1, c2 = st.columns([4, 1])
                with c1:
                    if st.button(q[:40] + ("…" if len(q) > 40 else ""), key=f"h_{i}"):
                        st.session_state._recall = q
                with c2:
                    if st.button("☆", key=f"hf_{i}", help="Save"):
                        if q not in st.session_state.favorites:
                            st.session_state.favorites.append(q)
        else:
            st.caption("No queries yet.")

    with st.expander("⭐ Favorites", expanded=False):
        if st.session_state.favorites:
            for i, q in enumerate(st.session_state.favorites):
                if st.button(q[:35] + ("…" if len(q) > 35 else ""), key=f"fav_{i}"):
                    st.session_state._recall = q
        else:
            st.caption("No favorites saved.")

    st.divider()
    st.caption("iTech AI Hackathon 2026")


# ── TABS ─────────────────────────────────────────────────────────────────

tab_chat, tab_data, tab_dashboard, tab_profiler, tab_insights = st.tabs(
    ["💬 Chat", "🗂️ My Data", "📌 Dashboard", "📊 Data Profiler", "🤖 Auto Insights"]
)


# ══════════════════════════════ CHAT ═════════════════════════════════════

with tab_chat:
    has_msgs = len(st.session_state.messages) > 0

    # ── WELCOME / EMPTY STATE ──
    if not has_msgs:
        st.markdown(
            f'<div class="welcome-hero">'
            f'<h1>👋 Ask your data anything</h1>'
            f'<p>DataPilot turns plain English into SQL, charts, and diagrams.<br>'
            f'Try one of the examples below, or type your own question.</p>'
            f'<div class="welcome-stats">'
            f'<div class="welcome-stat"><div class="welcome-stat-val">{t}</div><div class="welcome-stat-lbl">Tables</div></div>'
            f'<div class="welcome-stat"><div class="welcome-stat-val">{c}</div><div class="welcome-stat-lbl">Columns</div></div>'
            f'<div class="welcome-stat"><div class="welcome-stat-val">{f}</div><div class="welcome-stat-lbl">Relationships</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="welcome-cards">', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, (icon, title, query) in enumerate(WELCOME_CARDS):
            with cols[i % 2]:
                if st.button(
                    f"{icon} **{title}**\n\n{query}",
                    key=f"wc_{i}",
                    use_container_width=True,
                ):
                    st.session_state._recall = query
        st.markdown("</div>", unsafe_allow_html=True)

    # ── MESSAGE HISTORY ──
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(
                f'<div class="msg-row user"><div class="msg-bubble user">{msg["content"]}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="msg-row assistant">'
                f'<div class="msg-avatar">🤖</div>'
                f'<div class="msg-bubble assistant">',
                unsafe_allow_html=True,
            )

            if msg.get("reply"):
                st.markdown(f'<div style="font-size:14px;line-height:1.6;">{msg["reply"]}</div>', unsafe_allow_html=True)

            sql_qs = msg.get("sql_queries", [])
            if sql_qs and st.session_state.show_sql:
                st.markdown(
                    f'<div class="content-section">'
                    f'<span class="content-label sql">🔍 SQL Queries</span></div>',
                    unsafe_allow_html=True,
                )
                for qinfo in sql_qs:
                    st.code(qinfo["sql"], language="sql")
                    st.caption(f"↳ {qinfo['row_count']} rows · {qinfo['latency_ms']} ms")

            for i, fig_dict in enumerate(msg.get("charts", [])):
                st.markdown(
                    f'<div class="content-section">'
                    f'<span class="content-label chart">📊 Chart</span></div>',
                    unsafe_allow_html=True,
                )
                fig = go.Figure(fig_dict)
                apply_chart_theme(fig)
                fig.update_layout(height=340)
                st.plotly_chart(fig, use_container_width=True, key=f"c_{idx}_{i}", config={"displaylogo": False})

                bar_cols = st.columns(4)
                with bar_cols[0]:
                    if st.button("📌 Pin", key=f"pin_{idx}_{i}", use_container_width=True):
                        title = fig_dict.get("layout", {}).get("title", {}).get("text", "Untitled")
                        st.session_state.pinned.append({"title": title, "figure": fig_dict})
                        st.toast(f"📌 Pinned '{title}'")
                with bar_cols[1]:
                    try:
                        png = fig_to_png_bytes(fig_dict)
                        b64 = base64.b64encode(png).decode()
                        st.markdown(
                            f'<a href="data:image/png;base64,{b64}" download="chart_{i}.png" '
                            f'class="action-btn">⬇ PNG</a>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        pass
                with bar_cols[2]:
                    dr = msg.get("data_rows", [])
                    dc = msg.get("data_cols", [])
                    if dr and dc:
                        csv_b = pd.DataFrame(dr, columns=dc).to_csv(index=False).encode()
                        b64 = base64.b64encode(csv_b).decode()
                        st.markdown(
                            f'<a href="data:text/csv;base64,{b64}" download="data.csv" '
                            f'class="action-btn">⬇ CSV</a>',
                            unsafe_allow_html=True,
                        )

                st.markdown("<hr style='margin:0.5rem 0;border-color:var(--card-border)'>", unsafe_allow_html=True)

            for j, mermaid_code in enumerate(msg.get("diagrams", [])):
                st.markdown(
                    f'<div class="content-section">'
                    f'<span class="content-label diagram">📐 Diagram</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f'<div class="glass">', unsafe_allow_html=True)
                render_mermaid(mermaid_code)
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(
                f'<div class="msg-time">{_now()}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # ── EXPORT ──
    if has_msgs:
        e1, e2 = st.columns(2)
        with e1:
            lines = []
            for m in st.session_state.messages:
                role = "**You**" if m["role"] == "user" else "**DataPilot**"
                c = m.get("reply") if m["role"] == "assistant" else m.get("content", "")
                lines.append(f"{role}: {c}")
                for q in m.get("sql_queries", []):
                    lines.append(f"> ```sql\n> {q['sql']}\n> ```")
            st.download_button(
                "📥 Markdown", data="\n\n".join(lines).encode(),
                file_name="chat.md", mime="text/markdown", use_container_width=True,
            )
        with e2:
            try:
                pdf_bytes = _generate_pdf_report(st.session_state.messages)
                if pdf_bytes:
                    st.download_button(
                        "📕 PDF Report", data=pdf_bytes,
                        file_name="datapilot_report.pdf", mime="application/pdf", use_container_width=True,
                    )
            except Exception:
                st.button("📕 PDF", disabled=True, use_container_width=True)

    # ── SUGGESTION PILLS (compact, shown when chatting) ──
    if has_msgs:
        st.markdown('<div class="suggestions-strip">', unsafe_allow_html=True)
        for i in range(0, len(SUGGESTION_CHIPS[:6]), 3):
            cols = st.columns(3)
            for j in range(3):
                idx = i + j
                if idx < len(SUGGESTION_CHIPS[:6]):
                    with cols[j]:
                        short = SUGGESTION_CHIPS[idx][:20] + ("…" if len(SUGGESTION_CHIPS[idx]) > 20 else "")
                        if st.button(short, key=f"sp_{idx}", use_container_width=True):
                            st.session_state._recall = SUGGESTION_CHIPS[idx]
        st.markdown("</div>", unsafe_allow_html=True)

    # ── VOICE INPUT ──
    voice_prompt = None
    if st.session_state.voice_mode:
        voice_html = """
        <div style="display:flex;align-items:center;gap:8px;margin:8px 0;padding:8px 12px;background:rgba(0,212,170,0.06);border-radius:12px;border:1px solid rgba(0,212,170,0.15);">
            <span id="voice-status" style="font-size:13px;color:#7a7d91;">🎤 Click to speak...</span>
            <button id="voice-btn" onclick="startVoice()" style="background:rgba(0,212,170,0.12);border:1px solid rgba(0,212,170,0.2);color:#00d4aa;padding:6px 16px;border-radius:20px;cursor:pointer;font-size:13px;font-weight:500;">Start</button>
        </div>
        <script>
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            document.getElementById('voice-status').innerText = '❌ Speech not supported in this browser';
        } else {
            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = false;
            recognition.continuous = false;
            let listening = false;

            window.startVoice = function() {
                if (listening) return;
                listening = true;
                document.getElementById('voice-btn').innerText = 'Listening...';
                document.getElementById('voice-status').innerText = '🎤 Speak now...';
                recognition.start();
            };

            recognition.onresult = function(event) {
                const transcript = event.results[0][0].transcript;
                document.getElementById('voice-status').innerText = '✅ \"' + transcript + '\"';
                document.getElementById('voice-btn').innerText = 'Done';
                const input = window.parent.document.querySelector('textarea[data-testid="stChatInput"]');
                if (input) {
                    input.value = transcript;
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeInputValueSetter.call(input, transcript);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    const form = input.closest('form');
                    if (form) {
                        setTimeout(() => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })), 300);
                    }
                }
                listening = false;
            };

            recognition.onerror = function(event) {
                document.getElementById('voice-status').innerText = '❌ Error: ' + event.error;
                document.getElementById('voice-btn').innerText = 'Retry';
                listening = false;
            };

            recognition.onend = function() {
                if (listening) {
                    document.getElementById('voice-status').innerText = '🎤 Click to speak...';
                    document.getElementById('voice-btn').innerText = 'Start';
                    listening = false;
                }
            };
        }
        </script>
        """
        with st.container():
            st.html(voice_html)

    # ── CHAT INPUT ──
    recall = st.session_state.pop("_recall", None)
    prompt = recall or (voice_prompt) or st.chat_input(
        "Ask a question about your data...",
    )

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        if prompt not in st.session_state.query_history:
            st.session_state.query_history.append(prompt)

        api_hist = []
        for m in st.session_state.messages[:-1]:
            if m["role"] == "user":
                api_hist.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant" and m.get("reply"):
                api_hist.append({"role": "assistant", "content": m["reply"]})

        tracer = AgentTracer()

        with st.chat_message("assistant"):
            with st.spinner("Running tools..."):
                try:
                    result = run_agent_turn(
                        prompt, api_hist, tracer,
                        language=st.session_state.language,
                        username=_current_user,
                        file_mode=st.session_state.file_mode,
                    )
                except Exception as e:
                    result = {"reply": f"⚠️ {e}", "charts": [], "diagrams": [], "sql_queries": []}

            st.session_state.trace_log = tracer.events_for_turn()

            reply = result.get("reply", "")
            streamed_reply = st.write_stream(_word_stream(reply))

            sql_list = result.get("sql_queries", [])
            dr, dc = None, None
            if sql_list:
                last_q = sql_list[-1]
                dr = last_q.get("rows", [])
                dc = last_q.get("columns", [])

            if sql_list and st.session_state.show_sql:
                for qinfo in sql_list:
                    st.code(qinfo["sql"], language="sql")
                    st.caption(f"↳ {qinfo['row_count']} rows · {qinfo['latency_ms']} ms")

            for i, fig_dict in enumerate(result.get("charts", [])):
                fig = go.Figure(fig_dict)
                apply_chart_theme(fig)
                fig.update_layout(height=340)
                st.plotly_chart(fig, use_container_width=True, key=f"new_c_{i}", config={"displaylogo": False})

                bar_cols = st.columns(4)
                with bar_cols[0]:
                    if st.button("📌 Pin", key=f"new_pin_{i}", use_container_width=True):
                        title = fig_dict.get("layout", {}).get("title", {}).get("text", "Untitled")
                        st.session_state.pinned.append({"title": title, "figure": fig_dict})
                        st.toast(f"📌 Pinned '{title}'")
                with bar_cols[1]:
                    try:
                        png = fig_to_png_bytes(fig_dict)
                        b64 = base64.b64encode(png).decode()
                        st.markdown(
                            f'<a href="data:image/png;base64,{b64}" download="chart_{i}.png" '
                            f'class="action-btn">⬇ PNG</a>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        pass
                with bar_cols[2]:
                    if dr and dc:
                        csv_b = pd.DataFrame(dr, columns=dc).to_csv(index=False).encode()
                        b64 = base64.b64encode(csv_b).decode()
                        st.markdown(
                            f'<a href="data:text/csv;base64,{b64}" download="data.csv" '
                            f'class="action-btn">⬇ CSV</a>',
                            unsafe_allow_html=True,
                        )

            for mermaid_code in result.get("diagrams", []):
                render_mermaid(mermaid_code)

            payload = {
                "role": "assistant",
                "reply": reply,
                "charts": result.get("charts", []),
                "diagrams": result.get("diagrams", []),
                "sql_queries": sql_list,
                "data_rows": dr,
                "data_cols": dc,
            }
            st.session_state.messages.append(payload)


# ══════════════════════════════ MY DATA ═════════════════════════════════

with tab_data:
    st.markdown(f'<h3 style="color:{_accent};">🗂️ Your Data Sources</h3>', unsafe_allow_html=True)
    st.caption("Browse, query, and manage all your data sources in one place.")

    tab_overview, tab_upload_help = st.tabs(["📋 Overview", "📤 Upload Guide"])
    with tab_upload_help:
        st.markdown("""
        ### Supported Formats

        | Format | How to Upload | How to Query in Chat |
        |---|---|---|
        | **CSV** (.csv) | Sidebar → Upload CSV → pick file → name table → Import | "Show me first 10 rows from my.products" |
        | **SQLite DB** (.db/.sqlite/.sqlite3) | Sidebar → Upload SQLite DB → pick file → optional label → Import | "What tables are in my uploads?" then query any table |
        | **Excel** (.xlsx) | Convert to CSV first (File → Save As → CSV) or use SQLite DB | Same as CSV above |
        | **JSON** (.json) | Convert to CSV or SQLite, or use via connection string | Same |

        ### Quick Tips
        - **Personal mode** — only you see your uploads
        - **Shared mode** — all registered users see these tables
        - **"Ask from Uploaded File"** toggle → agent focuses only on your data
        - **Max file size** — Streamlit Cloud limit is ~200MB per upload
        """)

    with tab_overview:
        all_sources = []

        sample_path = _db_path
        if os.path.exists(sample_path):
            try:
                s = get_schema(db_path=sample_path)
                if s.get("success"):
                    all_sources.append(("📦 Sample E-Commerce DB", sample_path, s["tables"], False))
            except Exception:
                pass

        for label, mode_username in [("👤 My Uploads", st.session_state.user), ("🌐 Shared Uploads", "")]:
            info = list_uploaded_tables(username=mode_username)
            if info.get("success") and info["tables"]:
                from tools.query_tool import _uploads_db as _get_up_db
                up_path = _get_up_db(mode_username)
                all_sources.append((label, up_path, info["tables"], mode_username != ""))

        if not all_sources:
            st.info("No databases found. Upload a CSV or SQLite file to get started.")
        else:
            for src_name, src_path, tables, can_delete in all_sources:
                mode_user = st.session_state.user if "My Uploads" in src_name else ""
                col_title, col_clear = st.columns([3, 1])
                with col_title:
                    st.markdown(f'<h4 style="color:{_accent};">{src_name}</h4>', unsafe_allow_html=True)
                    st.code(src_path, language="text")
                with col_clear:
                    if can_delete and st.button(f"🗑️ Clear All", key=f"clear_{mode_user}", use_container_width=True):
                        clear_uploads(username=mode_user)
                        st.session_state.auto_insights = None
                        st.rerun()

                for t in tables:
                    cols_fmt = ", ".join(t["columns"][:5])
                    if len(t["columns"]) > 5:
                        cols_fmt += f" … +{len(t['columns'])-5} more"
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    with c1:
                        st.markdown(f'**{t["table_name"]}**')
                    with c2:
                        st.markdown(f'`{t["row_count"]} rows`')
                    with c3:
                        with st.popover("📋 Columns", help="View columns"):
                            for col in t["columns"]:
                                st.code(col)
                    with c4:
                        if can_delete:
                            if st.button("❌", key=f"del_{mode_user}_{t['table_name']}", help="Delete this table"):
                                drop_table(t["table_name"], username=mode_user)
                                st.rerun()
                    st.markdown(f'<span style="font-size:12px;color:{_text2};">{cols_fmt}</span>', unsafe_allow_html=True)
                    st.divider()

# ══════════════════════════════ DASHBOARD ════════════════════════════════

with tab_dashboard:
    n = len(st.session_state.pinned)
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-size:20px;font-weight:700;">📌 Dashboard</span>'
        f'<span class="badge badge-purple">{n} pinned</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.pinned:
        st.info("💡 Ask a question in Chat, then click **📌 Pin** under any chart.")
    else:
        ncols = 2 if n <= 4 else 3
        grid = st.columns(ncols)
        for i, item in enumerate(st.session_state.pinned):
            with grid[i % ncols]:
                st.markdown(f'<div class="dash-item">', unsafe_allow_html=True)
                st.markdown(f'<div class="dash-item-title">{item["title"]}</div>', unsafe_allow_html=True)
                fig = go.Figure(item["figure"])
                apply_chart_theme(fig)
                fig.update_layout(height=260, margin=dict(l=8, r=8, t=8, b=8))
                st.plotly_chart(fig, use_container_width=True, key=f"d_{i}", config={"displayModeBar": False})

                c1, c2 = st.columns(2)
                with c1:
                    try:
                        png = fig_to_png_bytes(item["figure"])
                        b64 = base64.b64encode(png).decode()
                        st.markdown(f'<a href="data:image/png;base64,{b64}" download="dash_{i}.png" class="action-btn" style="font-size:11px;">⬇ PNG</a>', unsafe_allow_html=True)
                    except Exception:
                        pass
                with c2:
                    if st.button("🗑️", key=f"rm_{i}", use_container_width=True):
                        st.session_state.pinned.pop(i)
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        if n > 0:
            st.divider()
            c1, c2 = st.columns([3, 1])
            with c1:
                html = [
                    f"<html><head><script src='https://cdn.plot.ly/plotly-2.32.0.min.js'></script>"
                    f"<style>body{{font-family:Inter,sans-serif;background:{_bg};color:{_text};padding:24px}}"
                    f"h1{{background:{_accent_grad};-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}"
                    f".chart{{margin:16px 0;background:{_card_bg};border-radius:12px;padding:12px;border:1px solid {_card_border};}}</style>"
                    f"</head><body><h1>📊 DataPilot Dashboard</h1>"
                    f"<p>Generated {datetime.now().strftime('%b %d, %Y at %I:%M %p')}</p>"
                ]
                for item in st.session_state.pinned:
                    fig = go.Figure(item["figure"])
                    apply_chart_theme(fig)
                    html.append(f"<div class='chart'><h3>{item['title']}</h3>{fig.to_html(full_html=False, include_plotlyjs='cdn')}</div>")
                html.append("</body></html>")
                st.download_button("📥 Export HTML", data="\n".join(html).encode(), file_name="dashboard.html", mime="text/html", use_container_width=True)
            with c2:
                if st.button("Clear All", use_container_width=True):
                    st.session_state.pinned = []
                    st.rerun()


# ══════════════════════════════ PROFILER ═════════════════════════════════

with tab_profiler:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.25rem;">'
        f'<span style="font-size:20px;font-weight:700;">📊 Data Profiler</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Select a table to inspect its schema, stats, and sample data.")

    sr = get_schema(_db_path)

    if sr.get("success"):
        tables = list(sr["schema"]["tables"].keys())
        selected = st.selectbox("Table", tables, label_visibility="collapsed")

        if selected:
            with st.spinner(f"Profiling `{selected}`..."):
                r = execute_query(_db_path, f"SELECT * FROM {selected} LIMIT 1000")
                if r.get("success"):
                    rows, cols = r["rows"], r["columns"]
                    df = pd.DataFrame(rows, columns=cols)

                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.markdown(f"<div class='metric-card'><div class='metric-val'>{len(df)}</div><div class='metric-lbl'>Rows</div></div>", unsafe_allow_html=True)
                    with m2:
                        st.markdown(f"<div class='metric-card'><div class='metric-val'>{len(cols)}</div><div class='metric-lbl'>Columns</div></div>", unsafe_allow_html=True)
                    with m3:
                        st.markdown(f"<div class='metric-card'><div class='metric-val'>{df.isnull().sum().sum()}</div><div class='metric-lbl'>Nulls</div></div>", unsafe_allow_html=True)
                    with m4:
                        st.markdown(f"<div class='metric-card'><div class='metric-val'>{len(df.select_dtypes(include=['number']).columns)}</div><div class='metric-lbl'>Numeric</div></div>", unsafe_allow_html=True)

                    st.divider()
                    st.markdown("### Column Analysis")
                    cd = []
                    for c in cols:
                        nn = df[c].count()
                        dt = str(df[c].dtype)
                        uq = df[c].nunique()
                        sp = str(df[c].dropna().iloc[0]) if len(df) > 0 and nn > 0 else "-"
                        if pd.api.types.is_numeric_dtype(df[c]):
                            sts = f"min={df[c].min()}, max={df[c].max()}, avg={df[c].mean():.1f}"
                        else:
                            sts = f"top={df[c].mode().iloc[0] if nn > 0 else '-'}"
                        cd.append({"Column": c, "Type": dt, "Non-Null": f"{nn}/{len(df)}", "Unique": uq, "Stats": sts})
                    st.dataframe(pd.DataFrame(cd), use_container_width=True, hide_index=True)

                    with st.expander("📋 Sample Data", expanded=False):
                        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

                    csv_b = df.describe(include="all").to_csv().encode()
                    st.download_button("⬇ Profile CSV", data=csv_b, file_name=f"{selected}_profile.csv", mime="text/csv")
                else:
                    st.error(r.get("error"))
    else:
        st.error("Could not read database schema.")

    with st.expander("🔍 Data Quality Scanner", expanded=False):
        st.caption("Scan all tables for nulls, duplicates, and outlier values.")
        if st.button("Scan Quality", use_container_width=True):
            from tools.quality_tool import scan_quality
            qr = scan_quality(_db_path)
            if qr.get("success"):
                if qr["clean"]:
                    st.success("No issues found! Dataset looks clean.")
                else:
                    st.warning(f"Found **{qr['total_issues']}** potential issues across {len(qr['tables'])} tables.")
                for tname, treport in qr["tables"].items():
                    with st.container():
                        st.markdown(f"**{tname}** ({treport['row_count']} rows)")
                        if treport["null_columns"]:
                            st.markdown(f"  - Nulls: {treport['null_columns']}")
                        if treport["duplicate_rows"]:
                            st.markdown(f"  - Duplicates: {treport['duplicate_rows']} rows")
                        if treport["outlier_columns"]:
                            for oc in treport["outlier_columns"]:
                                st.markdown(f"  - Outliers in {oc['column']}: {oc['outliers']} values exceed ±2σ (>{oc['threshold']})")
                        if treport["issue_count"] == 0:
                            st.markdown("  - ✅ Clean")
            else:
                st.error(qr.get("error", "Scan failed."))


# ══════════════════════════════ INSIGHTS ═════════════════════════════════

with tab_insights:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.25rem;">'
        f'<span style="font-size:20px;font-weight:700;">🤖 Auto Insights</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Multi-perspective report on your data — metrics, trends, anomalies, and recommendations.")

    if st.button("🔄 Generate Report", use_container_width=True, type="primary"):
        with st.spinner("Running analysis..."):
            st.session_state.auto_insights = generate_auto_insights(_db_path)

    if st.session_state.auto_insights:
        rpt = st.session_state.auto_insights

        if rpt.get("error"):
            st.error(rpt["error"])
        else:
            metrics = rpt.get("metrics", {})
            if metrics:
                st.markdown("### Key Metrics")
                for i, (lbl, val) in enumerate([
                    ("Revenue", f"${metrics.get('total_revenue', 0):,.0f}"),
                    ("Orders", f"{metrics.get('total_orders', 0):,}"),
                    ("Avg Order", f"${metrics.get('avg_order_value', 0):,.2f}"),
                    ("Customers", f"{metrics.get('active_customers', 0):,}"),
                ]):
                    if i % 4 == 0:
                        ms = st.columns(4)
                    with ms[i % 4]:
                        st.markdown(f"<div class='metric-card'><div class='metric-val'>{val}</div><div class='metric-lbl'>{lbl}</div></div>", unsafe_allow_html=True)

            trends = rpt.get("trends", {})
            if trends:
                st.divider()
                st.markdown("### Trends")

                if trends.get("monthly_revenue"):
                    df = pd.DataFrame(trends["monthly_revenue"])
                    if "month" in df.columns and "revenue" in df.columns:
                        fig = px.line(df, x="month", y="revenue", title="Monthly Revenue", markers=True)
                        apply_chart_theme(fig)
                        st.plotly_chart(fig, use_container_width=True)

                if trends.get("category_revenue"):
                    df = pd.DataFrame(trends["category_revenue"])
                    if "category" in df.columns and "revenue" in df.columns:
                        fig = px.pie(df, values="revenue", names="category", title="Revenue by Category")
                        apply_chart_theme(fig)
                        st.plotly_chart(fig, use_container_width=True)

                if trends.get("order_status"):
                    df = pd.DataFrame(trends["order_status"])
                    if "status" in df.columns and "count" in df.columns:
                        fig = px.bar(df, x="status", y="count", title="Orders by Status", color="status")
                        apply_chart_theme(fig)
                        st.plotly_chart(fig, use_container_width=True)

                if trends.get("top_products"):
                    df = pd.DataFrame(trends["top_products"])
                    if "name" in df.columns and "revenue" in df.columns:
                        fig = px.bar(df, x="revenue", y="name", title="Top Products", orientation="h")
                        apply_chart_theme(fig)
                        st.plotly_chart(fig, use_container_width=True)

            anomalies = rpt.get("anomalies", [])
            if anomalies:
                st.divider()
                st.markdown("### 🚨 Anomalies")
                for a in anomalies:
                    st.warning(f"**{a.get('label', '?')}** — {a.get('direction', '')} (z={a.get('z_score', 0):.2f})")

            summary = rpt.get("summary", "")
            if summary:
                st.divider()
                st.markdown("### Summary")
                st.info(summary)

            recommendations = rpt.get("recommendations", [])
            if recommendations:
                st.divider()
                st.markdown("### Recommendations")
                for r in recommendations:
                    st.markdown(f"- {r}")

            import json as _json
            st.download_button(
                "⬇ Report JSON",
                data=_json.dumps(rpt, indent=2, default=str).encode(),
                file_name="insights_report.json",
                mime="application/json",
            )

    st.divider()
    with st.expander("📖 Data Storytelling Report", expanded=False):
        st.caption("Generate a narrative report combining multiple perspectives into one story.")
        report_driver = st.text_input("Focus area (e.g. 'sales performance', 'customer behavior')", placeholder="What story do you want to tell?")
        if st.button("Generate Story", use_container_width=True) and report_driver:
            with st.spinner("Building your data story..."):
                from tools.report_tool import generate_report
                from tools.insight_tool import generate_auto_insights
                ai = generate_auto_insights(_db_path)
                if ai.get("error"):
                    st.error(ai["error"])
                else:
                    metrics = ai.get("metrics", {})
                    sample = []
                    if metrics.get("monthly_revenue"):
                        sample = metrics["monthly_revenue"]
                    cols = list(sample[0].keys()) if sample else []
                    r = generate_report(sample, cols, question=report_driver,
                                        chart_titles=["Monthly Revenue", "Category Breakdown", "Order Status"])
                    if r.get("success"):
                        st.markdown(f'<div style="background:{_card_bg};padding:1.5rem;border-radius:12px;border:1px solid {_card_border};">', unsafe_allow_html=True)
                        st.markdown(r["summary"])
                        if r.get("insights"):
                            st.markdown("#### Key Insights")
                            for ins in r["insights"]:
                                st.markdown(f"- {ins}")
                        st.markdown("</div>", unsafe_allow_html=True)

    ut = list_uploaded_tables()
    if ut.get("success") and ut["tables"]:
        st.divider()
        st.markdown("### Uploaded Tables")
        for u in ut["tables"]:
            st.markdown(f"- **`uploads.{u['table_name']}`** — {u['row_count']} rows, {len(u['columns'])} cols")
