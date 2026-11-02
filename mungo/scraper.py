"""Punto de entrada reservado para la extracción autenticada desde Kova."""

import asyncio
from datetime import date
from io import StringIO

import pandas as pd
from playwright.async_api import async_playwright

import logger as _log
from .transformer import filtrar_por_start_date, normalizar_fecha

logger = _log.get("mungo.scraper")


MUNGO_URL = "https://kova1.mungo.com/KovaMungo/desktopdefault.aspx?ReturnUrl=%2fKovaMungo%2f"
MUNGO_PO_URL = (
    "https://kova1.mungo.com/KovaMungo/Production/Jobs/"
    "JobPOList.aspx?qrefobjtype=JobPO&root=true&"
    "status=Released%7CRejected%7CNew%7CPublished%7CRevised%7CCompleted%7C"
    "Paid%7CBeingFixed%7CConfirmed%7CWorkInProgress"
)
MUNGO_LOGOUT_URL = "https://kova1.mungo.com/KovaMungo/LogOut.aspx"
ORDER_TABLE_SELECTOR = "#ctl00_GridContentJobPOGridJobPODataGrid_ctl00"
ORDER_GRID_SELECTOR = "#ctl00_GridContentJobPOGridJobPODataGrid"

DATE_FILTER_SELECTORS = {
    "released": (
        "#ctl00_GridContent__JobPOGrid__Filters_MinDateReleasedTextBox",
        "#ctl00_GridContent__JobPOGrid__Filters_MaxDateReleasedTextBox",
    ),
    "approved": (
        "#ctl00_GridContent__JobPOGrid__Filters_MinDateApprovedTextBox",
        "#ctl00_GridContent__JobPOGrid__Filters_MaxDateApprovedTextBox",
    ),
    "paid": (
        "#ctl00_GridContent__JobPOGrid__Filters_MinDatePaidTextBox",
        "#ctl00_GridContent__JobPOGrid__Filters_MaxDatePaidTextBox",
    ),
}


class MungoFilterPendingError(RuntimeError):
    """El filtro de fechas del portal todavía no ha sido identificado."""


class MungoAuthenticationError(RuntimeError):
    """Kova rechazó las credenciales configuradas."""


async def _iniciar_sesion(page, username: str, password: str) -> None:
    """Autentica una página de Playwright y valida la respuesta de Kova."""
    await page.goto(MUNGO_URL, wait_until="domcontentloaded", timeout=60_000)
    await page.locator("#SignIn1_username").fill(username)
    await page.locator("#SignIn1_password").fill(password)
    await page.locator("#SignIn1_ButtonSignIn").click()
    await page.wait_for_timeout(3_000)

    login_form_visible = await page.locator("#SignIn1_username").is_visible()
    page_text = await page.locator("body").inner_text()
    if login_form_visible or "Login Failed" in page_text:
        raise MungoAuthenticationError(
            "Kova rechazó el usuario o la contraseña configurados."
        )


