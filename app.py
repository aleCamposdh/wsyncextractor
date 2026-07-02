"""
ShineAndBright — SupplyPro Extractor + Jobber Uploader
"""
import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
from datetime import datetime as _dt
import subprocess
import sys

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
from config import SUPPLYPRO_USERNAME, SUPPLYPRO_PASSWORD
from scraper import ejecutar_extraccion
from transformer import transformar_ordenes
from jobber import storage, oauth
from jobber.client import JobberClient, JobberAuthError
from jobber.mappers import parse_total, validate_row
from qbo import storage as qbo_storage, oauth as qbo_oauth
from qbo.client import QBOClient, QBOAuthError
from qbo.parser import parse_visits_csv

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
    ("df_result",     None),
    ("df_editor",     None),   # DataFrame con columnas Subir + Ya subido
    ("upload_report", None),   # Resultados del último batch Jobber
    ("qbo_report",    None),   # Resultados del último batch QBO
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── OAuth callbacks ───────────────────────────────────────────────────────────
# QBO callback detectado primero (tiene realmId en URL)
if qbo_oauth.handle_callback():
    if st.session_state.get("qbo_just_connected"):
        st.session_state.pop("qbo_just_connected", None)
        try:
            qbo = QBOClient()
            info = qbo.fetch_company_info()
            company = info.get("CompanyName", "QuickBooks")
            qbo_tokens = qbo_storage.get_tokens()
            if qbo_tokens:
                qbo_storage.save_tokens(
                    access_token=qbo_tokens["access_token"],
                    refresh_token=qbo_tokens["refresh_token"],
                    expires_at=_dt.fromisoformat(qbo_tokens["expires_at"]),
                    realm_id=qbo_tokens["realm_id"],
                    company_name=company,
                )
            st.success(t("qbo_connect_success", company=company))
        except Exception as e:
            st.error(t("qbo_connect_error", err=e))
    elif err := st.session_state.pop("qbo_connect_error", None):
        st.error(t("qbo_connect_error", err=err))

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
    st.caption(t("section_qbo"))

    qbo_tokens = qbo_storage.get_tokens()
    if qbo_tokens:
        company_name = qbo_tokens.get("company_name") or "QuickBooks"
        st.success(t("qbo_connected", company=company_name))
        col_qt, col_qd = st.columns(2)
        with col_qt:
            if st.button(t("btn_test_qbo"), use_container_width=True):
                try:
                    qbo = QBOClient()
                    info = qbo.fetch_company_info()
                    st.toast(t("qbo_test_ok", company=info.get("CompanyName", "QBO")))
                except QBOAuthError:
                    st.warning(t("qbo_token_expired"))
                except Exception as e:
                    st.error(t("qbo_test_fail", err=e))
        with col_qd:
            if st.button(t("btn_disconnect_qbo"), use_container_width=True):
                qbo_storage.clear_tokens()
                st.rerun()
    else:
        st.info(t("qbo_not_connected"))
        qbo_auth_url = qbo_oauth.build_auth_url()
        st.link_button(t("btn_connect_qbo"), qbo_auth_url, use_container_width=True)


# ── Contenido principal ───────────────────────────────────────────────────────
st.title(t("app_title"))
st.markdown(f"### {t('app_subtitle')}")
st.markdown("---")

# ── Extracción ────────────────────────────────────────────────────────────────
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
                st.session_state.df_result  = None
                st.session_state.df_editor  = None
            else:
                st.session_state.df_result = df_final
                # Inicializar tabla editable con columnas de control
                df_edit = df_final.copy()
                df_edit.insert(0, t("col_upload"),   True)
                df_edit[t("col_uploaded")] = False
                st.session_state.df_editor  = df_edit
                st.session_state.upload_report = None
                st.success(t("success_extracted", n=len(df_final)))

        except Exception as e:
            st.error(t("error_extraction", err=e))
            st.info(t("info_retry"))


# ── Tabla editable ────────────────────────────────────────────────────────────
if st.session_state.df_editor is not None:
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
    col_csv, col_xlsx = st.columns(2)
    with col_csv:
        csv_data = df_download.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label=t("btn_csv"),
            data=csv_data.encode("utf-8-sig"),
            file_name="ordenes_shineandbright.csv",
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
            file_name="ordenes_shineandbright.xlsx",
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


# ── Sección QBO: crear facturas desde Visits Report ──────────────────────────
st.markdown("---")
st.markdown(f"### {t('section_qbo_upload')}")
st.caption(t("qbo_upload_hint"))

if not qbo_storage.has_tokens():
    st.warning(t("qbo_warning_not_connected"))
