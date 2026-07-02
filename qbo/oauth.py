"""
Flujo OAuth 2.0 para QuickBooks Online (Authorization Code Grant).
"""
import base64
import secrets
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from qbo import storage
import logger as _log

_logger = _log.get(__name__)

AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL     = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPE         = "com.intuit.quickbooks.accounting"


def _client_id() -> str:
    return st.secrets["QBO_CLIENT_ID"]


def _client_secret() -> str:
    return st.secrets["QBO_CLIENT_SECRET"]


def _redirect_uri() -> str:
    return st.secrets.get("APP_URL", "https://worksyncextractor.streamlit.app/")


def _basic_auth_header() -> str:
    raw = f"{_client_id()}:{_client_secret()}"
    encoded = base64.b64encode(raw.encode()).decode()
    return f"Basic {encoded}"


def build_auth_url() -> str:
    state = secrets.token_urlsafe(16)
    st.session_state["qbo_oauth_state"] = state
    params = {
        "client_id":     _client_id(),
        "response_type": "code",
        "scope":         SCOPE,
        "redirect_uri":  _redirect_uri(),
        "state":         state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _exchange_code(code: str, realm_id: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": _basic_auth_header()},
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": _redirect_uri(),
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    data["realm_id"] = realm_id
    return data


def refresh_tokens(refresh_token: str, realm_id: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": _basic_auth_header()},
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    data["realm_id"] = realm_id
    return data


def save_token_response(data: dict, company_name: str = "") -> None:
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    storage.save_tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=expires_at,
        realm_id=data["realm_id"],
        company_name=company_name,
    )


def handle_callback() -> bool:
    """
    Detecta callback de QBO (realmId en query params) y completa el flujo.
    Devuelve True si procesó un callback de QBO.
    """
    params = st.query_params
    code     = params.get("code")
    realm_id = params.get("realmId")
    state    = params.get("state")

    if not code or not realm_id:
        return False

    st.query_params.clear()

    saved_state = st.session_state.pop("qbo_oauth_state", None)
    if saved_state and state != saved_state:
        st.error("❌ QBO OAuth state mismatch — posible ataque CSRF.")
        return True

    try:
        data = _exchange_code(code, realm_id)
        save_token_response(data)
        st.session_state["qbo_just_connected"] = True
    except Exception as e:
        st.session_state["qbo_connect_error"] = str(e)
        _logger.error("QBO OAuth error: %s", e)

    return True