async def _probar_conexion_mungo(username: str, password: str) -> None:
    """Inicia sesión en Kova sin consultar ni modificar órdenes."""
    if not username or not password:
        raise MungoAuthenticationError("Faltan las credenciales de Mungo.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = await browser.new_page()
        try:
            await _iniciar_sesion(page, username, password)
        finally:
            await browser.close()


def probar_conexion_mungo(username: str, password: str) -> None:
    """Wrapper síncrono para probar las credenciales desde Streamlit."""
    asyncio.run(_probar_conexion_mungo(username, password))


async def _extraer_ordenes_mungo(
    username: str,
    password: str,
    date_from: date,
    date_to: date,
    date_filter: str,
) -> pd.DataFrame:
    """Extrae la grilla de PO's y aplica el rango solicitado."""
    if date_filter not in {*DATE_FILTER_SELECTORS, "start_date"}:
        raise MungoFilterPendingError(
            "Selecciona Start Date, Released, Approved o Paid."
        )
    if date_from > date_to:
        raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = await browser.new_page()
        logged_in = False
        try:
            await _iniciar_sesion(page, username, password)
            logged_in = True
            await page.goto(MUNGO_PO_URL, wait_until="domcontentloaded", timeout=60_000)
            await page.locator(ORDER_TABLE_SELECTOR).wait_for(state="visible", timeout=60_000)

            if date_filter in DATE_FILTER_SELECTORS:
                from_selector, to_selector = DATE_FILTER_SELECTORS[date_filter]
                await page.locator(from_selector).fill(date_from.strftime("%m/%d/%Y"))
                await page.locator(to_selector).fill(date_to.strftime("%m/%d/%Y"))
                await page.locator(
                    "#ctl00_GridContent__JobPOGrid__Filters_ImageGoFilterButton"
                ).click()
                await page.wait_for_timeout(5_000)
            result = await _leer_todas_las_paginas(page)
            diagnostic_detail = {}
            po_column = next(
                (column for column in result.columns if str(column).strip().casefold() == "po#"),
                None,
            )
            start_date_column = next(
                (column for column in result.columns if str(column).strip().casefold() == "start date"),
                None,
            )
            if po_column is not None and start_date_column is not None:
                target_rows = result.loc[
                    result[po_column].map(lambda value: str(value).strip().removesuffix(".0")) == "50289142",
                    [po_column, start_date_column],
                ]
                diagnostic_detail["po_50289142"] = [
                    {
                        "raw_start_date": str(row[start_date_column]),
                        "normalized_start_date": normalizar_fecha(row[start_date_column]),
                    }
                    for _, row in target_rows.iterrows()
                ]
            diagnostic_detail["start_date_examples"] = (
                [
                    {
                        "raw": str(value),
                        "normalized": normalizar_fecha(value),
                    }
                    for value in result[start_date_column].head(5)
                ]
                if start_date_column is not None else []
            )
            logger.warning(
                "Mungo diagnóstico: filas_leídas=%s columnas=%s filtro=%s desde=%s hasta=%s detalle=%s",
                len(result), list(result.columns), date_filter,
                date_from.isoformat(), date_to.isoformat(), diagnostic_detail,
            )
            if date_filter == "start_date":
                filtered = filtrar_por_start_date(result, date_from, date_to)
                filtered.attrs["mungo_diagnostic"] = {
                    "rows_read": len(result),
                    "columns": list(result.columns),
                    "matching_rows": len(filtered),
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                    **diagnostic_detail,
                }
                logger.warning(
                    "Mungo diagnóstico: filas_coincidentes_Start_Date=%s",
                    len(filtered),
                )
                return filtered
            return result
        finally:
            if logged_in:
                try:
                    await page.goto(MUNGO_LOGOUT_URL, wait_until="domcontentloaded", timeout=15_000)
                except Exception:
                    pass
            await browser.close()


async def _leer_todas_las_paginas(page) -> pd.DataFrame:
    """Lee todas las páginas de la grilla ASP.NET de Purchase Orders."""
    from hashlib import sha1

    rows: list[pd.DataFrame] = []
    seen_pages: set[str] = set()
    visited_page_numbers = {1}
    grid = page.locator(ORDER_GRID_SELECTOR)
    table = page.locator(ORDER_TABLE_SELECTOR)
    await table.wait_for(state="visible", timeout=60_000)

    while True:
        table_html = await table.evaluate("element => element.outerHTML")
        fingerprint = sha1(table_html.encode("utf-8")).hexdigest()
        if fingerprint in seen_pages:
            break
        seen_pages.add(fingerprint)

        frames = pd.read_html(StringIO(table_html), header=0)
        if frames:
            current = frames[0]
            current.columns = [
                str(column).replace("\xa0", " ").strip()
                for column in current.columns
            ]
            rows.append(current)

        # Los grids de WebForms suelen renderizar el paginador como links con
        # href __doPostBack(..., "Page$N"). Buscar el siguiente número evita
        # depender del texto/localización del botón.
        page_links = await grid.locator(
            'a[href*="__doPostBack"][href*="Page$"]'
        ).evaluate_all(
            "els => els.map(el => el.getAttribute('href'))"
        )
        import re

        page_numbers = []
        for href in page_links:
            match = re.search(r"Page\$(\d+)", href or "")
            if match:
                page_numbers.append(int(match.group(1)))
        candidates = [
            number for number in page_numbers
            if number > max(visited_page_numbers) and number not in visited_page_numbers
        ]
        if not candidates:
            break

        target = min(candidates)
        visited_page_numbers.add(target)
        target_link = grid.locator(f'a[href*="Page${target}"]').first
        await target_link.click()
        try:
            await page.wait_for_function(
                "([selector, oldHtml]) => document.querySelector(selector)?.outerHTML !== oldHtml",
                arg=[ORDER_TABLE_SELECTOR, table_html],
                timeout=30_000,
            )
        except Exception:
            # Si el postback no cambió el HTML, el fingerprint detectará el
            # ciclo y terminará sin duplicar las filas.
            pass

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).drop_duplicates().reset_index(drop=True)


def ejecutar_extraccion_mungo(
    username: str,
    password: str,
    date_from: date,
    date_to: date,
    date_filter: str | None = None,
) -> pd.DataFrame:
    """Wrapper síncrono del extractor de Purchase Orders."""
    return asyncio.run(
        _extraer_ordenes_mungo(
            username,
            password,
            date_from,
            date_to,
            date_filter or "",
        )
    )
