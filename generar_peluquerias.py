"""
Peluquerías sin web en Sitges → landing → GitHub Pages → hoja Excel.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openpyxl import load_workbook

from content_ai import generate_copy_peluqueria
from github_pages import deploy_github_pages
from scraper import PlaceLead, search_leads
from templater import (
    DIST_DIR,
    has_whatsapp,
    render_peluqueria_landing,
    whatsapp_href,
    whatsapp_message_info,
)
from webs_storage import save_client_web, webs_path_for_excel

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "leads_generados.xlsx"
SHEET_PELU = "Peluquerías Sitges"
HEADERS = [
    "Zona / Búsqueda",
    "Empresa",
    "Teléfono",
    "Dirección",
    "Ciudad",
    "URL Web (GitHub)",
    "Enlace WhatsApp",
    "HTML local",
    "Generado",
]

QUERIES = [
    "Peluquerías en Sitges",
    "Peluquería en Sitges",
    "Salón de belleza Sitges",
    "Peluquería unisex Sitges",
    "Barbería Sitges",
]

MAX_LEADS = 10

SKIP_NAME = re.compile(
    r"restaurante|pizzer|hotel|farmacia|supermerc|gimnasio|dentista|veterinar|"
    r"abogad|inmobiliar|taller|mecánic|ferreter",
    re.I,
)


def _is_hair_salon(lead: PlaceLead) -> bool:
    text = f"{lead.name} {lead.category}".lower()
    if SKIP_NAME.search(text):
        return False
    return any(
        w in text
        for w in (
            "peluquer", "peluquería", "hair", "salon", "salón", "barber",
            "barbershop", "estilista", "beauty", "belleza", "coiff",
        )
    )


def _append_sheet(rows: list[list]) -> None:
    wb = load_workbook(XLSX)
    if SHEET_PELU in wb.sheetnames:
        ws = wb[SHEET_PELU]
        start = ws.max_row + 1
    else:
        ws = wb.create_sheet(SHEET_PELU)
        ws.append(HEADERS)
        start = 2
    for i, row in enumerate(rows):
        for c, val in enumerate(row[:9], 1):
            ws.cell(start + i - 1, c, val)
    if "Pizzerías" not in wb.sheetnames and wb.sheetnames:
        wb[wb.sheetnames[0]].title = "Pizzerías"
    wb.save(XLSX)


def main() -> None:
    log.info("=== Peluquerías Sitges (sin web) ===")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    results: list[list] = []
    deploy_i = 0

    for query in QUERIES:
        if len(results) >= MAX_LEADS:
            break
        log.info("--- %s ---", query)
        try:
            found = search_leads(query, max_results=15)
        except Exception as e:
            log.error("Scraper: %s", e)
            continue

        for lead in found:
            if len(results) >= MAX_LEADS:
                break
            key = lead.name.lower().strip()
            if key in seen or lead.place_id in seen:
                continue
            if not _is_hair_salon(lead):
                log.info("  omitido (no peluquería): %s", lead.name)
                continue
            seen.add(key)
            seen.add(lead.place_id)

            log.info("→ %s", lead.name)
            try:
                copy = generate_copy_peluqueria(
                    lead.name, lead.reviews, city=lead.city or "Sitges"
                )
            except Exception as e:
                log.error("  IA: %s", e)
                continue

            deploy_i += 1
            out = DIST_DIR / f"pelu-sitges-{deploy_i}"
            try:
                render_peluqueria_landing(lead=lead, copy=copy, output_dir=out)
            except Exception as e:
                log.error("  HTML: %s", e)
                continue

            url = ""
            webs_html = ""
            try:
                saved = save_client_web(lead.name, out)
                url = deploy_github_pages(saved.parent, lead.name)
                webs_html = webs_path_for_excel(saved)
            except Exception as e:
                log.error("  GitHub: %s", e)
                webs_html = str(out / "index.html")

            wa = (
                whatsapp_href(lead.phone, whatsapp_message_info(lead.name))
                if has_whatsapp(lead.phone)
                else ""
            )
            results.append([
                query,
                lead.name,
                lead.phone or "—",
                lead.address,
                lead.city or "Sitges",
                url.rstrip("/") if url else "",
                wa,
                webs_html,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ])
            log.info("  ✓ %s", url or webs_html)

    if results:
        _append_sheet(results)
    log.info("=== FIN: %d peluquerías ===", len(results))


if __name__ == "__main__":
    main()
