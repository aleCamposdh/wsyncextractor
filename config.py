import os
import streamlit as st


def _secret(key: str, fallback_env: str) -> str:
    """Lee de st.secrets si existe, si no del entorno."""
    try:
        return st.secrets[key]
    except Exception:
        val = os.environ.get(fallback_env, "")
        if not val:
            raise RuntimeError(
                f"Falta credencial '{key}'. "
                f"Configúrala en Streamlit Cloud secrets o en la variable de entorno '{fallback_env}'."
            )
        return val


# Credenciales SupplyPro — leer de secrets/env, nunca hardcodeadas
SUPPLYPRO_USERNAME = _secret("SUPPLYPRO_USERNAME", "SUPPLYPRO_USERNAME")
SUPPLYPRO_PASSWORD = _secret("SUPPLYPRO_PASSWORD", "SUPPLYPRO_PASSWORD")

SUPPLYPRO_URL = "https://www.hyphensolutions.com/MH2Supply/Login.asp"

# Mapas de reglas ShineAndBright
SHINE_TASK_MAP = {
    "Interior Cleaning Draw 1 Base": "ROUGH CLEAN",
    "Interior Cleaning Draw 2 Final": "ROUGH RECLEAN",
    "Interior Reclean 1": "FINAL CLEAN",
    "Interior Reclean 2": "RECLEAN",
    "Interior Reclean 3": "RECLEAN",
    "Pressure Washing Draw 2": "REWASH",
    "Pressure Washing Draw 3": "REWASH",
    "Pressure Washing": "FIRST WASH",
    "Cleaning - Pre-Paint Clean": "ROUGH CLEAN",
    "Cleaning - Rough Clean": "ROUGH RECLEAN",
    "Cleaning - Final Clean": "FINAL CLEAN",
    "Cleaning - Final QA Clean": "QA CLEAN",
    "Cleaning - Quality Assurance Clean": "QA CLEAN",
    "Cleaning - TLC Re-Clean": "TLC RECLEAN",
    "Cleaning - Pressure Wash Home": "FIRST WASH",
    "Cleaning - Re-Wash Home": "REWASH",
    "Cleaning - Brick Clean": "BRICK CLEAN",
    "Rough Clean": "ROUGH CLEAN",
    "Final Clean": "FINAL CLEAN",
    "Quality Re-Walk": "QA CLEAN",
    "Interior Clean Touch Up #1": "TOUCH UP",
    "Interior Clean Touch Up #2": "TOUCH UP",
    "Power Wash": "FIRST WASH",
    "Celebration Walk Clean": "TLC RECLEAN",
}

SHINE_CLIENT_MAP = {
    r"^LGI Homes.*": "LGI Homes",
    r"^DRB Group.*": "DRB Group",
    r"^Lennar Homes.*": "Lennar Homes",
}

# Requerido por transformer.py (no se usa en modo ShineAndBright)
APEX_INSTRUCTION_REGEX = []

# Credenciales QuickBooks Online
QBO_CLIENT_ID     = _secret("QBO_CLIENT_ID",     "QBO_CLIENT_ID")
QBO_CLIENT_SECRET = _secret("QBO_CLIENT_SECRET", "QBO_CLIENT_SECRET")

SERVICE_ABBREV_MAP = {
    "ROUGH CLEAN":    "RC",
    "ROUGH RECLEAN":  "RRC",
    "FINAL CLEAN":    "FC",
    "RECLEAN":        "RC",
    "FIRST WASH":     "PW",
    "REWASH":         "RW",
    "QA CLEAN":       "QA",
    "TLC RECLEAN":    "TLC",
    "BRICK CLEAN":    "BC",
    "TOUCH UP":       "TU",
}
# Auto-add original SupplyPro names so Jobber visit titles with un-normalized
# service names (e.g. "Celebration Walk Clean") still get the right abbreviation.
# This runs after both maps are defined.
def _build_extended_abbrev():
    for _orig, _norm in SHINE_TASK_MAP.items():
        key = _orig.upper()
        if key not in SERVICE_ABBREV_MAP:
            abbrev = SERVICE_ABBREV_MAP.get(_norm.upper())
            if abbrev:
                SERVICE_ABBREV_MAP[key] = abbrev
_build_extended_abbrev()
del _build_extended_abbrev

SHINE_SUBDIVISION_MAP = {
    "5536 Lakeside Glen Lake Series 40s": "Lakeside Glen 40s",
    "5537 Lakeside Glen Lake Series 50s": "Lakeside Glen 50s",
    "GAL - Bell Farm 50 - 2487260": "Bell Farm 50",
    "GAL - Bell Farm 60 - 2487360": "Bell Farm 60",
    "GAL - Creekside Cottages Dream - 2489260": "Creekside Cottages Dream",
    "GAL - Elizabeth - - 2485160": "Elizabeth Arbor",
    "GAL - Elizabeth - Chase Det Gar - 2485060": "Elizabeth Chase Det Gar",
    "GAL - Elizabeth - Enclave - 2485460": "Elizabeth Enclave",
    "GAL - Elizabeth - Meadows - 2485360": "Elizabeth Meadows",
    "GAL - Elizabeth - Trinity - 2484960": "Elizabeth Trinity",
    "GAL - Elizabeth - Walk - 2487160": "Elizabeth Walk",
    "GAL - Estates at New Town - 2902460": "Estates at New Town",
    "GAL - Legacy Ridge Dream - 2489960": "Legacy Ridge Dream",
    "GAL - Shannon Woods Meadows - 2486560": "Shannon Woods Meadows",
    "GAL - Shannon Woods Walk Enclave - 2486460": "Shannon Woods Walk Enclave",
    "GAL - Sullivan Farm - 2487960": "Sullivan Farm",
}
