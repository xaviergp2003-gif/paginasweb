"""Deploy a Netlify vía file digest (Content-Type HTML correcto)."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NETLIFY_API = "https://api.netlify.com/api/v1"
REQUEST_TIMEOUT = 120
POLL_INTERVAL = 2
POLL_TIMEOUT = 120


def prepare_dist(dist_dir: Path) -> None:
    (dist_dir / "_headers").write_text(
        "/index.html\n  Content-Type: text/html; charset=UTF-8\n\n"
        "/\n  Content-Type: text/html; charset=UTF-8\n",
        encoding="utf-8",
    )
    (dist_dir / "netlify.toml").write_text(
        '[[headers]]\n  for = "/*.html"\n  [headers.values]\n'
        '    Content-Type = "text/html; charset=UTF-8"\n',
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

    prepare_dist(dist_dir)
    if netlify_url:
        site_id = _site_id_from_url(token, netlify_url)
    else:
        site_id = os.getenv("NETLIFY_SITE_ID") or _create_site(token, site_name)

    auth = {"Authorization": f"Bearer {token}"}
    file_map = _collect_files(dist_dir)

    r = requests.post(
        f"{NETLIFY_API}/sites/{site_id}/deploys",
        headers={**auth, "Content-Type": "application/json"},
        json={"files": file_map},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    deploy_id = data["id"]
    sha_to_path = {sha: p for p, sha in file_map.items()}
    data = _wait_for_upload_window(token, site_id, deploy_id, data)

    for sha in data.get("required") or []:
        rel = sha_to_path.get(sha, "").lstrip("/")
        put = requests.put(
            f"{NETLIFY_API}/deploys/{deploy_id}/files/{rel}",
            headers={**auth, "Content-Type": "application/octet-stream"},
            data=(dist_dir / rel).read_bytes(),
            timeout=REQUEST_TIMEOUT,
        )
        put.raise_for_status()

    data = _wait_until_ready(token, site_id, deploy_id, data)
    if data.get("error_message"):
        raise RuntimeError(data["error_message"])

    url = (data.get("ssl_url") or data.get("deploy_ssl_url") or "").rstrip("/")
    if not url:
        raise RuntimeError("Deploy sin URL")
    logger.info("Deploy OK: %s", url)
    return url


def _collect_files(dist_dir: Path) -> dict[str, str]:
    return {
        "/" + p.relative_to(dist_dir).as_posix(): _sha1(p)
        for p in sorted(dist_dir.rglob("*"))
        if p.is_file()
    }


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _wait_for_upload_window(token: str, site_id: str, deploy_id: str, data: dict) -> dict:
    url = f"{NETLIFY_API}/sites/{site_id}/deploys/{deploy_id}"
    auth = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        if data.get("state") in ("prepared", "uploaded", "ready") or data.get("required"):
            return data
        if data.get("state") in ("error", "failed"):
            break
        time.sleep(POLL_INTERVAL)
        data = requests.get(url, headers=auth, timeout=REQUEST_TIMEOUT).json()
    return data


def _wait_until_ready(token: str, site_id: str, deploy_id: str, data: dict) -> dict:
    url = f"{NETLIFY_API}/sites/{site_id}/deploys/{deploy_id}"
    auth = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        if data.get("state") == "ready":
            return data
        if data.get("state") in ("error", "failed"):
            break
        time.sleep(POLL_INTERVAL)
        data = requests.get(url, headers=auth, timeout=REQUEST_TIMEOUT).json()
    return data


def _site_id_from_url(token: str, netlify_url: str) -> str:
    slug = re.search(r"https?://([a-z0-9-]+)\.netlify\.app", netlify_url.lower())
    if not slug:
        raise ValueError(f"URL inválida: {netlify_url}")
    name = slug.group(1)
    auth = {"Authorization": f"Bearer {token}"}
    for page in range(1, 11):
        sites = requests.get(
            f"{NETLIFY_API}/sites",
            headers=auth,
            params={"per_page": 100, "page": page},
            timeout=REQUEST_TIMEOUT,
        ).json()
        if not sites:
            break
        for s in sites:
            if s.get("name") == name:
                return s["id"]
    raise RuntimeError(f"Sitio no encontrado: {name}")


def _create_site(token: str, name: str | None) -> str:
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = re.sub(r"[^a-z0-9-]", "", (name or "demo").lower().replace(" ", "-"))[:50] or "demo"
    for slug in (base, f"{base}-{int(time.time()) % 100000}"):
        r = requests.post(f"{NETLIFY_API}/sites", headers=auth, json={"name": slug}, timeout=REQUEST_TIMEOUT)
        if r.status_code == 422:
            continue
        r.raise_for_status()
        sid = r.json().get("id")
        if sid:
            return sid
    raise RuntimeError("No se pudo crear sitio Netlify")


def _site_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))[:50] or "demo"
