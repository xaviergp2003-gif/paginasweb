"""Deploy a Netlify (ZIP + publicación en producción)."""

from __future__ import annotations

import io
import logging
import os
import re
import time
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
for _env in (ROOT / ".env", ROOT / "nombres.env"):
    if _env.is_file():
        load_dotenv(_env)
        break
else:
    load_dotenv()

logger = logging.getLogger(__name__)

NETLIFY_API = "https://api.netlify.com/api/v1"
REQUEST_TIMEOUT = 120
POLL_INTERVAL = 2
POLL_TIMEOUT = 180


def prepare_dist(dist_dir: Path) -> None:
    (dist_dir / "netlify.toml").write_text(
        '[[headers]]\n  for = "/*"\n  [headers.values]\n'
        '    Content-Type = "text/html; charset=UTF-8"\n\n'
        '[[headers]]\n  for = "/index.html"\n  [headers.values]\n'
        '    Content-Type = "text/html; charset=UTF-8"\n\n'
        "[[redirects]]\n"
        '  from = "/*"\n'
        '  to = "/index.html"\n'
        "  status = 200\n",
        encoding="utf-8",
    )


def deploy_dist(
    dist_dir: Path,
    site_name: str | None = None,
    *,
    netlify_url: str | None = None,
) -> str:
    token = os.getenv("NETLIFY_ACCESS_TOKEN")
    if not token:
        raise ValueError("Falta NETLIFY_ACCESS_TOKEN en .env")

    if not (dist_dir / "index.html").is_file():
        raise FileNotFoundError(f"Falta index.html en {dist_dir}")

    prepare_dist(dist_dir)
    if netlify_url:
        site_id = _site_id_from_url(token, netlify_url)
    else:
        site_id = os.getenv("NETLIFY_SITE_ID") or _create_site(token, site_name)

    auth = {"Authorization": f"Bearer {token}"}
    zip_bytes = _make_deploy_zip(dist_dir)

    data = _api(
        requests.post,
        f"{NETLIFY_API}/sites/{site_id}/deploys",
        headers={**auth, "Content-Type": "application/zip"},
        data=zip_bytes,
        timeout=REQUEST_TIMEOUT,
    )
    deploy_id = data["id"]
    data = _wait_until_ready(token, site_id, deploy_id, data)
    if data.get("error_message"):
        raise RuntimeError(data["error_message"])
    if data.get("state") not in ("ready", "published"):
        raise RuntimeError(f"Deploy no terminó correctamente (state={data.get('state')})")

    _publish_deploy(token, site_id, deploy_id, auth)
    url = _canonical_site_url(token, site_id, auth)
    _verify_published_api(url)
    logger.info("Deploy OK: %s", url)
    return url


def _bust_deploy_cache(dist_dir: Path) -> None:
    """Marca única en HTML para que Netlify no reutilice un deploy vacío antiguo."""
    path = dist_dir / "index.html"
    text = path.read_text(encoding="utf-8")
    stamp = f"<!-- deploy:{int(time.time())} -->"
    text = re.sub(r"<!-- deploy:\d+ -->", "", text)
    if "</html>" in text:
        text = text.replace("</html>", f"{stamp}\n</html>", 1)
    else:
        text += f"\n{stamp}\n"
    path.write_text(text, encoding="utf-8")


