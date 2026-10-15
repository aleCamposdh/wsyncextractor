import streamlit as st
from supabase import Client, create_client


def _base_supabase_url(value: str) -> str:
    url = value.strip().rstrip("/")
    for suffix in ("/rest/v1", "/auth/v1", "/storage/v1"):
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        _base_supabase_url(st.secrets["SUPABASE_URL"]),
        st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
    )
