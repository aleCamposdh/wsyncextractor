"""Historial persistente de órdenes incluidas en archivos de exportación."""

from __future__ import annotations

import re

import pandas as pd

from database import get_supabase


HISTORY_TABLE = "worksync_exported_orders"


def _key_part(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def order_keys(df: pd.DataFrame, source: str) -> list[str]:
    """Crea identificadores estables usando el número único de cada orden."""
    if source != "Mungo Homes":
        raise ValueError("El historial de exportación solo aplica a Mungo Homes.")
    column = "PO#"
    if column not in df.columns:
        raise ValueError("No se encontró el PO# necesario para evitar duplicados.")
    values = df[column].map(_key_part)
    if values.eq("").any():
        raise ValueError("Hay órdenes de Mungo sin PO#; no se pueden deduplicar con seguridad.")
    return [f"mungo:{value}" for value in values]


def exclude_exported(df: pd.DataFrame, source: str) -> tuple[pd.DataFrame, int]:
    """Devuelve únicamente órdenes que aún no aparecen en el historial."""
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame(), 0
    keys = order_keys(df, source)
    known_rows = (
        get_supabase().table(HISTORY_TABLE).select("order_key")
        .in_("order_key", keys).execute().data or []
    )
    known = {row["order_key"] for row in known_rows}
    mask = [key not in known for key in keys]
    result = df.loc[mask].reset_index(drop=True)
    return result, len(df) - len(result)


def record_exported(df: pd.DataFrame, source: str) -> None:
    """Registra las órdenes al preparar la descarga CSV/Excel."""
    if df is None or df.empty:
        return
    keys = order_keys(df, source)
    rows = [{"order_key": key, "source": source} for key in dict.fromkeys(keys)]
    get_supabase().table(HISTORY_TABLE).upsert(rows, on_conflict="order_key").execute()
