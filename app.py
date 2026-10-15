"""
ShineAndBright — SupplyPro Extractor + Jobber Uploader
"""
import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
from datetime import date, timedelta
import subprocess
import sys
import html

import logger as _log
_log.setup()


# ── Playwright install ────────────────────────────────────────────────────────
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
        )
    except Exception as e:
        st.warning(f"Playwright setup: {e}")


install_playwright()

from i18n import t
from config import (
    MUNGO_PASSWORD,
    MUNGO_USERNAME,
    SUPPLYPRO_PASSWORD,
    SUPPLYPRO_USERNAME,
)
from scraper import ejecutar_extraccion
from transformer import transformar_ordenes
from mungo.scraper import (
    MungoAuthenticationError,
    ejecutar_extraccion_mungo,
    probar_conexion_mungo,
)
from mungo.transformer import transformar_ordenes_mungo
from jobber import storage, oauth
from jobber.client import JobberClient, JobberAuthError
from jobber.mappers import parse_total, validate_row
from tasks import (
    ASSIGNEES,
    ASSIGNEE_COLORS,
    PRIORITIES,
    build_pdf,
    create_task,
    delete_task,
    init_db,
    list_tasks,
    report_tasks,
    set_completed,
)

# ── CSS ───────────────────────────────────────────────────────────────────────
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Rubik:wght@300;400;500&display=swap');

/* === TOKENS === */
:root {
  --ws-accent:        #00C2FF;
  --ws-accent-dark:   #009FD4;
  --ws-accent-glow:   rgba(0,194,255,0.18);
  --ws-sidebar:       #0C1628;
  --ws-sidebar-hi:    rgba(255,255,255,0.07);
  --ws-sidebar-text:  #BDD0E8;
  --ws-sidebar-muted: #5A748E;
  --ws-surface:       #F7F9FC;
  --ws-surface-2:     #EDF1F7;
  --ws-white:         #FFFFFF;
  --ws-text:          #111827;
  --ws-text-2:        #374151;
  --ws-muted:         #6B7280;
  --ws-border:        #E2E8F0;
  --ws-border-2:      #CBD5E1;
  --ws-success:       #059669;
  --ws-success-bg:    rgba(5,150,105,0.08);
  --ws-error:         #DC2626;
  --ws-error-bg:      rgba(220,38,38,0.07);
  --ws-warn:          #D97706;
  --ws-warn-bg:       rgba(217,119,6,0.08);
  --ws-info-bg:       rgba(0,194,255,0.07);
  --r-sm:  6px;
  --r-md:  10px;
  --r-lg:  14px;
  --sh-xs: 0 1px 3px rgba(15,23,42,0.07),0 1px 2px rgba(15,23,42,0.04);
  --sh-sm: 0 2px 8px rgba(15,23,42,0.08),0 1px 3px rgba(15,23,42,0.05);
  --sh-md: 0 4px 16px rgba(15,23,42,0.1),0 2px 6px rgba(15,23,42,0.06);
}

/* === BASE === */
html, body, .stApp {
  font-family: 'Rubik', -apple-system, sans-serif !important;
}
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
  display: none !important;
}

/* === SIDEBAR === */
[data-testid="stSidebar"] {
  background-color: var(--ws-sidebar) !important;
  border-right: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: 1.75rem !important;
}

/* Sidebar text */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div:not([data-testid]) > span {
  color: var(--ws-sidebar-text) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  font-family: 'Sora', sans-serif !important;
  color: #FFFFFF !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
  font-size: 0.95rem !important;
  letter-spacing: 0.05em !important;
  margin-bottom: 0.5rem !important;
}
[data-testid="stSidebar"] .stCaption > p {
  color: var(--ws-sidebar-muted) !important;
  font-size: 0.69rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.09em !important;
  text-transform: uppercase !important;
}

/* Sidebar hr */
[data-testid="stSidebar"] hr {
  border-color: rgba(255,255,255,0.07) !important;
  margin: 1.1rem 0 !important;
}

/* Sidebar alerts */
[data-testid="stSidebar"] [data-testid="stAlert"] {
  background-color: rgba(5,150,105,0.14) !important;
  border: 1px solid rgba(5,150,105,0.28) !important;
  border-radius: var(--r-sm) !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"][data-baseweb="notification"][kind="info"] {
  background-color: rgba(0,194,255,0.1) !important;
  border-color: rgba(0,194,255,0.22) !important;
}
[data-testid="stSidebar"] [data-testid="stAlert"] p {
  color: #A7F3D0 !important;
  font-size: 0.8rem !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--ws-sidebar-text) !important;
  border: 1px solid rgba(255,255,255,0.1) !important;
  border-radius: var(--r-sm) !important;
  font-family: 'Rubik', sans-serif !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  transition: background 140ms ease, border-color 140ms ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background-color: var(--ws-sidebar-hi) !important;
  border-color: rgba(0,194,255,0.3) !important;
  color: #FFFFFF !important;
}

/* Sidebar primary navigation */
[data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] {
  margin-bottom: 0.45rem;
}
[data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] .stButton > button {
  min-height: 3.35rem !important;
  justify-content: flex-start !important;
  padding: 0.75rem 1rem !important;
  background: rgba(255,255,255,0.035) !important;
  border: 1px solid rgba(255,255,255,0.06) !important;
  border-radius: 0.9rem !important;
  color: #DCE8F5 !important;
  font-family: 'Sora', sans-serif !important;
  font-size: 0.92rem !important;
  font-weight: 600 !important;
  text-align: left !important;
}
[data-testid="stSidebar"] [class*="st-key-sidebar_nav_"] .stButton > button:hover {
  background: rgba(255,255,255,0.085) !important;
  border-color: rgba(0,194,255,0.32) !important;
  transform: translateX(2px);
}
[data-testid="stSidebar"] .st-key-sidebar_nav_orders_active .stButton > button,
[data-testid="stSidebar"] .st-key-sidebar_nav_tasks_active .stButton > button {
  background: linear-gradient(135deg, rgba(0,194,255,0.22), rgba(16,185,129,0.16)) !important;
  border-color: rgba(0,194,255,0.5) !important;
  box-shadow: inset 3px 0 0 var(--ws-accent), 0 5px 16px rgba(0,0,0,0.12) !important;
  color: #FFFFFF !important;
}

/* Sidebar link buttons (connect) */
[data-testid="stSidebar"] .stLinkButton > a {
  background-color: var(--ws-accent) !important;
  color: #0A1628 !important;
  border: none !important;
  border-radius: var(--r-sm) !important;
  font-weight: 600 !important;
  font-size: 0.8rem !important;
  transition: background 140ms ease !important;
}
[data-testid="stSidebar"] .stLinkButton > a:hover {
  background-color: var(--ws-accent-dark) !important;
}

/* Sidebar radio (lang) */
[data-testid="stSidebar"] .stRadio label {
  color: var(--ws-sidebar-text) !important;
  font-size: 0.82rem !important;
}

/* === MAIN AREA === */
[data-testid="stMain"] {
  background-color: var(--ws-surface) !important;
}
[data-testid="stMainBlockContainer"] {
  padding-top: 2.25rem !important;
  padding-bottom: 3.5rem !important;
}