def _make_deploy_zip(dist_dir: Path) -> bytes:
    _bust_deploy_cache(dist_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("index.html", "netlify.toml"):
            path = dist_dir / name
            if path.is_file():
                zf.write(path, name)
    data = buf.getvalue()
    if not data:
        raise ValueError(f"ZIP vacío en {dist_dir}")
    return data


def _get_deploy(token: str, site_id: str, deploy_id: str) -> dict:
    auth = {"Authorization": f"Bearer {token}"}
    return _api(
        requests.get,
        f"{NETLIFY_API}/sites/{site_id}/deploys/{deploy_id}",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    )


def _wait_until_ready(token: str, site_id: str, deploy_id: str, data: dict) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        state = data.get("state")
        if state in ("ready", "published"):
            return data
        if state in ("error", "failed"):
            raise RuntimeError(data.get("error_message") or f"Deploy falló: {state}")
        time.sleep(POLL_INTERVAL)
        data = _get_deploy(token, site_id, deploy_id)
    raise RuntimeError(f"Timeout esperando deploy listo (state={data.get('state')})")


def _publish_deploy(token: str, site_id: str, deploy_id: str, auth: dict) -> None:
    """Publica el deploy en producción (evita sitios vacíos / preview sin publicar)."""
    r = requests.post(
        f"{NETLIFY_API}/sites/{site_id}/deploys/{deploy_id}/restore",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code not in (200, 201, 204, 422):
        r.raise_for_status()
    time.sleep(2)


def _canonical_site_url(token: str, site_id: str, auth: dict) -> str:
    site = _api(
        requests.get,
        f"{NETLIFY_API}/sites/{site_id}",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    )
    url = (site.get("ssl_url") or site.get("url") or "").rstrip("/")
    if not url:
        pub = site.get("published_deploy") or {}
        url = (pub.get("ssl_url") or pub.get("deploy_ssl_url") or "").rstrip("/")
    if not url:
        raise RuntimeError("No se pudo obtener la URL pública del sitio")
    return url


def _verify_published_api(url: str) -> None:
    """Verifica por API que index.html está publicado (fiable; el HTTP público da 429 si hay muchos deploys)."""
    from netlify_verify import verify_published

    result = verify_published(url)
    if not result.get("ok"):
        raise RuntimeError(result.get("message") or f"Deploy no verificado: {url}")
    logger.info(
        "Verificado API: %s (%s bytes)",
        result.get("slug"),
        result.get("size"),
    )


def _api(method, url: str, **kwargs) -> dict:
    r = method(url, **kwargs)
    if r.status_code == 429:
        time.sleep(35)
        r = method(url, **kwargs)
    r.raise_for_status()
    return r.json()


def _site_id_from_url(token: str, netlify_url: str) -> str:
    slug = re.search(r"https?://([a-z0-9-]+)\.netlify\.app", netlify_url.lower())
    if not slug:
        raise ValueError(f"URL inválida: {netlify_url}")
    name = slug.group(1)
    auth = {"Authorization": f"Bearer {token}"}
    for page in range(1, 11):
        sites = _api(
            requests.get,
            f"{NETLIFY_API}/sites",
            headers=auth,
            params={"per_page": 100, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        if not sites:
            break
        for s in sites:
            if s.get("name") == name or s.get("subdomain") == name:
                return s["id"]
    raise RuntimeError(f"Sitio no encontrado en tu cuenta Netlify: {name}")


def _create_site(token: str, name: str | None) -> str:
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = _site_slug(name)
    for slug in (base, f"{base}-{int(time.time()) % 100000}"):
        r = requests.post(
            f"{NETLIFY_API}/sites",
            headers=auth,
            json={"name": slug},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 429:
            time.sleep(35)
            r = requests.post(
                f"{NETLIFY_API}/sites",
                headers=auth,
                json={"name": slug},
                timeout=REQUEST_TIMEOUT,
            )
        if r.status_code == 422:
            continue
        r.raise_for_status()
        sid = r.json().get("id")
        if sid:
            return sid
    raise RuntimeError("No se pudo crear sitio Netlify")


def _site_slug(name: str | None) -> str:
    import unicodedata

    raw = (name or "demo").lower().strip()
    norm = unicodedata.normalize("NFKD", raw)
    ascii_name = "".join(c for c in norm if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:50]
    return slug or "demo"


def get_site_status(token: str, netlify_url: str) -> dict:
    """Estado de un sitio (útil para diagnóstico)."""
    site_id = _site_id_from_url(token, netlify_url)
    auth = {"Authorization": f"Bearer {token}"}
    site = _api(
        requests.get,
        f"{NETLIFY_API}/sites/{site_id}",
        headers=auth,
        timeout=REQUEST_TIMEOUT,
    )
    pub = site.get("published_deploy") or {}
    return {
        "name": site.get("name"),
        "url": site.get("ssl_url"),
        "published": bool(pub.get("id")),
        "published_state": pub.get("state"),
        "deploy_id": pub.get("id"),
    }
