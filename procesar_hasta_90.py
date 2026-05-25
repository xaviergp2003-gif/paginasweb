"""
Procesa leads en orden: GitHub Pages + carpeta webs/ + negrita en Excel.
Hasta 90 completados (reanudable).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.hyperlink import Hyperlink

from github_pages import GITHUB_RE, deploy_github_pages
from webs_storage import save_client_web, webs_path_for_excel

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "leads_generados.xlsx"
STATE_FILE = ROOT / ".proceso_lote.json"
DIST_DIR = ROOT / "dist"

BATCH_SIZE = 10
META_TOTAL = 90
DIST_PAT = re.compile(r"(redeploy-\d+|lead-new-\d+|pelu-sitges-\d+|lead-\d+)", re.I)

SHEETS_ORDEN = ["Pizzerías", "Peluquerías Sitges"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _load_env() -> None:
    for f in (ROOT / ".env", ROOT / "nombres.env"):
        if f.is_file():
            load_dotenv(f, override=False)


def _is_header_row(ws, row: int, sheet: str) -> bool:
    v = ws.cell(row, 1).value
    if sheet == "Pizzerías" and row == 1:
        return str(v or "").startswith("Zona")
    return False


def _row_done(ws, row: int) -> bool:
    html = str(ws.cell(row, 8).value or "")
    url = str(ws.cell(row, 6).value or "")
    if "webs/" not in html or not GITHUB_RE.search(url):
        return False
    font = ws.cell(row, 2).font
    return bool(font and font.bold)


def _resolve_dist(html_cell: str | None, sheet: str, row: int) -> Path | None:
    s = str(html_cell or "")
    m = DIST_PAT.search(s)
    if m:
        d = DIST_DIR / m.group(1)
        if (d / "index.html").is_file():
            return d

    if sheet == "Pizzerías" and row >= 2:
        if row <= 13:
            cand = DIST_DIR / f"redeploy-{row - 1}"
        else:
            cand = DIST_DIR / f"lead-new-{row - 13}"
        if (cand / "index.html").is_file():
            return cand

    if sheet == "Peluquerías Sitges":
        idx = max(1, row if row > 2 else 1)
        for name in (f"pelu-sitges-{idx}", f"pelu-sitges-{row}"):
            cand = DIST_DIR / name
            if (cand / "index.html").is_file():
                return cand

    return None


def _set_url_cell(ws, row: int, url: str) -> None:
    u = url.rstrip("/")
    cell = ws.cell(row, 6, u)
    cell.hyperlink = Hyperlink(ref=cell.coordinate, target=u, display=u)
    cell.font = Font(bold=True, underline="single", color="0563C1")


def _bold_row(ws, row: int) -> None:
    bold = Font(bold=True)
    for col in range(1, 10):
        ws.cell(row, col).font = bold


def _unbold_row(ws, row: int) -> None:
    normal = Font(bold=False)
    for col in range(1, 10):
        ws.cell(row, col).font = normal


def _collect_queue(wb) -> list[dict]:
    items: list[dict] = []
    seen_names: set[str] = set()
    for sheet in SHEETS_ORDEN:
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        for row in range(1, ws.max_row + 1):
            if _is_header_row(ws, row, sheet):
                continue
            name = str(ws.cell(row, 2).value or "").strip()
            if not name:
                continue
            key = f"{sheet}:{name.lower()}"
            if key in seen_names:
                continue
            seen_names.add(key)
            if _row_done(ws, row):
                continue
            dist = _resolve_dist(ws.cell(row, 8).value, sheet, row)
            if not dist:
                p = ROOT / str(ws.cell(row, 8).value or "")
                if p.is_file():
                    dist = p.parent
                elif (p / "index.html").is_file():
                    dist = p
            if not dist or not (dist / "index.html").is_file():
                log.warning("Sin HTML local: %s (%s fila %d)", name, sheet, row)
                continue
            items.append({
                "sheet": sheet,
                "row": row,
                "name": name,
                "dist": str(dist),
                "html_prev": ws.cell(row, 8).value,
            })
    return items


def _load_state() -> set[str]:
    if not STATE_FILE.is_file():
        return set()
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return set(data.get("done_keys", []))


def _save_state(done_keys: set[str], completed: int) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "done_keys": sorted(done_keys),
                "completed": completed,
                "updated": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _process_one(wb, item: dict) -> bool:
    ws = wb[item["sheet"]]
    row = item["row"]
    dist = Path(item["dist"])
    name = item["name"]

    log.info("→ [%s] %s", item["sheet"], name)
    try:
        webs_html = save_client_web(name, dist, existing_html=item.get("html_prev"))
        new_url = deploy_github_pages(webs_html.parent, name)
        _set_url_cell(ws, row, new_url)
        ws.cell(row, 8, webs_path_for_excel(webs_html))
        ws.cell(row, 9, datetime.now().strftime("%Y-%m-%d %H:%M"))
        _bold_row(ws, row)
        log.info("  ✓ %s | %s", new_url, webs_html.parent.name)
        return True
    except Exception as e:
        log.error("  ✗ %s: %s", name, e)
        _unbold_row(ws, row)
        return False


def _generate_more(needed: int) -> None:
    if needed <= 0:
        return
    log.info("Faltan %d: lanzando ampliar_leads…", needed)
    import ampliar_leads_pizzerias as amp

    amp.MAX_NUEVOS = min(needed, 53)
    amp.main()


def main() -> None:
    _load_env()
    if not XLSX.is_file():
        log.error("No existe %s", XLSX)
        sys.exit(1)

    wb = load_workbook(XLSX)
    done_keys = _load_state()
    queue = _collect_queue(wb)
    queue = [q for q in queue if f"{q['sheet']}:{q['row']}" not in done_keys]

    already_bold = sum(
        1
        for sheet in SHEETS_ORDEN
        if sheet in wb.sheetnames
        for row in range(1, wb[sheet].max_row + 1)
        if not _is_header_row(wb[sheet], row, sheet)
        and _row_done(wb[sheet], row)
    )
    log.info(
        "Cola: %d pendientes | Completados: %d | Meta: %d",
        len(queue),
        already_bold,
        META_TOTAL,
    )

    completed = already_bold
    batch_num = 0

    while completed < META_TOTAL:
        if not queue and completed < META_TOTAL:
            falta = META_TOTAL - completed
            _generate_more(falta)
            wb = load_workbook(XLSX)
            queue = _collect_queue(wb)
            queue = [q for q in queue if f"{q['sheet']}:{q['row']}" not in done_keys]
            if not queue:
                log.error("No hay más leads para procesar.")
                break

        if not queue:
            break

        batch = queue[:BATCH_SIZE]
        queue = queue[BATCH_SIZE:]
        batch_num += 1
        log.info("--- Lote %d (%d leads) ---", batch_num, len(batch))

        for i, item in enumerate(batch):
            if completed >= META_TOTAL:
                break
            key = f"{item['sheet']}:{item['row']}"
            if _process_one(wb, item):
                done_keys.add(key)
                completed += 1
            wb.save(XLSX)
            _save_state(done_keys, completed)

        log.info("Progreso: %d / %d", completed, META_TOTAL)

        if completed >= META_TOTAL or not queue:
            break

    wb.save(XLSX)
    _save_state(done_keys, completed)
    log.info("=== FIN: %d / %d ===", completed, META_TOTAL)


if __name__ == "__main__":
    main()
