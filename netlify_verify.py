"""Verificación de deploy vía API Netlify (no depende de HTTP público; evita falsos 429/404)."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

NETLIFY_API = "https://api.netlify.com/api/v1"
NETLIFY_RE = re.compile(r"https?://([a-z0-9-]+)\.netlify\.app", re.I)
REQUEST_TIMEOUT = 60
MIN_HTML_BYTES = 1000


def _auth() -> dict[str, str]:
    token = os.getenv("NETLIFY_ACCESS_TOKEN")
    if not token:
        raise ValueError("Falta NETLIFY_ACCESS_TOKEN en .env o nombres.env")
    return {"Authorization": f"Bearer {token}"}


def slug_from_url(url: str) -> str | None:
    m = NETLIFY_RE.search(url or "")
    return m.group(1) if m else None


def verify_published(netlify_url: str) -> dict:
    """
    Comprueba por API que el sitio tiene index.html publicado.
    Devuelve dict con ok, slug, size, state, message.
    """
    slug = slug_from_url(netlify_url)
    if not slug:
        return {"ok": False, "message": "URL Netlify inválida"}

    auth = _auth()
    site_id = None
    for page in range(1, 12):
        sites = requests.get(
            f"{NETLIFY_API}/sites",
            headers=auth,
            params={"per_page": 100, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        if sites.status_code == 401:
            return {"ok": False, "message": "Token Netlify inválido o expirado (401)"}
        sites.raise_for_status()
        batch = sites.json()
        if not batch:
            break
        for s in batch:
            if s.get("name") == slug or s.get("subdomain") == slug:
                site_id = s["id"]
                break
        if site_id:
            break

    if not site_id:
        return {
            "ok": False,
            "message": f"Sitio '{slug}' no está en tu cuenta Netlify (clave de otra cuenta?)",
        }

    site = requests.get(
        f"{NETLIFY_API}/sites/{site_id}",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    ).json()
    pub = site.get("published_deploy") or {}
    if pub.get("state") != "ready":
        return {
            "ok": False,
            "slug": slug,
            "state": pub.get("state"),
            "message": f"Deploy publicado no está listo (state={pub.get('state')})",
        }

    dep_id = pub.get("id")
    if not dep_id:
        return {"ok": False, "slug": slug, "message": "Sin deploy publicado (sitio vacío)"}

    meta = requests.get(
        f"{NETLIFY_API}/deploys/{dep_id}/files/index.html",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    )
    if not meta.ok:
        return {"ok": False, "slug": slug, "message": "No hay index.html en el deploy publicado"}

    size = int(meta.json().get("size") or 0)
    if size < MIN_HTML_BYTES:
        return {
            "ok": False,
            "slug": slug,
            "size": size,
            "message": f"index.html demasiado pequeño ({size} bytes)",
        }

    return {
        "ok": True,
        "slug": slug,
        "size": size,
        "state": "ready",
        "ssl_url": (site.get("ssl_url") or "").rstrip("/"),
        "message": "OK",
    }


def check_all_keys() -> dict[str, str]:
    """Prueba rápida de todas las claves del .env."""
    out: dict[str, str] = {}
    token = os.getenv("NETLIFY_ACCESS_TOKEN")
    if not token:
        out["NETLIFY"] = "FALTA"
    else:
        r = requests.get(f"{NETLIFY_API}/user", headers=_auth(), timeout=30)
        out["NETLIFY"] = f"OK ({r.json().get('email', '?')})" if r.ok else f"ERROR {r.status_code}"

    gkey = os.getenv("GOOGLE_PLACES_API_KEY")
    if not gkey:
        out["GOOGLE_PLACES"] = "FALTA"
    else:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": gkey,
                "X-Goog-FieldMask": "places.id",
            },
            json={"textQuery": "pizzeria Barcelona", "pageSize": 1},
            timeout=30,
        )
        out["GOOGLE_PLACES"] = "OK" if r.status_code == 200 else f"ERROR {r.status_code}"

    akey = os.getenv("ANTHROPIC_API_KEY")
    if not akey:
        out["ANTHROPIC"] = "FALTA"
    else:
        try:
            import anthropic

            c = anthropic.Anthropic(api_key=akey)
            c.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=8,
                messages=[{"role": "user", "content": "ok"}],
            )
            out["ANTHROPIC"] = "OK"
        except Exception as e:
            out["ANTHROPIC"] = f"ERROR {e}"[:80]

    return out
