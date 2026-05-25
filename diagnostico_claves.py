"""
Diagnóstico: claves API + URLs GitHub Pages del Excel.
Uso: python3 diagnostico_claves.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from openpyxl import load_workbook

from github_pages import GITHUB_RE, check_all_keys, url_responds_ok

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "leads_generados.xlsx"


def _load_env() -> None:
    for f in (ROOT / ".env", ROOT / "nombres.env"):
        if f.is_file():
            load_dotenv(f, override=False)


def main() -> None:
    _load_env()
    print("=== CLAVES API ===")
    for k, v in check_all_keys().items():
        print(f"  {k}: {v}")

    if not XLSX.is_file():
        print("\nNo hay Excel.")
        return

    print("\n=== URL DEMO (columna F) ===")
    wb = load_workbook(XLSX)
    ok = fail = sin = 0
    for sheet in wb.sheetnames:
        if sheet == "Enlaces demos":
            continue
        ws = wb[sheet]
        for row in range(2, ws.max_row + 1):
            name = ws.cell(row, 2).value
            if not name:
                continue
            url = str(ws.cell(row, 6).value or "").strip()
            if not url:
                sin += 1
                print(f"  — {sheet} r{row} {name}: sin URL")
                continue
            if not GITHUB_RE.search(url):
                fail += 1
                print(f"  ? {name}: {url[:70]}")
                continue
            if url_responds_ok(url):
                ok += 1
                print(f"  ✓ {name}")
            else:
                fail += 1
                print(f"  ✗ {name} (aún propagando o error): {url}")

    print(f"\nResumen: {ok} OK, {fail} problema, {sin} sin URL")


if __name__ == "__main__":
    main()
