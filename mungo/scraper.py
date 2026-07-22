"""Punto de entrada reservado para la extracción autenticada desde Kova."""

from datetime import date

import pandas as pd


MUNGO_URL = "https://kova1.mungo.com/KovaMungo/desktopdefault.aspx?ReturnUrl=%2fKovaMungo%2f"


class MungoFilterPendingError(RuntimeError):
    """El filtro de fechas del portal todavía no ha sido identificado."""


def ejecutar_extraccion_mungo(
    username: str,
    password: str,
    date_from: date,
    date_to: date,
) -> pd.DataFrame:
    """Contrato del futuro scraper; se activará al confirmar el filtro Kova."""
    raise MungoFilterPendingError(
        "Falta confirmar qué filtro de Kova corresponde a las Purchase Orders."
    )
