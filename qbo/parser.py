"""
Parser del Jobber Visits Report para generar facturas en QBO.
"""
import math
import re
import pandas as pd
from datetime import datetime

from config import SHINE_CLIENT_MAP


def _normalize_builder(name: str) -> str:
    if not name:
        return name
    n = re.sub(r"\s+", " ", name).strip()
    for pattern, replacement in SHINE_CLIENT_MAP.items():
        if re.match(pattern, n, flags=re.IGNORECASE):
            return replacement
    return n


def _col_lookup(df: pd.DataFrame, *candidates: str) -> str | None:
    """Busca primera columna del df que matchee (case/space-insensitive) uno de candidates."""
    norm_cols = {re.sub(r"\s+", "", str(c)).lower(): c for c in df.columns}
    for cand in candidates:
        key = re.sub(r"\s+", "", cand).lower()
        if key in norm_cols:
            return norm_cols[key]
    return None


def _get(row, col: str | None, default=""):
    if not col:
        return default
    val = row.get(col, default)
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


def _split_street(s: str) -> tuple[str, str]:
    """'256 Macintosh Drive King' → ('256 Macintosh', 'Drive King').
    Regla: primeros 2 tokens = street, resto = city.
    """
    s = (s or "").strip()
    if not s:
        return "", ""
    tokens = s.split()
    if len(tokens) <= 2:
        return s, ""
    return " ".join(tokens[:2]), " ".join(tokens[2:])


def _to_amount(val) -> float | None:
    """Convierte cualquier formato razonable de monto a float. None si no parseable."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def parse_visits_csv(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """
    Filtra y convierte filas del Visits Report en dicts listos para create_invoice.

    Returns (parsed_rows, skipped_rows).
    skipped_rows: list of {title, reason} for debugging.

    EPO: si ORDER NUMBER == 'EPO', se permite y order_number = 'EPO'.
    Acepta montos negativos (créditos/devoluciones).
    """
    col_title  = _col_lookup(df, "Visit title", "VisitTitle", "Title")
    col_order  = _col_lookup(df, "ORDER NUMBER", "OrderNumber", "Order Number", "Order #")
    col_amount = _col_lookup(df, "One-off job ($)", "One-off job", "Amount", "Total")
    col_date   = _col_lookup(df, "Date", "Visit Date", "Scheduled Date")
    col_assign = _col_lookup(df, "Assigned to", "Assigned", "Team")
    col_street = _col_lookup(df, "Service street", "Property street", "Street")
    col_city   = _col_lookup(df, "Service city", "Property city", "City")
    col_state  = _col_lookup(df, "Service province", "Service state", "State", "Province")
    col_zip    = _col_lookup(df, "Service ZIP", "Service zip", "ZIP", "Postal")

    rows: list[dict] = []
    skipped: list[dict] = []

    for _, row in df.iterrows():
        title = ""
        try:
            title = str(_get(row, col_title, "")).strip()
            order_num_col = str(_get(row, col_order, "")).strip().upper()
            is_epo = order_num_col == "EPO"

            amount = _to_amount(_get(row, col_amount, None))
            if amount is None:
                if is_epo:
                    amount = 0.0
                else:
                    skipped.append({"title": title, "reason": f"monto inválido ({_get(row, col_amount, '')})"})
                    continue
            if not is_epo and amount <= 0:
                skipped.append({"title": title, "reason": f"monto ≤ 0 ({amount})"})
                continue

            parsed = _parse_visit_title(title)
            if not parsed:
                skipped.append({"title": title, "reason": "título no parseable"})
                continue

            date_raw = str(_get(row, col_date, "")).strip()
            txn_date = _parse_date(date_raw)
            if not txn_date:
                skipped.append({"title": title, "reason": f"fecha no parseable ({date_raw})"})
                continue

            order_number = parsed["order_number"]
            if is_epo:
                order_number = "EPO"
            elif not order_number and order_num_col not in ("", "INVOICE"):
                order_number = order_num_col

            assigned = str(_get(row, col_assign, "")).strip()
            cleaner  = assigned.split()[0].upper() if assigned else ""

            raw_street = str(_get(row, col_street, "")).strip()
            raw_city   = str(_get(row, col_city, "")).strip()
            raw_state  = str(_get(row, col_state, "")).strip()
            raw_zip    = str(_get(row, col_zip, "")).strip()
            street, city = _split_street(raw_street)
            # Si Service city != state (no es duplicado del state), preferir Service city
            if raw_city and raw_city.upper() != raw_state.upper():
                city = raw_city

            rows.append({
                "title":        title,
                "builder":      parsed["builder"],
                "service_type": parsed["service_type"],
                "community":    parsed["community"],
                "lot":          parsed["lot"],
                "order_number": order_number,
                "amount":       amount,
                "txn_date":     txn_date,
                "cleaner":      cleaner,
                "address": {
                    "street":  street,
                    "city":    city,
                    "state":   raw_state,
                    "zip":     raw_zip,
                    "country": "United States" if raw_state else "",
                },
            })
        except Exception as ex:
            skipped.append({"title": title, "reason": f"error inesperado: {ex}"})
            continue

    return rows, skipped


def _parse_visit_title(title: str) -> dict | None:
    """
    Parse formatos:
      'Builder - SERVICE TYPE / LOT xxx / Community / order-number'
      'Builder - SERVICE TYPE / Community'   (sin lot)
      'Builder / SERVICE TYPE / ...'         (fallback sin guión)
    """
    if not title:
        return None

    segments = [s.strip() for s in title.split(" / ")]
    first = segments[0]
    parts = [p.strip() for p in first.split(" - ")]

    if len(parts) >= 2:
        service_type = parts[-1]
        builder      = _normalize_builder(" - ".join(parts[:-1]))
        rest = segments[1:]
    elif len(segments) >= 2:
        builder      = _normalize_builder(segments[0])
        service_type = segments[1]
        rest = segments[2:]
    else:
        return None

    lot = ""
    if rest and rest[0].upper().startswith("LOT"):
        lot_parts = rest[0].split()
        if len(lot_parts) >= 2:
            lot = lot_parts[1]

    community    = ""
    order_number = ""

    if len(rest) >= 3:
        community    = rest[-2]
        order_number = rest[-1]
    elif len(rest) == 2:
        community = rest[-1]
    elif len(rest) == 1:
        if not rest[0].upper().startswith("LOT"):
            community = rest[0]

    return {
        "builder":      builder,
        "service_type": service_type,
        "community":    community,
        "lot":          lot,
        "order_number": order_number,
    }


_DATE_FORMATS = [
    "%b %d, %Y", "%B %d, %Y",
    "%Y-%m-%d",
    "%m/%d/%Y", "%m/%d/%y",
    "%d/%m/%Y",
]


def _parse_date(date_str: str) -> str | None:
    """Convierte fecha en varios formatos → 'YYYY-MM-DD'. None si no parseable."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        ts = pd.to_datetime(date_str, errors="coerce")
        if pd.notna(ts):
            return ts.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None
