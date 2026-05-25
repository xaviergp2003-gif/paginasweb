"""Copia el HTML del cliente a webs/{nombre}/ para archivo local."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from templater import clean_name

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
WEBS_DIR = ROOT / "webs"


def client_slug(name: str) -> str:
    """Slug legible para carpeta (mantiene acentos, como webs/casa-escarré-gavá-2)."""
    n = clean_name(name).lower().strip()
    n = re.sub(r"[^\w\sáéíóúüñ-]", "", n, flags=re.UNICODE)
    n = re.sub(r"[\s_]+", "-", n)
    n = re.sub(r"-+", "-", n).strip("-")
    return (n[:60] or "cliente")


def resolve_webs_dir(client_name: str, existing_html: str | Path | None = None) -> Path:
    """Carpeta webs del cliente: reutiliza ruta del Excel o crea slug único."""
    if existing_html:
        p = Path(str(existing_html))
        if not p.is_absolute():
            p = ROOT / p
        try:
            p.resolve().relative_to(WEBS_DIR.resolve())
            return p.parent if p.name == "index.html" else p
        except ValueError:
            pass

    base = client_slug(client_name)
    direct = WEBS_DIR / base
    if not direct.exists():
        return direct
    for i in range(2, 100):
        candidate = WEBS_DIR / f"{base}-{i}"
        if not candidate.exists():
            return candidate
    return WEBS_DIR / f"{base}-99"


def save_client_web(
    client_name: str,
    html_source: Path,
    *,
    existing_html: str | Path | None = None,
) -> Path:
    """
    Guarda index.html en webs/{cliente}/.
    html_source puede ser el .html o la carpeta dist con index.html dentro.
    """
    src = Path(html_source)
    if src.is_dir():
        src = src / "index.html"
    if not src.is_file():
        raise FileNotFoundError(f"No hay HTML en {html_source}")

    dest_dir = resolve_webs_dir(client_name, existing_html)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "index.html"
    shutil.copy2(src, dest)
    logger.info("Web cliente: %s", dest)
    return dest.resolve()


def webs_path_for_excel(path: Path) -> str:
    """Ruta relativa al proyecto para la columna HTML local del Excel."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)
