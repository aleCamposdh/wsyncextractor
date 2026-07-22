"""Punto de entrada reservado para la extracción autenticada desde Kova."""

import asyncio
from datetime import date
from io import StringIO

import pandas as pd
from playwright.async_api import async_playwright

from .transformer import filtrar_por_start_date


MUNGO_URL = "https://kova1.mungo.com/KovaMungo/desktopdefault.aspx?ReturnUrl=%2fKovaMungo%2f"
MUNGO_PO_URL = (
    "https://kova1.mungo.com/KovaMungo/Production/Jobs/"
    "JobPOList.aspx?qrefobjtype=JobPO&root=true&status=all"
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
            table = page.locator(ORDER_TABLE_SELECTOR)
            await table.wait_for(state="visible", timeout=60_000)

            table_html = await table.evaluate("element => element.outerHTML")
            frames = pd.read_html(StringIO(table_html), header=0)
            if not frames:
                return pd.DataFrame()
            result = frames[0]
            result.columns = [
                str(column).replace("\xa0", " ").strip()
                for column in result.columns
            ]
            if date_filter == "start_date":
                return filtrar_por_start_date(result, date_from, date_to)
            return result
        finally:
            if logged_in:
                try:
                    await page.goto(MUNGO_LOGOUT_URL, wait_until="domcontentloaded", timeout=15_000)
                except Exception:
                    pass
            await browser.close()


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
