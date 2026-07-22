"""Transformación del reporte de Purchase Orders de Mungo Homes."""

from __future__ import annotations

from datetime import date, datetime
import re

import pandas as pd


FINAL_COLUMNS = [
    "Client Name",
    "Job title Final",
    "Full Property Address",
    "total",
    "Start Date",
]

REQUIRED_SOURCE_COLUMNS = {
    "activity": "Activity",
    "lot#": "Lot#",
    "community": "Community",
    "po#": "PO#",
    "address": "Address",
    "po amount": "PO Amount",
    "start date": "Start Date",
}

COMMUNITY_ADDRESS_SUFFIX = {
    "WILLOWBROOK": "Shelby, NC 28150",
    "RYDER PARK": "Charlotte, NC 28215",
    "WESTVIEW": "Charlotte, NC 28214",
}


def _column_key(value: object) -> str:
    """Normaliza encabezados sin perder caracteres significativos como '#'."""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _cell_text(value: object) -> str:
    """Convierte celdas de Excel a texto y elimina el sufijo .0 artificial."""
    if pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return re.sub(r"^(\d+)\.0$", r"\1", text)


def limpiar_activity(value: object) -> str:
    """Quita el prefijo anterior al primer guión: A-B-C -> B-C."""
    text = _cell_text(value)
    if "-" in text:
        text = text.split("-", 1)[1]
    return text.strip()


def construir_direccion(address: object, community: object) -> str:
    """Completa la calle con ciudad, estado y ZIP según la comunidad."""
    street = _cell_text(address)
    community_key = _cell_text(community).upper()
    suffix = COMMUNITY_ADDRESS_SUFFIX.get(community_key, "")
    if not street or not suffix:
        return street
    if street.casefold().endswith(suffix.casefold()):
        return street
    return f"{street.rstrip(', ')}, {suffix}"


def normalizar_total(value: object) -> str:
    """Devuelve un monto compatible con Jobber usando punto decimal."""
    if pd.isna(value) or str(value).strip() == "":
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.2f}"

    text = re.sub(r"[^\d,.-]", "", str(value).strip())
    if not text:
        return ""

    if "," in text and "." in text:
        # El separador que aparezca de último es el decimal.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)

    try:
        return f"{float(text):.2f}"
    except ValueError:
        return ""


def normalizar_fecha(value: object) -> str:
    """Convierte fechas de Kova como 7/1/26 a MM/DD/YYYY."""
    if pd.isna(value) or str(value).strip() == "":
        return ""
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.strftime("%m/%d/%Y")

    text = str(value).strip()
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?!\d)", text)
    if not match:
        return ""
    month, day, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000 if year < 69 else 1900
    try:
        return datetime(year, month, day).strftime("%m/%d/%Y")
    except ValueError:
        return ""


def filtrar_por_start_date(
    df_raw: pd.DataFrame,
    date_from: date,
    date_to: date,
) -> pd.DataFrame:
    """Filtra localmente la grilla Kova por su columna Start Date."""
    if date_from > date_to:
        raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
    if df_raw is None or df_raw.empty:
        return df_raw.copy() if df_raw is not None else pd.DataFrame()

    available = {_column_key(column): column for column in df_raw.columns}
    start_date_column = available.get("start date")
    if start_date_column is None:
        raise ValueError("La tabla de Mungo no contiene la columna Start Date.")

    normalized = df_raw[start_date_column].map(normalizar_fecha)
    parsed = pd.to_datetime(normalized, format="%m/%d/%Y", errors="coerce").dt.date
    mask = parsed.map(
        lambda value: bool(pd.notna(value) and date_from <= value <= date_to)
    )
    return df_raw.loc[mask].reset_index(drop=True)


def transformar_ordenes_mungo(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Mapea un reporte Kova al esquema compartido por WorkSyncExtractor."""
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    available = {_column_key(column): column for column in df_raw.columns}
    missing = [label for key, label in REQUIRED_SOURCE_COLUMNS.items() if key not in available]
    if missing:
        raise ValueError(f"Faltan columnas requeridas de Mungo: {', '.join(missing)}")

    source = {
        label: df_raw[available[key]]
        for key, label in REQUIRED_SOURCE_COLUMNS.items()
    }
    df = pd.DataFrame(source)

    activity = df["Activity"].map(limpiar_activity)
    lot = df["Lot#"].map(_cell_text)
    community = df["Community"].map(_cell_text)
    po_number = df["PO#"].map(_cell_text)

    result = pd.DataFrame({
        "Client Name": "Mungo Homes",
        "Job title Final": activity + " / LOT " + lot + " / " + community + " / " + po_number,
        "Full Property Address": [
            construir_direccion(address, community_name)
            for address, community_name in zip(df["Address"], df["Community"])
        ],
        "total": df["PO Amount"].map(normalizar_total),
        "Start Date": df["Start Date"].map(normalizar_fecha),
    })

    # Una fila sin PO no representa una orden utilizable.
    result = result[po_number.ne("")].reset_index(drop=True)
    return result[FINAL_COLUMNS]
