"""Punto de entrada reservado para la extracción autenticada desde Kova."""

import asyncio
from datetime import date
from io import StringIO

import pandas as pd
from playwright.async_api import async_playwright

import logger as _log
from .transformer import filtrar_por_start_date

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
            logger.info("Mungo: filas leídas de Kova=%s", len(result))
            if date_filter == "start_date":
                filtered = filtrar_por_start_date(result, date_from, date_to)
                logger.info("Mungo: filas coincidentes con Start Date=%s", len(filtered))
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
    import re

    rows: list[pd.DataFrame] = []
    seen_pages: set[str] = set()
    visited_page_numbers = {1}
    table = page.locator(ORDER_TABLE_SELECTOR)
    await table.wait_for(state="visible", timeout=60_000)

    # Kova limita inicialmente la grilla a 100 filas. El total está impreso
    # debajo de la tabla; el textbox NumberOfRows permite pedirlas en una carga.
    body_text = await page.locator("body").inner_text()
    total_match = re.search(
        r"Showing\s+\d+\s*\.\.\.\s*\d+\s+of\s+([\d,]+)\s+Purchase Orders",
        body_text,
        re.IGNORECASE,
    )
    rows_input = page.locator("#ctl00_GridContent__JobPOGrid_NumberOfRows")
    if total_match and await rows_input.count():
        total_orders = int(total_match.group(1).replace(",", ""))
        try:
            current_limit = int(await rows_input.input_value())
        except ValueError:
            current_limit = 0
        logger.info(
            "Mungo Rows on Page: total=%s límite_actual=%s",
            total_orders, current_limit,
        )
        if total_orders > current_limit:
            old_html = await table.evaluate("element => element.outerHTML")
            await rows_input.fill(str(total_orders))
            # El textbox actualiza la grilla al confirmar con Enter.
            await rows_input.press("Enter")
            try:
                await page.wait_for_function(
                    "([selector, oldHtml]) => document.querySelector(selector)?.outerHTML !== oldHtml",
                    arg=[ORDER_TABLE_SELECTOR, old_html],
                    timeout=30_000,
                )
                await table.wait_for(state="visible", timeout=30_000)
            except Exception as error:
                logger.warning(
                    "Mungo Rows on Page: postback no confirmado (%s)",
                    type(error).__name__,
                )
        updated_text = await page.locator("body").inner_text()
        updated_match = re.search(
            r"Showing\s+\d+\s*\.\.\.\s*\d+\s+of\s+([\d,]+)\s+Purchase Orders",
            updated_text,
            re.IGNORECASE,
        )
        logger.info(
            "Mungo Rows on Page: valor_final=%s resumen=%s",
            await rows_input.input_value(),
            updated_match.group(0) if updated_match else "no localizado",
        )
    else:
        logger.warning(
            "Mungo Rows on Page: total o textbox no localizado; total_match=%s input_count=%s",
            total_match.group(0) if total_match else None,
            await rows_input.count(),
        )

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
        page_links = await page.locator(
            'a[href*="Page$"]'
        ).evaluate_all(
            "els => els.map(el => el.getAttribute('href'))"
        )
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
            next_link = page.locator('a[href*="Page$Next"]').first
            if await next_link.count() == 0:
                break
            await next_link.click()
        else:
            target = min(candidates)
            visited_page_numbers.add(target)
            target_link = page.locator(f'a[href*="Page${target}"]').first
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
