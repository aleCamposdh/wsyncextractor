"""Historial persistente de órdenes incluidas en archivos de exportación."""

from __future__ import annotations

import re

import pandas as pd

from database import get_supabase


HISTORY_TABLE = "worksync_exported_orders"
KEY_COLUMN = "Job title Final"  # Activity / LOT / Community / PO#
EXPORTED_AT_COLUMN = "Exported At"
_BATCH_SIZE = 200


def _key_part(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def order_keys(df: pd.DataFrame, source: str = "Mungo Homes") -> list[str]:
    """Llave estable por orden: actividad + lote + comunidad + PO# (título del job)."""
    if source != "Mungo Homes":
        raise ValueError("El historial de exportación solo aplica a Mungo Homes.")
    if KEY_COLUMN not in df.columns:
        raise ValueError(f"No se encontró la columna {KEY_COLUMN} para detectar duplicados.")
    values = df[KEY_COLUMN].map(_key_part)
    if values.eq("").any():
        raise ValueError("Hay órdenes de Mungo sin título; no se pueden deduplicar con seguridad.")
    return [f"mungo:{value}" for value in values]


def _fetch_known(keys: list[str]) -> dict[str, str]:
    """Devuelve {order_key: exported_at} de las llaves ya registradas (por lotes)."""
    known: dict[str, str] = {}
    client = get_supabase()
    unique = list(dict.fromkeys(keys))
    for i in range(0, len(unique), _BATCH_SIZE):
        batch = unique[i:i + _BATCH_SIZE]
        rows = (
            client.table(HISTORY_TABLE).select("order_key, exported_at")
            .in_("order_key", batch).execute().data or []
        )
        known.update({row["order_key"]: row.get("exported_at") or "" for row in rows})
    return known


def split_exported(
    df: pd.DataFrame, source: str = "Mungo Homes"
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Separa (nuevas, duplicadas, llaves_de_las_nuevas).

    Las duplicadas incluyen la columna 'Exported At' con la fecha de su primera exportación.
    """
    if df is None or df.empty:
        empty = df.copy() if df is not None else pd.DataFrame()
        return empty, empty.copy(), []
    keys = order_keys(df, source)
    known = _fetch_known(keys)
    is_dup = pd.Series([key in known for key in keys], index=df.index)

    new_df = df.loc[~is_dup].reset_index(drop=True)
    new_keys = [key for key, dup in zip(keys, is_dup) if not dup]

    dup_df = df.loc[is_dup].copy()
    dup_df[EXPORTED_AT_COLUMN] = [
        _format_date(known[key]) for key, dup in zip(keys, is_dup) if dup
    ]
    return new_df, dup_df.reset_index(drop=True), new_keys


def _format_date(value: str) -> str:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return "" if pd.isna(parsed) else parsed.strftime("%m/%d/%Y %H:%M")


def record_exported(keys: list[str] | None, source: str = "Mungo Homes") -> None:
    """Registra las llaves (calculadas al extraer) al descargar el CSV/Excel."""
    if not keys:
        return
    rows = [{"order_key": key, "source": source} for key in dict.fromkeys(keys)]
    client = get_supabase()
    for i in range(0, len(rows), _BATCH_SIZE):
        client.table(HISTORY_TABLE).upsert(
            rows[i:i + _BATCH_SIZE], on_conflict="order_key"
        ).execute()