/* === TYPOGRAPHY (main) === */
[data-testid="stMain"] h1 {
  font-family: 'Sora', sans-serif !important;
  font-weight: 700 !important;
  font-size: 1.9rem !important;
  letter-spacing: -0.025em !important;
  color: var(--ws-text) !important;
  line-height: 1.2 !important;
}
[data-testid="stMain"] h2 {
  font-family: 'Sora', sans-serif !important;
  font-weight: 600 !important;
  font-size: 1.25rem !important;
  letter-spacing: -0.015em !important;
  color: var(--ws-text) !important;
}
[data-testid="stMain"] h3 {
  font-family: 'Sora', sans-serif !important;
  font-weight: 600 !important;
  font-size: 1rem !important;
  letter-spacing: -0.01em !important;
  color: var(--ws-text-2) !important;
}
[data-testid="stMain"] p {
  font-family: 'Rubik', sans-serif !important;
  color: var(--ws-text) !important;
  line-height: 1.65 !important;
}
[data-testid="stMain"] .stCaption > p {
  color: var(--ws-muted) !important;
  font-size: 0.8125rem !important;
}
hr { border: none !important; border-top: 1px solid var(--ws-border) !important; margin: 1.75rem 0 !important; }

/* === BUTTONS (main) === */
.stButton > button {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  border-radius: var(--r-sm) !important;
  border: 1px solid var(--ws-border) !important;
  background-color: var(--ws-white) !important;
  color: var(--ws-text) !important;
  padding: 0.45rem 1.1rem !important;
  box-shadow: var(--sh-xs) !important;
  transition: box-shadow 140ms ease, transform 120ms ease, border-color 140ms ease !important;
}
.stButton > button:hover {
  background-color: var(--ws-surface-2) !important;
  border-color: var(--ws-border-2) !important;
  transform: translateY(-1px) !important;
  box-shadow: var(--sh-sm) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Primary button */
.stButton > button[kind="primary"] {
  background-color: var(--ws-accent) !important;
  color: #071525 !important;
  border-color: transparent !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"]:hover {
  background-color: var(--ws-accent-dark) !important;
  box-shadow: 0 0 0 3px var(--ws-accent-glow), var(--sh-sm) !important;
}

/* Download buttons */
.stDownloadButton > button {
  font-family: 'Rubik', sans-serif !important;
  font-size: 0.875rem !important;
  font-weight: 500 !important;
  border-radius: var(--r-sm) !important;
  border: 1px solid var(--ws-border) !important;
  background-color: var(--ws-white) !important;
  box-shadow: var(--sh-xs) !important;
  transition: all 140ms ease !important;
}
.stDownloadButton > button:hover {
  border-color: var(--ws-accent) !important;
  transform: translateY(-1px) !important;
}

/* === METRICS === */
[data-testid="stMetric"] {
  background-color: var(--ws-white) !important;
  border: 1px solid var(--ws-border) !important;
  border-radius: var(--r-lg) !important;
  padding: 1.25rem 1.5rem !important;
  box-shadow: var(--sh-xs) !important;
  transition: box-shadow 200ms ease !important;
}
[data-testid="stMetric"]:hover { box-shadow: var(--sh-sm) !important; }
[data-testid="stMetricLabel"] > div {
  font-family: 'Rubik', sans-serif !important;
  font-size: 0.675rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.09em !important;
  text-transform: uppercase !important;
  color: var(--ws-muted) !important;
}
[data-testid="stMetricValue"] > div {
  font-family: 'Sora', sans-serif !important;
  font-size: 1.8rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.025em !important;
  color: var(--ws-text) !important;
}

/* === ALERTS === */
[data-testid="stAlert"] {
  border-radius: var(--r-md) !important;
  font-family: 'Rubik', sans-serif !important;
  font-size: 0.875rem !important;
}

/* === DATA FRAME / EDITOR === */
[data-testid="stDataFrameContainer"],
[data-testid="stDataEditorContainer"] {
  border-radius: var(--r-md) !important;
  border: 1px solid var(--ws-border) !important;
  box-shadow: var(--sh-xs) !important;
  overflow: hidden !important;
}

/* === FILE UPLOADER === */
[data-testid="stFileUploaderDropzone"] {
  border: 2px dashed var(--ws-border-2) !important;
  border-radius: var(--r-md) !important;
  background-color: rgba(0,194,255,0.03) !important;
  transition: border-color 140ms ease, background 140ms ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--ws-accent) !important;
  background-color: var(--ws-info-bg) !important;
}

/* === EXPANDER === */
[data-testid="stExpander"] {
  border: 1px solid var(--ws-border) !important;
  border-radius: var(--r-md) !important;
  background-color: var(--ws-white) !important;
  box-shadow: var(--sh-xs) !important;
}
[data-testid="stExpander"] summary {
  font-family: 'Rubik', sans-serif !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  color: var(--ws-muted) !important;
}

/* === PROGRESS BAR === */
[data-testid="stProgressBar"] > div {
  background-color: var(--ws-border) !important;
  border-radius: 99px !important;
  height: 5px !important;
  overflow: hidden !important;
}
[data-testid="stProgressBar"] > div > div {
  background-color: var(--ws-accent) !important;
  border-radius: 99px !important;
  transition: width 280ms ease-out !important;
}

/* === TOAST === */
[data-testid="stToast"] {
  border-radius: var(--r-md) !important;
  border: 1px solid var(--ws-border) !important;
  box-shadow: var(--sh-md) !important;
  font-family: 'Rubik', sans-serif !important;
  font-size: 0.875rem !important;
}

/* === RESPONSIVE === */
@media (max-width: 640px) {
  [data-testid="stMain"] h1 { font-size: 1.5rem !important; }
  [data-testid="stMetricValue"] > div { font-size: 1.4rem !important; }
  [data-testid="stMainBlockContainer"] { padding-top: 1.25rem !important; }
  [data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 100% !important;
  }
  [data-testid="stMetric"] { margin-bottom: 0.5rem; }
}
@media (max-width: 768px) {
  section[data-testid="stSidebar"] { min-width: 200px !important; }
}