else:
    with st.expander("🔍 Debug — Campos personalizados QBO"):
        try:
            _qbo_dbg = QBOClient()

            st.caption("Query CustomFieldDefinition (NEW custom fields):")
            try:
                _defs = _qbo_dbg.query("SELECT * FROM CustomFieldDefinition")
                st.json(_defs)
            except Exception as _q_err:
                st.warning(f"Query falló: {_q_err}")

            st.caption("GET /customfielddefinition (REST):")
            try:
                import requests as _req
                _resp = _req.get(
                    _qbo_dbg._url("customfielddefinition"),
                    params={"minorversion": "75"},
                    headers=_qbo_dbg._headers(),
                    timeout=30,
                )
                st.write(f"Status: {_resp.status_code}")
                st.json(_resp.json())
            except Exception as _r_err:
                st.warning(f"REST falló: {_r_err}")

            st.caption("Mapping estático actual:")
            st.json(_qbo_dbg.get_custom_field_ids())
        except Exception as _e:
            st.error(f"Error: {_e}")

    uploaded_csv = st.file_uploader(
        t("qbo_upload_label"),
        type=["csv"],
        key="qbo_visits_upload",
    )

    if uploaded_csv is not None:
        try:
            df_visits = pd.read_csv(uploaded_csv, dtype=str)
            # Parser maneja conversión de monto (acepta "$1,234.00", negativos, etc.)
            invoice_rows, skipped_rows = parse_visits_csv(df_visits)
        except Exception as parse_err:
            st.error(f"Error leyendo el CSV: {parse_err}")
            invoice_rows, skipped_rows = [], []

        if invoice_rows:
            st.markdown(t("qbo_preview_title", n=len(invoice_rows)))
            preview_df = pd.DataFrame([
                {
                    t("qbo_col_title"):    r["title"],
                    t("qbo_col_customer"): f"{r['builder']} / {r['community']}" if r["community"] else r["builder"],
                    "LOT":                 r.get("lot", ""),
                    "Order #":             r.get("order_number", ""),
                    "Cleaner":             r.get("cleaner", ""),
                    t("qbo_col_amount"):   f"${r['amount']:,.2f}",
                    "Fecha":               r["txn_date"],
                }
                for r in invoice_rows
            ])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            if skipped_rows:
                with st.expander(f"⚠️ {len(skipped_rows)} filas omitidas del CSV"):
                    st.dataframe(
                        pd.DataFrame(skipped_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

            if st.button(
                t("btn_create_invoices", n=len(invoice_rows)),
                type="primary",
                use_container_width=True,
            ):
                st.session_state["trigger_qbo_upload"] = invoice_rows
                st.rerun()
        else:
            st.info("No se encontraron facturas válidas en el archivo (sin EPO y con monto > 0).")
            if skipped_rows:
                with st.expander(f"⚠️ {len(skipped_rows)} filas omitidas"):
                    st.dataframe(pd.DataFrame(skipped_rows), use_container_width=True, hide_index=True)


# ── Crear facturas QBO (siguiente rerun) ──────────────────────────────────────
if invoice_rows_pending := st.session_state.pop("trigger_qbo_upload", None):
    total_inv  = len(invoice_rows_pending)
    qbo_prog   = st.progress(0)
    qbo_status = st.empty()
    qbo_results = []

    try:
        qbo = QBOClient()
    except QBOAuthError as e:
        st.error(str(e))
        st.stop()

    # Precargar custom fields y términos una sola vez
    qbo.get_custom_field_ids()
    qbo.get_net15_term_id()

    # Cache de clientes para el batch
    _cust_cache: dict[str, str] = {}

    import time as _time

    for i, row in enumerate(invoice_rows_pending):
        qbo_status.info(t("qbo_invoice_progress", i=i + 1, n=total_inv, title=row["title"]))
        qbo_prog.progress(i / total_inv)

        try:
            cache_key = f"{row['builder']}||{row['community']}||{row.get('lot', '')}"
            if cache_key not in _cust_cache:
                _cust_cache[cache_key] = qbo.resolve_customer_id(
                    row["builder"],
                    row["community"],
                    row.get("lot", ""),
                    address=row.get("address"),
                )
            customer_id = _cust_cache[cache_key]

            inv = qbo.create_invoice(
                customer_id=customer_id,
                txn_date=row["txn_date"],
                amount=row["amount"],
                service_type=row["service_type"],
                order_number=row["order_number"],
                cleaner=row.get("cleaner", ""),
            )
            qbo_results.append({
                "title":      row["title"],
                "customer":   f"{row['builder']} / {row['community']}" if row["community"] else row["builder"],
                "amount":     row["amount"],
                "ok":         True,
                "invoice_no": str(inv.get("DocNumber", "")),
                "error":      "",
            })
        except Exception as inv_err:
            qbo_results.append({
                "title":      row["title"],
                "customer":   row["builder"],
                "amount":     row["amount"],
                "ok":         False,
                "invoice_no": "",
                "error":      str(inv_err),
            })

        _time.sleep(0.2)

    qbo_prog.progress(1.0)
    qbo_status.success(t("qbo_invoice_complete"))
    st.session_state["qbo_report"] = qbo_results


# ── Reporte QBO ───────────────────────────────────────────────────────────────
if st.session_state.get("qbo_report"):
    qbo_results = st.session_state["qbo_report"]
    st.markdown(f"### {t('section_qbo_report')}")

    ok_c   = sum(1 for r in qbo_results if r["ok"])
    fail_c = len(qbo_results) - ok_c
    c1, c2 = st.columns(2)
    c1.metric("✅ Exitosas", ok_c)
    c2.metric("❌ Fallidas", fail_c)

    report_qbo = pd.DataFrame([
        {
            t("qbo_col_title"):    r["title"],
            t("qbo_col_customer"): r["customer"],
            t("qbo_col_amount"):   f"${r['amount']:,.2f}",
            t("qbo_col_status"):   "✅" if r["ok"] else "❌",
            t("qbo_col_invoice"):  r["invoice_no"],
            t("qbo_col_error"):    r["error"],
        }
        for r in qbo_results
    ])
    st.dataframe(report_qbo, use_container_width=True, hide_index=True)

    st.download_button(
        label=t("btn_download_report"),
        data=report_qbo.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
        file_name="reporte_qbo.csv",
        mime="text/csv",
    )


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
st.markdown(
    f"<p style='text-align:center; color:gray;'>{t('footer')}</p>",
    unsafe_allow_html=True,
)
