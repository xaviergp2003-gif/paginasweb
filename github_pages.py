"""Publicar cada HTML en su propio repo GitHub Pages → un enlace por cliente."""

from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

API = "https://api.github.com"
REQUEST_TIMEOUT = 60
GITHUB_RE = re.compile(r"https?://[a-z0-9.-]+\.github\.io/", re.I)


def slug_repo(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9._-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s[:100] or "demo-web").strip("-")


def repo_from_folder(folder: Path, client_name: str) -> str:
    if folder.parent.name == "webs" and folder.name:
        return slug_repo(folder.name)
    return slug_repo(client_name)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _api(method, url: str, token: str, **kwargs) -> requests.Response:
    r = method(url, headers=_headers(token), timeout=REQUEST_TIMEOUT, **kwargs)
    if r.status_code >= 400:
        detail = r.text[:500]
        raise RuntimeError(f"GitHub API {r.status_code}: {detail}")
    return r


def _owner(token: str) -> str:
    owner = os.getenv("GITHUB_OWNER", "").strip()
    if owner:
        return owner
    r = _api(requests.get, f"{API}/user", token)
    return r.json()["login"]


def pages_url(owner: str, repo: str) -> str:
    return f"https://{owner.lower()}.github.io/{repo}/"


def url_responds_ok(url: str) -> bool:
    target = url if url.endswith("/") else url + "/"
    try:
        r = requests.get(
            target,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (preview-check)"},
        )
        return r.status_code < 400
    except requests.RequestException:
        return False


def _ensure_repo(token: str, owner: str, repo: str) -> None:
    r = requests.get(
        f"{API}/repos/{owner}/{repo}",
        headers=_headers(token),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 200:
        return
    if r.status_code != 404:
        raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:300]}")
    _api(
        requests.post,
        f"{API}/user/repos",
        token,
        json={"name": repo, "public": True, "auto_init": True},
    )
    logger.info("Repo creado: %s/%s", owner, repo)


def _enable_pages_root(token: str, owner: str, repo: str) -> None:
    r = requests.get(
        f"{API}/repos/{owner}/{repo}/pages",
        headers=_headers(token),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 200:
        src = r.json().get("source") or {}
        if src.get("branch") == "main" and src.get("path") in ("/", None):
            return
    method = requests.post if r.status_code == 404 else requests.put
    _api(
        method,
        f"{API}/repos/{owner}/{repo}/pages",
        token,
        json={"build_type": "legacy", "source": {"branch": "main", "path": "/"}},
    )
    logger.info("Pages activado: %s/%s", owner, repo)


def _file_sha(token: str, owner: str, repo: str, path: str) -> str | None:
    r = requests.get(
        f"{API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(token),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:300]}")
    return r.json().get("sha")


def _upload_file(
    token: str,
    owner: str,
    repo: str,
    path: str,
    content: bytes,
    message: str,
) -> None:
    body: dict = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
    }
    sha = _file_sha(token, owner, repo, path)
    if sha:
        body["sha"] = sha
    _api(
        requests.put,
        f"{API}/repos/{owner}/{repo}/contents/{path}",
        token,
        json=body,
    )


def deploy_github_pages(folder: Path, client_name: str) -> str:
    """Un repo público por HTML → https://usuario.github.io/nombre-repo/"""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "Falta GITHUB_TOKEN en .env / nombres.env\n"
            "Token: https://github.com/settings/tokens (permiso repo)"
        )

    html = folder / "index.html"
    if not html.is_file():
        raise FileNotFoundError(f"No hay index.html en {folder}")

    owner = _owner(token)
    repo = repo_from_folder(folder, client_name)
    _ensure_repo(token, owner, repo)

    _upload_file(token, owner, repo, ".nojekyll", b"", "Pages sin Jekyll")
    _upload_file(
        token,
        owner,
        repo,
        "index.html",
        html.read_bytes(),
        f"Web demo: {client_name}",
    )
    _enable_pages_root(token, owner, repo)

    url = pages_url(owner, repo)
    logger.info("Enlace: %s", url)
    return url


def check_all_keys() -> dict[str, str]:
    """Prueba rápida de claves en .env / nombres.env."""
    out: dict[str, str] = {}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        out["GITHUB"] = "FALTA"
    else:
        r = requests.get(f"{API}/user", headers=_headers(token), timeout=30)
        out["GITHUB"] = f"OK ({r.json().get('login', '?')})" if r.ok else f"ERROR {r.status_code}"

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