/* === TASKS === */
.task-summary {
  border: 1px solid var(--ws-border); border-radius: var(--r-md);
  background: var(--ws-white); padding: 1rem 1.1rem; box-shadow: var(--sh-xs);
}
.task-summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1rem; }
.task-summary .label { color: var(--ws-muted); font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.task-summary .value { color: var(--ws-text); font-family: 'Sora',sans-serif; font-size: 1.55rem; font-weight: 700; margin-top: .25rem; }
.task-table-wrap { overflow-x:auto; border:1px solid var(--ws-border); border-radius:var(--r-md); background:white; }
.task-table { width:100%; border-collapse:collapse; font-size:.86rem; }
.task-table th { background:#F1F5F9; color:#475569; font-size:.7rem; text-transform:uppercase; letter-spacing:.05em; text-align:left; padding:.78rem .9rem; }
.task-table td { padding:.82rem .9rem; border-top:1px solid #E8EDF3; color:#1E293B; vertical-align:top; }
.task-table tr.task-done td { color:#8793A3; background:#FAFBFC; }
.task-title { font-weight:600; color:#111827; }
.task-desc { color:#64748B; font-size:.76rem; margin-top:.2rem; max-width:430px; }
.task-grid-header { color:#475569; font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; padding:.25rem .15rem; }
.task-grid-cell { display:flex; flex-direction:column; justify-content:center; min-height:2.3rem; padding:0 .15rem; color:#1E293B; font-size:.84rem; }
.task-grid-actions [data-testid="stButton"] button { padding:.28rem .45rem !important; min-height:2rem !important; font-size:.9rem !important; }
[class*="st-key-task_row_"] {
  border:1px solid var(--ws-border); border-radius:var(--r-sm);
  background:var(--ws-white); padding:.38rem .65rem !important; margin-bottom:.28rem;
}
[class*="st-key-task_row_"] [data-testid="stVerticalBlock"] { gap:.18rem !important; }
[class*="st-key-task_row_"] [data-testid="stHorizontalBlock"] { align-items:center !important; }
[class*="st-key-task_row_"] [data-testid="stMarkdownContainer"] p { margin:0 !important; }
[class*="st-key-task_row_"] [data-testid="stButton"] button {
  min-height:1.9rem !important; height:1.9rem !important; padding:.18rem .35rem !important;
}
.person-pill,.priority-pill,.status-pill { display:inline-block; border-radius:999px; padding:.22rem .55rem; font-size:.72rem; font-weight:600; white-space:nowrap; }
.task-title { line-height:1.15; }
.task-desc { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; line-height:1.2; margin-top:.16rem; }
[class*="st-key-task_open_"] [data-testid="stButton"] button {
  width:100% !important; height:auto !important; min-height:2.6rem !important;
  padding:.12rem .1rem !important; border:0 !important; box-shadow:none !important;
  background:transparent !important; text-align:left !important; justify-content:flex-start !important;
  white-space:normal !important;
}
[class*="st-key-task_open_"] [data-testid="stButton"] button p { text-align:left !important; line-height:1.2 !important; }
[class*="st-key-task_open_"] [data-testid="stButton"] [data-testid="stMarkdownContainer"] {
  width:100% !important; text-align:left !important;
}
.task-badges { display:flex; flex-wrap:wrap; align-items:center; gap:.3rem; }
.task-detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem 1.25rem; margin:.75rem 0 1rem; }
.task-detail-item { min-width:0; }
.task-detail-label { color:#64748B; font-size:.72rem; font-weight:600; text-transform:uppercase; letter-spacing:.035em; margin-bottom:.2rem; }
.task-detail-value { color:#111827; font-size:.92rem; font-weight:500; overflow-wrap:anywhere; }
.task-mobile-header { display:none; }
[class*="st-key-task_desktop_row_"], [class*="st-key-task_mobile_row_"] {
  border:1px solid var(--ws-border); border-radius:var(--r-sm);
  background:var(--ws-white); padding:.38rem .65rem !important; margin-bottom:.28rem;
}
[class*="st-key-task_mobile_row_"] { display:none; }
[class*="st-key-task_desktop_row_"] [data-testid="stVerticalBlock"],
[class*="st-key-task_mobile_row_"] [data-testid="stVerticalBlock"] { gap:.2rem !important; }
[class*="st-key-task_detail_"] [data-testid="stButton"] button {
  border:0 !important; box-shadow:none !important; min-height:1.6rem !important; height:1.6rem !important;
  padding:0 .2rem !important; color:#64748B !important; background:transparent !important;
}
.person-Danna { color:#A16207 !important; background:#FEF3C7 !important; }
.priority-Alta { color:#B91C1C; background:#FEE2E2; }
.priority-Media { color:#A16207; background:#FEF3C7; }
.priority-Baja { color:#047857; background:#D1FAE5; }
.status-done { color:#047857; background:#D1FAE5; }
.status-open { color:#475569; background:#E2E8F0; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--ws-border); }
[data-testid="stTabs"] button[role="tab"] { font-family:'Rubik',sans-serif; font-weight:600; padding:.75rem 1.1rem; }

@media (max-width:640px) {
  html, body, .stApp, [data-testid="stMain"] { max-width:100vw !important; overflow-x:hidden !important; }
  [data-testid="stMainBlockContainer"] { width:100% !important; max-width:100% !important; padding:.8rem .7rem 2rem !important; }
  .task-summary-grid { width:100%; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.45rem; }
  .task-summary { padding:.6rem .7rem; min-height:4rem; }
  .task-summary .label { font-size:.61rem; letter-spacing:.025em; }
  .task-summary .value { font-size:1.2rem; margin-top:.08rem; }
  [class*="st-key-task_table_header"] { display:none !important; }
  .task-mobile-header {
    display:grid; grid-template-columns:minmax(0,1fr) 104px 58px;
    gap:.5rem; padding:0 .65rem .38rem; color:#475569; font-size:.58rem;
    font-weight:700; text-transform:uppercase; letter-spacing:.025em;
  }
  .task-mobile-header span:nth-child(2), .task-mobile-header span:nth-child(3) { text-align:center; }
  .task-mobile-header span { white-space:nowrap; }
  [class*="st-key-task_desktop_row_"] { display:none !important; }
  [class*="st-key-task_mobile_row_"] {
    display:block !important; width:100% !important; max-width:100% !important;
    box-sizing:border-box; min-height:6.6rem; padding:.6rem .65rem !important;
    margin-bottom:.45rem; overflow:visible !important;
  }
  [class*="st-key-task_mobile_row_"] [data-testid="stHorizontalBlock"] {
    display:grid !important;
    grid-template-columns:minmax(0,1fr) 104px 58px !important;
    gap:.5rem !important; align-items:center !important; width:100% !important;
  }
  [class*="st-key-task_mobile_row_"] [data-testid="column"] {
    width:100% !important; min-width:0 !important; max-width:100% !important; flex:none !important;
  }
  [class*="st-key-task_mobile_row_"] .task-badges {
    min-height:4.9rem; flex-direction:column; justify-content:center;
    align-items:center; gap:.25rem;
  }
  [class*="st-key-task_open_mobile_"] [data-testid="stButton"],
  [class*="st-key-task_open_mobile_"] [data-testid="stButton"] > div { width:100% !important; }
  [class*="st-key-task_open_mobile_"] [data-testid="stButton"] button {
    display:block !important; width:100% !important; min-height:4.9rem !important;
    text-align:left !important;
    justify-content:flex-start !important; align-items:flex-start !important;
  }
  [class*="st-key-task_open_mobile_"] [data-testid="stButton"] button *,
  [class*="st-key-task_open_mobile_"] [data-testid="stMarkdownContainer"] {
    width:100% !important; text-align:left !important; justify-content:flex-start !important;
  }
  [class*="st-key-task_mobile_row_"] [class*="st-key-task_open_"] [data-testid="stButton"] button { min-height:3.2rem !important; }
  [class*="st-key-task_mobile_actions_"] [data-testid="stVerticalBlock"] { gap:.3rem !important; }
  [class*="st-key-task_mobile_actions_"] [data-testid="stButton"] button {
    width:2.35rem !important; min-height:2.2rem !important; height:2.2rem !important;
    padding:.15rem !important; margin:0 auto !important;
  }
}
</style>
"""

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WorkSync - Shine And Bright",
    page_icon="✨",
    layout="wide",
)
st.markdown(APP_CSS, unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in [
    ("lang",          "es"),
    ("main_section",  "Órdenes"),
    ("df_result",     None),
    ("df_editor",     None),   # DataFrame con columnas Subir + Ya subido
    ("df_source",     None),   # SupplyPro o Mungo Homes
    ("upload_report", None),   # Resultados del último batch Jobber
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── OAuth callbacks ───────────────────────────────────────────────────────────
if oauth.handle_callback():
    if st.session_state.get("jobber_just_connected"):
        st.session_state.pop("jobber_just_connected", None)
        try:
            client = JobberClient()
            client.enrich_account_info()
            tokens = storage.get_tokens()
            account_name = tokens.get("account_name", "Jobber") if tokens else "Jobber"
            st.success(t("jobber_connect_success", account=account_name))
        except Exception as e:
            st.error(t("jobber_connect_error", err=e))
    elif err := st.session_state.pop("jobber_connect_error", None):
        st.error(t("jobber_connect_error", err=err))


# ── Sidebar ───────────────────────────────────────────────────────────────────
mungo_credentials_ready = bool(MUNGO_USERNAME and MUNGO_PASSWORD)


def select_main_section(section: str) -> None:
    st.session_state.main_section = section

with st.sidebar:
    st.markdown("## ✨ ShineAndBright")
    st.markdown("---")

    st.caption(t("sidebar_lang"))
    lang_choice = st.radio(
        label="lang",
        options=["🇪🇸 Español", "🇬🇧 English"],
        index=0 if st.session_state.lang == "es" else 1,
        label_visibility="collapsed",
    )
    st.session_state.lang = "es" if lang_choice.startswith("🇪🇸") else "en"

    st.markdown("---")
    st.caption("Navegación" if st.session_state.lang == "es" else "Navigation")
    active_section = st.session_state.main_section
    orders_container_key = (
        "sidebar_nav_orders_active" if active_section == "Órdenes" else "sidebar_nav_orders"
    )
    tasks_container_key = (
        "sidebar_nav_tasks_active" if active_section == "Tareas" else "sidebar_nav_tasks"
    )
    with st.container(key=orders_container_key):
        st.button(
            "📦   Órdenes" if st.session_state.lang == "es" else "📦   Orders",
            key="sidebar_orders_button",
            use_container_width=True,
            on_click=select_main_section,
            args=("Órdenes",),
        )
    with st.container(key=tasks_container_key):
        st.button(
            "✅   Tareas" if st.session_state.lang == "es" else "✅   Tasks",
            key="sidebar_tasks_button",
            use_container_width=True,
            on_click=select_main_section,
            args=("Tareas",),
        )
    main_section = st.session_state.main_section

    if main_section == "Órdenes":
        st.markdown("---")
        st.caption(t("sidebar_jobber_status"))

        tokens = storage.get_tokens()
        if tokens:
            account_name = tokens.get("account_name") or "Jobber"
            st.success(t("jobber_connected", account=account_name))

            col_test, col_disc = st.columns(2)
            with col_test:
                if st.button(t("btn_test_connection"), use_container_width=True):
                    try:
                        client = JobberClient()
                        account = client.fetch_account()
                        st.toast(t("jobber_test_ok", account=account["name"]))
                    except JobberAuthError:
                        st.warning(t("jobber_token_expired"))
                    except Exception as e:
                        st.error(t("jobber_test_fail", err=e))
            with col_disc:
                if st.button(t("btn_disconnect_jobber"), use_container_width=True):
                    storage.clear_tokens()
                    st.rerun()
        else:
            st.info(t("jobber_not_connected"))
            auth_url, _ = oauth.build_auth_url()
            st.link_button(t("btn_connect_jobber"), auth_url, use_container_width=True)

        st.markdown("---")
        st.caption(t("sidebar_mungo_status"))
        if mungo_credentials_ready:
            st.success(t("mungo_credentials_ready"))
            if st.button(t("btn_test_mungo"), use_container_width=True):
                with st.spinner(t("mungo_testing_connection")):
                    try:
                        probar_conexion_mungo(MUNGO_USERNAME, MUNGO_PASSWORD)
                        st.success(t("mungo_connection_ok"))
                    except MungoAuthenticationError as error:
                        st.error(str(error))
                    except Exception as error:
                        st.error(t("mungo_connection_error", err=error))
        else:
            st.warning(t("mungo_credentials_missing"))


@st.dialog("Detalle de la tarea", width="small")
def show_task_detail(task: dict):
    """Show the complete task information without expanding the table row."""
    due_date = date.fromisoformat(task["due_date"]).strftime("%d/%m/%Y")
    status = "Completada" if task["completed"] else "Pendiente"
    st.markdown(f"### {html.escape(task['title'])}")
    st.markdown(
        '<div class="task-detail-grid">'
        f'<div class="task-detail-item"><div class="task-detail-label">Asignada a</div><div class="task-detail-value">{html.escape(task["assignee"])}</div></div>'
        f'<div class="task-detail-item"><div class="task-detail-label">Fecha</div><div class="task-detail-value">{due_date}</div></div>'
        f'<div class="task-detail-item"><div class="task-detail-label">Prioridad</div><div class="task-detail-value">{html.escape(task["priority"])}</div></div>'
        f'<div class="task-detail-item"><div class="task-detail-label">Estado</div><div class="task-detail-value">{status}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("**Descripción**")
    st.info(task["description"] or "Sin descripción")


def render_tasks_module():
    """UI del tablero compartido de tareas y sus reportes."""
    init_db()
    st.markdown("### Tablero de tareas")
    st.caption("Crea, prioriza y da seguimiento al trabajo del equipo desde un solo lugar.")

    with st.expander("＋ Crear nueva tarea", expanded=False):
        with st.form("new_task_form", clear_on_submit=True):
            title = st.text_input("Tarea *", placeholder="Ej. Confirmar orden con el cliente")
            description = st.text_area(
                "Descripción", placeholder="Agrega instrucciones o contexto útil…", height=90
            )
            form_col1, form_col2, form_col3 = st.columns(3)
            with form_col1:
                assignee = st.selectbox("Asignar a *", ASSIGNEES)
            with form_col2:
                priority = st.selectbox("Prioridad *", PRIORITIES, index=1)
            with form_col3:
                due_date = st.date_input("Fecha *", value=date.today())
            submitted = st.form_submit_button(
                "Crear tarea", type="primary", use_container_width=True
            )
            if submitted:
                if not title.strip():
                    st.error("Escribe el nombre de la tarea.")
                else:
                    create_task(title, description, assignee, priority, due_date)
                    st.success("Tarea creada correctamente.")
                    st.rerun()

    with st.expander("Filtros", expanded=False):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            assignee_filter = st.multiselect(
                "Persona asignada", ASSIGNEES, placeholder="Todas las personas"
            )
        with filter_col2:
            priority_filter = st.multiselect(
                "Prioridad", PRIORITIES, placeholder="Todas las prioridades"
            )
        with filter_col3:
            status_filter = st.multiselect(
                "Estado", ["Pendiente", "Completada"], placeholder="Todos los estados"
            )

    tasks = list_tasks(assignee_filter, priority_filter, status_filter)
    all_tasks = list_tasks()
    pending_count = sum(not task["completed"] for task in all_tasks)
    completed_count = sum(bool(task["completed"]) for task in all_tasks)
    high_count = sum(not task["completed"] and task["priority"] == "Alta" for task in all_tasks)
    summary_cards = []
    for label, value in zip(
        ("Total", "Pendientes", "Completadas", "Altas pendientes"),
        (len(all_tasks), pending_count, completed_count, high_count),
    ):
        summary_cards.append(
            f'<div class="task-summary"><div class="label">{label}</div>'
            f'<div class="value">{value}</div></div>'
        )
    st.markdown(
        f'<div class="task-summary-grid">{"".join(summary_cards)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("#### Tareas")
    st.caption("Las tareas se ordenan automáticamente: prioridad alta, media y baja.")
    if not tasks:
        st.info("No hay tareas que coincidan con los filtros seleccionados.")
    else:
        page_size = 10
        page_count = max(1, (len(tasks) + page_size - 1) // page_size)
        current_page = min(max(st.session_state.get("task_page", 1), 1), page_count)
        st.session_state.task_page = current_page
        page_start = (current_page - 1) * page_size
        visible_tasks = tasks[page_start:page_start + page_size]

        table_widths = [3.5, 2.1, 1.2, 0.75]
        with st.container(key="task_table_header"):
            header_columns = st.columns(table_widths)
            for column, label in zip(
                header_columns,
                ("Tarea", "Información", "Fecha", "Acciones"),
            ):
                column.markdown(f'<div class="task-grid-header">{label}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="task-mobile-header"><span>Tarea</span>'
            '<span>Información</span><span>Acciones</span></div>',
            unsafe_allow_html=True,
        )

        for task in visible_tasks:
            person_color = ASSIGNEE_COLORS.get(task["assignee"], "#475569")
            done = bool(task["completed"])
            full_description = task["description"] or "Sin descripción"
            short_description = (
                full_description if len(full_description) <= 62
                else f"{full_description[:59].rstrip()}…"
            )
            with st.container(key=f'task_desktop_row_{task["id"]}'):
                row_columns = st.columns(table_widths, vertical_alignment="center")
                with row_columns[0]:
                    st.markdown(
                        f'<div class="task-title">{html.escape(task["title"])}</div>',
                        unsafe_allow_html=True,
                    )
                    description_col, detail_col = st.columns(
                        [9, 1], gap="small", vertical_alignment="center"
                    )
                    description_col.markdown(
                        f'<div class="task-desc">{html.escape(short_description)}</div>',
                        unsafe_allow_html=True,
                    )
                    with detail_col:
                        with st.container(key=f'task_detail_desktop_{task["id"]}'):
                            if st.button(
                                "ⓘ",
                                key=f'task_desktop_detail_button_{task["id"]}',
                                help="Ver información completa",
                            ):
                                show_task_detail(task)
                row_columns[1].markdown(
                    f'<div class="task-badges"><span class="person-pill person-{html.escape(task["assignee"])}" '
                    f'style="color:{person_color};background:{person_color}18">'
                    f'{html.escape(task["assignee"])}</span>'
                    f'<span class="priority-pill priority-{task["priority"]}">{task["priority"]}</span>'
                    f'<span class="status-pill {"status-done" if done else "status-open"}">'
                    f'{"Completada" if done else "Pendiente"}</span></div>',
                    unsafe_allow_html=True,
                )
                row_columns[2].markdown(
                    f'<div class="task-grid-cell">{date.fromisoformat(task["due_date"]).strftime("%d/%m/%Y")}</div>',
                    unsafe_allow_html=True,
                )
                with row_columns[3]:
                    with st.container(key=f'task_desktop_actions_{task["id"]}'):
                        if st.button(
                            "↩" if done else "✓",
                            key=f'task_desktop_toggle_{task["id"]}',
                            help="Reabrir tarea" if done else "Marcar como completada",
                            use_container_width=True,
                        ):
                            set_completed(task["id"], not done)
                            st.toast("Estado actualizado.")
                            st.rerun()
                        if st.button(
                            "🗑",
                            key=f'task_desktop_delete_{task["id"]}',
                            help="Eliminar tarea",
                            use_container_width=True,
                        ):
                            st.session_state.confirm_delete_task_id = task["id"]
                            st.rerun()

            with st.container(key=f'task_mobile_row_{task["id"]}'):
                mobile_task_col, mobile_badges_col, mobile_actions_col = st.columns(
                    [1.7, .8, .42], vertical_alignment="center"
                )
                with mobile_task_col:
                    with st.container(key=f'task_open_mobile_{task["id"]}'):
                        if st.button(
                            f'**{task["title"]}**  \n{short_description}',
                            key=f'task_mobile_open_button_{task["id"]}',
                            help="Ver información completa",
                            use_container_width=True,
                        ):
                            show_task_detail(task)
                mobile_badges_col.markdown(
                    f'<div class="task-badges"><span class="person-pill person-{html.escape(task["assignee"])}" '
                    f'style="color:{person_color};background:{person_color}18">'
                    f'{html.escape(task["assignee"])}</span>'
                    f'<span class="priority-pill priority-{task["priority"]}">{task["priority"]}</span>'
                    f'<span class="status-pill {"status-done" if done else "status-open"}">'
                    f'{"Completada" if done else "Pendiente"}</span></div>',
                    unsafe_allow_html=True,
                )
                with mobile_actions_col:
                    with st.container(key=f'task_mobile_actions_{task["id"]}'):
                        if st.button(
                            "↩" if done else "✓",
                            key=f'task_mobile_toggle_{task["id"]}',
                            help="Reabrir tarea" if done else "Marcar como completada",
                            use_container_width=True,
                        ):
                            set_completed(task["id"], not done)
                            st.toast("Estado actualizado.")
                            st.rerun()
                        if st.button(
                            "🗑",
                            key=f'task_mobile_delete_{task["id"]}',
                            help="Eliminar tarea",
                            use_container_width=True,
                        ):
                            st.session_state.confirm_delete_task_id = task["id"]
                            st.rerun()

            if st.session_state.get("confirm_delete_task_id") == task["id"]:
                st.warning(f'¿Eliminar definitivamente “{task["title"]}”?')
                confirm_col, cancel_col, _ = st.columns([1, 1, 4])
                with confirm_col:
                    if st.button("Sí, eliminar", key=f'confirm_delete_{task["id"]}', type="primary"):
                        delete_task(task["id"])
                        st.session_state.pop("confirm_delete_task_id", None)
                        st.toast("Tarea eliminada.")
                        st.rerun()
                with cancel_col:
                    if st.button("Cancelar", key=f'cancel_delete_{task["id"]}'):
                        st.session_state.pop("confirm_delete_task_id", None)
                        st.rerun()

        if page_count > 1:
            previous_col, page_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
            with previous_col:
                if st.button(
                    "← Anterior",
                    disabled=current_page == 1,
                    use_container_width=True,
                    key="task_page_previous",
                ):
                    st.session_state.task_page = current_page - 1
                    st.rerun()
            with page_col:
                st.markdown(
                    f'<p style="text-align:center;margin:.45rem 0;color:#64748B;font-size:.82rem">'
                    f'Página <strong>{current_page}</strong> de <strong>{page_count}</strong> · '
                    f'{len(tasks)} tareas</p>',
                    unsafe_allow_html=True,
                )
            with next_col:
                if st.button(
                    "Siguiente →",
                    disabled=current_page == page_count,
                    use_container_width=True,
                    key="task_page_next",
                ):
                    st.session_state.task_page = current_page + 1
                    st.rerun()

    st.markdown("---")
    st.markdown("### Reporte PDF")
    st.caption("Selecciona un día, semana, mes o rango personalizado de hasta un año.")
    report_col1, report_col2, report_col3 = st.columns(3)
    with report_col1:
        period = st.selectbox("Periodo", ["Día", "Semana", "Mes", "Personalizado"])
    with report_col2:
        report_status = st.selectbox("Estado de las tareas", ["Todas", "Completadas", "Pendientes"])

    today = date.today()
    if period == "Personalizado":
        with report_col3:
            custom_dates = st.date_input(
                "Rango de fechas",
                value=(today - timedelta(days=30), today),
                max_value=today + timedelta(days=365),
            )
        if isinstance(custom_dates, (tuple, list)) and len(custom_dates) == 2:
            report_start, report_end = custom_dates
        else:
            report_start = report_end = custom_dates[0] if isinstance(custom_dates, (tuple, list)) else custom_dates
    else:
        with report_col3:
            reference_date = st.date_input("Fecha de referencia", value=today, key="report_reference")
        if period == "Día":
            report_start = report_end = reference_date
        elif period == "Semana":
            report_start = reference_date - timedelta(days=reference_date.weekday())
            report_end = report_start + timedelta(days=6)
        else:
            report_start = reference_date.replace(day=1)
            next_month = (report_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            report_end = next_month - timedelta(days=1)

    range_days = (report_end - report_start).days
    if report_end < report_start:
        st.error("La fecha final debe ser posterior a la fecha inicial.")
    elif range_days > 366:
        st.error("El reporte puede abarcar como máximo un año.")
    else:
        selected_report_tasks = report_tasks(report_start, report_end, report_status)
        st.caption(
            f"{len(selected_report_tasks)} tareas · "
            f"{report_start.strftime('%d/%m/%Y')} al {report_end.strftime('%d/%m/%Y')}"
        )
        pdf_data = build_pdf(selected_report_tasks, report_start, report_end, report_status)
        st.download_button(
            "Descargar reporte PDF",
            data=pdf_data,
            file_name=f"reporte_tareas_{report_start.isoformat()}_{report_end.isoformat()}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )


# ── Contenido principal ───────────────────────────────────────────────────────
st.title(t("app_title"))
if main_section == "Tareas":
    st.markdown("### Gestión compartida de tareas")
else:
    st.markdown(f"### {t('app_subtitle')}")
st.markdown("---")

if main_section == "Tareas":
    render_tasks_module()
    st.stop()

# ── Extracción ────────────────────────────────────────────────────────────────
source_choice = st.radio(
    t("source_label"),
    options=[t("source_supplypro"), t("source_mungo")],
    horizontal=True,
    key="order_source_choice",
)

if source_choice == t("source_supplypro"):
    if not storage.has_tokens():
        st.warning(t("warning_connect_jobber_first"))

    if st.button(t("btn_export"), type="primary", use_container_width=True, disabled=not storage.has_tokens()):
        with st.spinner(t("spinner_extracting")):
            try:
                st.info(t("info_connecting"))
                df_raw = ejecutar_extraccion(SUPPLYPRO_USERNAME, SUPPLYPRO_PASSWORD)

                st.info(t("info_processing"))
                df_final = transformar_ordenes(df_raw, "ShineAndBright")

                if len(df_final) == 0:
                    st.warning(t("warning_no_orders"))
                    st.session_state.df_result = None
                    st.session_state.df_editor = None
                    st.session_state.df_source = None
                else:
                    st.session_state.df_result = df_final
                    df_edit = df_final.copy()
                    df_edit.insert(0, t("col_upload"), True)
                    df_edit[t("col_uploaded")] = False
                    st.session_state.df_editor = df_edit
                    st.session_state.df_source = t("source_supplypro")
                    st.session_state.upload_report = None
                    st.success(t("success_extracted", n=len(df_final)))

            except Exception as e:
                st.error(t("error_extraction", err=e))
                st.info(t("info_retry"))
else:
    st.markdown(f"### {t('mungo_section_title')}")
    date_mode = st.radio(
        t("mungo_date_mode"),
        options=[t("mungo_one_date"), t("mungo_date_range")],
        horizontal=True,
        key="mungo_date_mode",
    )
    if date_mode == t("mungo_one_date"):
        selected_date = st.date_input(
            t("mungo_start_date"),
            value=date.today(),
            key="mungo_exact_start_date",
        )
        selected_from = selected_date
        selected_to = selected_date
    else:
        default_to = date.today()
        default_from = default_to - timedelta(days=30)
        date_col_from, date_col_to = st.columns(2)
        with date_col_from:
            selected_from = st.date_input(
                t("mungo_date_from"), value=default_from, key="mungo_date_from"
            )
        with date_col_to:
            selected_to = st.date_input(
                t("mungo_date_to"), value=default_to, key="mungo_date_to"
            )

    st.success(t("mungo_mapping_ready"))
    if st.button(
        t("btn_export_mungo"),
        type="primary",
        use_container_width=True,
        disabled=not mungo_credentials_ready,
    ):
        with st.spinner(t("mungo_extracting_start_date")):
            try:
                df_raw = ejecutar_extraccion_mungo(
                    MUNGO_USERNAME,
                    MUNGO_PASSWORD,
                    selected_from,
                    selected_to,
                    date_filter="start_date",
                )
                df_final = transformar_ordenes_mungo(df_raw)
                if df_final.empty:
                    st.warning(t("mungo_no_orders_for_date"))
                    st.session_state.df_result = None
                    st.session_state.df_editor = None
                    st.session_state.df_source = None
                else:
                    st.session_state.df_result = df_final
                    df_edit = df_final.copy()
                    df_edit.insert(0, t("col_upload"), True)
                    df_edit[t("col_uploaded")] = False
                    st.session_state.df_editor = df_edit
                    st.session_state.df_source = t("source_mungo")
                    st.session_state.upload_report = None
                    st.success(t("success_extracted", n=len(df_final)))
            except MungoAuthenticationError as error:
                st.error(str(error))
            except Exception as error:
                st.error(t("error_extraction", err=error))


# ── Tabla editable ────────────────────────────────────────────────────────────
if (
    st.session_state.df_editor is not None
    and st.session_state.df_source == source_choice
):
    df_edit = st.session_state.df_editor
    col_subir    = t("col_upload")
    col_uploaded = t("col_uploaded")

    st.markdown("---")
    st.markdown(f"### {t('section_results')}")

    # Detectar filas con total inválido para mostrar advertencia
    invalid_rows = []
    for i, row in df_edit.iterrows():
        err = validate_row(row.to_dict())
        if err:
            invalid_rows.append(f"Fila {i + 1} — {err}")
    if invalid_rows:
        st.warning("⚠️ " + " · ".join(invalid_rows))

    # Botones seleccionar / deseleccionar todas (solo filas no subidas)
    btn_all, btn_none, _ = st.columns([1, 1, 6])
    with btn_all:
        if st.button("☑ Todas", use_container_width=True):
            mask = st.session_state.df_editor[col_uploaded] == False
            st.session_state.df_editor.loc[mask, col_subir] = True
            st.rerun()
    with btn_none:
        if st.button("☐ Ninguna", use_container_width=True):
            mask = st.session_state.df_editor[col_uploaded] == False
            st.session_state.df_editor.loc[mask, col_subir] = False
            st.rerun()

    # Columnas configuradas para el editor
    col_config = {
        col_subir: st.column_config.CheckboxColumn(
            col_subir, help="Marcar para subir a Jobber", default=True
        ),
        col_uploaded: st.column_config.CheckboxColumn(
            col_uploaded, disabled=True
        ),
        "Client Name": st.column_config.TextColumn("Client Name", width="medium"),
        "Job title Final": st.column_config.TextColumn("Job Title", width="large"),
        "Full Property Address": st.column_config.TextColumn("Address", width="large"),
        "total": st.column_config.TextColumn("Total", width="small"),
        "Start Date": st.column_config.TextColumn("Start Date", width="small"),
    }

    edited = st.data_editor(
        df_edit,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="data_editor_widget",
    )
    # Persistir ediciones entre reruns
    st.session_state.df_editor = edited

    # Métricas rápidas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(t("metric_total_orders"), len(edited))
    with col2:
        st.metric(t("metric_unique_clients"), edited["Client Name"].nunique())
    with col3:
        try:
            total_amt = (
                edited["total"]
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .astype(float)
                .sum()
            )
            st.metric(t("metric_total_amount"), f"${total_amt:,.2f}")
        except Exception:
            st.metric(t("metric_total_amount"), "N/A")

    # ── Descargas ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"### {t('section_download')}")

    df_download = edited.drop(columns=[col_subir, col_uploaded], errors="ignore")
    download_slug = (
        "mungo_homes"
        if st.session_state.df_source == t("source_mungo")
        else "shineandbright"
    )
    col_csv, col_xlsx = st.columns(2)
    with col_csv:
        csv_data = df_download.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label=t("btn_csv"),
            data=csv_data.encode("utf-8-sig"),
            file_name=f"ordenes_{download_slug}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_xlsx:
        buffer = BytesIO()
        df_download.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        st.download_button(
            label=t("btn_excel"),
            data=buffer,
            file_name=f"ordenes_{download_slug}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ── Botón Subir a Jobber ──────────────────────────────────────────────────
    pending_rows = edited[
        (edited[col_subir] == True) & (edited[col_uploaded] == False)
    ]
    jobber_connected = storage.has_tokens()

    if jobber_connected and len(pending_rows) > 0:
        st.markdown("---")
        if st.button(
            f"{t('btn_upload_jobber')} ({len(pending_rows)})",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["trigger_upload"] = True
            st.rerun()


# ── Upload a Jobber (se ejecuta en el siguiente rerun) ────────────────────────
if st.session_state.pop("trigger_upload", False):
    df_edit      = st.session_state.df_editor
    col_subir    = t("col_upload")
    col_uploaded = t("col_uploaded")
    pending      = df_edit[(df_edit[col_subir] == True) & (df_edit[col_uploaded] == False)]
    total_rows   = len(pending)

    progress_bar = st.progress(0)
    status_text  = st.empty()
    results      = []

    try:
        client = JobberClient()
    except JobberAuthError as e:
        st.error(str(e))
        st.stop()

    # Importar aquí para no cargar en cada rerun
    from jobber.mutations import (
        LIST_CLIENTS_QUERY, CREATE_CLIENT_MUTATION,
        FIND_PROPERTY_QUERY, CREATE_PROPERTY_MUTATION,
        CREATE_JOB_MUTATION, VISIT_START_MUTATION,
    )
    from jobber.mappers import map_row_to_job_input, build_property_input, addresses_match
    import time

    # Cache de clientes y properties para evitar queries repetidas
    client_cache   = {}  # nombre.lower() → id
    property_cache = {}  # client_id → {address_str.lower(): property_id}

    # Cargar todos los clientes una sola vez al inicio del batch
    status_text.info("Cargando clientes de Jobber...")
    all_clients = client.execute(LIST_CLIENTS_QUERY)["data"]["clients"]["nodes"]
    for node in all_clients:
        for key in (node.get("name") or "", node.get("companyName") or ""):
            if key:
                client_cache[key.lower()] = node["id"]

    def get_or_find_client(name: str) -> str:
        cached = client_cache.get(name.lower())
        if cached:
            return cached
        res2 = client.execute(CREATE_CLIENT_MUTATION, {
            "input": {"companyName": name, "isCompany": True}
        })
        errors = res2["data"]["clientCreate"]["userErrors"]
        if errors:
            raise Exception(f"Error creando cliente '{name}': {errors[0]['message']}")
        new_id = res2["data"]["clientCreate"]["client"]["id"]
        client_cache[name.lower()] = new_id
        return new_id

    def get_or_create_property(client_id: str, address_str: str) -> str:
        # Check local cache first
        addr_key = address_str.strip().lower()
        cached = (property_cache.get(client_id) or {}).get(addr_key)
        if cached:
            return cached

        # Query Jobber for existing properties
        res_p = client.execute(FIND_PROPERTY_QUERY, {"clientId": client_id})
        nodes = res_p["data"]["client"]["clientProperties"]["nodes"]
        for node in nodes:
            if addresses_match(node.get("address") or {}, address_str):
                pid = node["id"]
                property_cache.setdefault(client_id, {})[addr_key] = pid
                return pid

        # Create new property
        prop_input = build_property_input(address_str)
        res_c = client.execute(CREATE_PROPERTY_MUTATION, {
            "clientId": client_id,
            "input": {"properties": [prop_input]},
        })
        errors = res_c["data"]["propertyCreate"]["userErrors"]
        if errors:
            raise Exception(f"Error creando propiedad: {errors[0]['message']}")
        properties = res_c["data"]["propertyCreate"]["properties"]
        if not properties:
            raise Exception("propertyCreate no devolvió ninguna propiedad")
        pid = properties[0]["id"]
        property_cache.setdefault(client_id, {})[addr_key] = pid
        return pid

    for i, (idx, row) in enumerate(pending.iterrows()):
        title = row["Job title Final"]
        status_text.info(t("upload_progress", i=i + 1, n=total_rows, title=title))
        progress_bar.progress((i) / total_rows)

        try:
            client_id   = get_or_find_client(row["Client Name"])
            property_id = get_or_create_property(client_id, row["Full Property Address"])
            attributes  = map_row_to_job_input(row.to_dict(), property_id)

            res = client.execute(CREATE_JOB_MUTATION, {"input": attributes})
            errors = res["data"]["jobCreate"]["userErrors"]
            if errors:
                raise Exception(errors[0]["message"])

            job_data = res["data"]["jobCreate"]["job"]

            # Iniciar la visita automáticamente para que quede en ACTIVE
            visit_nodes = job_data.get("visits", {}).get("nodes", [])
            if visit_nodes:
                try:
                    vr = client.execute(VISIT_START_MUTATION, {"visitId": visit_nodes[0]["id"]})
                    v_errors = vr["data"]["visitStart"]["userErrors"]
                    if v_errors:
                        _log.get(__name__).warning("visitStart userError: %s", v_errors[0]["message"])
                except Exception as ve:
                    _log.get(__name__).warning("visitStart falló (job creado OK): %s", ve)

            results.append({
                "order":  title,
                "ok":     True,
                "number": job_data["jobNumber"],
                "url":    job_data["jobberWebUri"],
                "error":  "",
            })
            # Marcar como subido en el editor
            st.session_state.df_editor.at[idx, col_uploaded] = True
            st.session_state.df_editor.at[idx, col_subir]    = False

        except Exception as e:
            results.append({
                "order": title,
                "ok":    False,
                "number": "",
                "url":   "",
                "error": str(e),
            })

        time.sleep(0.3)  # Rate limit conservador

    progress_bar.progress(1.0)
    status_text.success(t("upload_complete"))
    st.session_state.upload_report = results


# ── Reporte de subida ─────────────────────────────────────────────────────────
if st.session_state.upload_report:
    results = st.session_state.upload_report
    st.markdown("---")
    st.markdown(f"### {t('section_upload_report')}")

    ok_count   = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count
    c1, c2 = st.columns(2)
    c1.metric("✅ Exitosas", ok_count)
    c2.metric("❌ Fallidas", fail_count)

    report_df = pd.DataFrame([
        {
            t("report_col_order"):  r["order"],
            t("report_col_status"): "✅" if r["ok"] else "❌",
            t("report_col_job"):    f"#{r['number']}" if r["ok"] else "",
            "Link":                 r["url"] if r["ok"] else "",
            t("report_col_error"):  r["error"],
        }
        for r in results
    ])

    st.dataframe(
        report_df,
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="Abrir en Jobber"),
        },
        use_container_width=True,
        hide_index=True,
    )

    # Descargar reporte
    report_csv = report_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label=t("btn_download_report"),
        data=report_csv.encode("utf-8-sig"),
        file_name="reporte_jobber.csv",
        mime="text/csv",
    )

    # Reintentar fallidas
    failed = [r for r in results if not r["ok"]]
    if failed and st.session_state.df_editor is not None:
        if st.button(t("btn_retry_failed")):
            df_edit = st.session_state.df_editor
            col_subir    = t("col_upload")
            col_uploaded = t("col_uploaded")
            failed_titles = {r["order"] for r in failed}
            mask = df_edit["Job title Final"].isin(failed_titles)
            st.session_state.df_editor.loc[mask, col_subir]    = True
            st.session_state.df_editor.loc[mask, col_uploaded] = False
            st.session_state.upload_report = None
            st.rerun()

# ── Debug: introspección de schema (temporal) ────────────────────────────────
if storage.has_tokens():
    with st.expander("🔧 Debug — Inspeccionar schema de Jobber"):
        from jobber.mutations import INTROSPECT_TYPE_QUERY

        col_single, col_batch = st.columns(2)

        with col_single:
            st.caption("Tipo individual")
            type_name = st.text_input("Nombre del tipo", value="JobInvoicingAttributes")
            if st.button("Inspeccionar"):
                try:
                    _c = JobberClient()
                    result = _c.execute(INTROSPECT_TYPE_QUERY, {"typeName": type_name})
                    type_data = result["data"]["__type"]
                    if not type_data:
                        st.error(f"Tipo '{type_name}' no encontrado.")
                    else:
                        st.write(f"Kind: **{type_data.get('kind')}**")
                        enum_vals = type_data.get("enumValues") or []
                        if enum_vals:
                            st.write("Valores: " + ", ".join(v["name"] for v in enum_vals))
                        fields = type_data.get("inputFields") or []
                        if fields:
                            rows = []
                            for f in fields:
                                ti = f["type"]
                                oti = ti.get("ofType") or {}
                                oti2 = oti.get("ofType") or {}
                                tipo = ti.get("name") or oti.get("name") or oti2.get("name", "")
                                rows.append({"Campo": f["name"], "Tipo": tipo, "Kind": ti["kind"]})
                            st.dataframe(rows, use_container_width=True)
                except Exception as e:
                    st.error(str(e))

        with col_batch:
            st.caption("Batch — tipos pendientes de verificar")
            PENDING_TYPES = [
                "BillingStrategy",
                "BillingFrequencyEnum",
                "ProductOrServiceInput",
                "ServiceInput",
                "LineItemCreateInput",
                "LineItemInputAttributes",
                "ProductAndServiceInput",
            ]
            if st.button("Inspeccionar todos"):
                try:
                    _c = JobberClient()
                    for tn in PENDING_TYPES:
                        result = _c.execute(INTROSPECT_TYPE_QUERY, {"typeName": tn})
                        type_data = result["data"]["__type"]
                        if not type_data:
                            st.warning(f"**{tn}** — no encontrado")
                        else:
                            st.markdown(f"**{tn}** ({type_data.get('kind', '')})")
                            enum_vals = type_data.get("enumValues") or []
                            if enum_vals:
                                st.write(", ".join(v["name"] for v in enum_vals))
                            fields = type_data.get("inputFields") or []
                            if fields:
                                rows = []
                                for f in fields:
                                    ti = f["type"]
                                    oti = ti.get("ofType") or {}
                                    oti2 = oti.get("ofType") or {}
                                    tipo = ti.get("name") or oti.get("name") or oti2.get("name", "")
                                    rows.append({"Campo": f["name"], "Tipo": tipo, "Kind": ti["kind"]})
                                st.dataframe(rows, use_container_width=True)
                except Exception as e:
                    st.error(str(e))

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
footer_html = t("footer").replace(
    "Alejandro Campos",
    "<a href='https://alejandrocampos.dev/' target='_blank' rel='noopener noreferrer' style='color:#2563eb; text-decoration:underline; text-underline-offset:2px;'>Alejandro Campos</a>",
)
st.markdown(
    f"<p style='text-align:center; color:gray;'>{footer_html}</p>",
    unsafe_allow_html=True,
)
