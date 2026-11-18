from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter

from app.core.config import PROJECT_ROOT

updates_router = APIRouter(prefix="/api/v1/system/updates")

_DEFAULT_MANIFEST: dict[str, Any] = {
    "version": "1.1.0",
    "release_tag": "v1.1.0",
    "repo": "aliazizdbab/apex-ai-trading-lab",
    "channel": "stable",
    "published_at": "2026-11-19T00:05:00Z",
    "notes": "APEX AI Trading Lab v1.1.0",
    "platforms": {
        "web": "https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-web-v1.1.0.zip",
        "windows": "https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-windows-v1.1.0.zip",
        "macos": "https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-macos-v1.1.0.tar.gz",
        "android": "https://github.com/aliazizdbab/apex-ai-trading-lab/releases/download/v1.1.0/apex-android-v1.1.0.apk",
    },
}


def _load_manifest() -> dict[str, Any]:
    path = PROJECT_ROOT / "version.json"
    if not path.exists():
        return dict(_DEFAULT_MANIFEST)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**_DEFAULT_MANIFEST, **data}
    except Exception:
        return dict(_DEFAULT_MANIFEST)


def _semver_tuple(ver: str) -> tuple[int, ...]:
    cleaned = ver.strip().lstrip("vV").split("-", 1)[0]
    parts: list[int] = []
    for seg in cleaned.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def _run_git(args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out
    except Exception as exc:
        return False, str(exc)


def _local_commit_short() -> str:
    ok, out = _run_git(["rev-parse", "--short", "HEAD"])
    return out if ok and out else "local"


def _match_platform_assets(assets: list[dict[str, Any]], fallback_platforms: dict[str, str]) -> dict[str, str]:
    out = dict(fallback_platforms)
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        url = str(asset.get("browser_download_url", "")).strip()
        if not url:
            continue
        if "android" in name or name.endswith(".apk"):
            out["android"] = url
        elif "windows" in name or name.endswith(".exe") or name.endswith(".msi"):
            out["windows"] = url
        elif "macos" in name or "darwin" in name or name.endswith(".dmg") or name.endswith(".app.tar.gz") or "macos" in name:
            out["macos"] = url
        elif "web" in name:
            out["web"] = url
    return out


@updates_router.get("/status")
def get_update_status() -> dict[str, Any]:
    manifest = _load_manifest()
    repo = str(manifest["repo"])
    tag = str(manifest["release_tag"])
    return {
        "current_version": str(manifest["version"]),
        "release_tag": tag,
        "repo": repo,
        "channel": str(manifest.get("channel", "stable")),
        "local_commit": _local_commit_short(),
        "auto_check_enabled": True,
        "release_url": f"https://github.com/{repo}/releases/tag/{tag}",
        "repo_url": f"https://github.com/{repo}",
        "platforms": manifest.get("platforms", {}),
    }


@updates_router.post("/check")
def check_github_updates() -> dict[str, Any]:
    manifest = _load_manifest()
    repo = str(manifest["repo"])
    current_version = str(manifest["version"])
    current_tag = str(manifest["release_tag"])
    local_commit = _local_commit_short()
    fallback_platforms = dict(manifest.get("platforms", {}))
    now_iso = datetime.now(timezone.utc).isoformat()

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "APEX-AI-Trading-Lab-Updater/1.0",
    }

    latest_version = current_version
    latest_tag = current_tag
    remote_commit = local_commit
    release_url = f"https://github.com/{repo}/releases/tag/{current_tag}"
    release_notes = str(manifest.get("notes", ""))
    platforms = dict(fallback_platforms)
    ok = True
    error_msg: str | None = None

    try:
        with httpx.Client(timeout=12.0, headers=headers) as client:
            rel_resp = client.get(f"https://api.github.com/repos/{repo}/releases/latest")
            if rel_resp.status_code == 200:
                rel = rel_resp.json()
                latest_tag = str(rel.get("tag_name") or current_tag)
                latest_version = latest_tag.lstrip("vV")
                release_url = str(rel.get("html_url") or release_url)
                release_notes = str(rel.get("body") or release_notes)
                platforms = _match_platform_assets(rel.get("assets") or [], fallback_platforms)
            elif rel_resp.status_code != 404:
                ok = False
                error_msg = f"GitHub Releases returned HTTP {rel_resp.status_code}"

            cmt_resp = client.get(f"https://api.github.com/repos/{repo}/commits/main")
            if cmt_resp.status_code == 200:
                sha = str(cmt_resp.json().get("sha") or "")
                if sha:
                    remote_commit = sha[:7]
    except Exception as exc:
        ok = False
        error_msg = f"Unable to reach GitHub: {exc}"

    ver_newer = _semver_tuple(latest_version) > _semver_tuple(current_version)
    commit_newer = bool(remote_commit and local_commit not in {"local", remote_commit})

    return {
        "ok": ok,
        "error": error_msg,
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "update_available": ver_newer or commit_newer,
        "current_version": current_version,
        "latest_version": latest_version,
        "latest_tag": latest_tag,
        "local_commit": local_commit,
        "remote_commit": remote_commit,
        "release_url": release_url,
        "release_notes": release_notes,
        "platforms": platforms,
        "checked_at": now_iso,
    }


@updates_router.post("/apply")
def apply_github_update() -> dict[str, Any]:
    before_commit = _local_commit_short()
    ok_fetch, out_fetch = _run_git(["fetch", "origin", "main"])
    if not ok_fetch:
        return {
            "ok": False,
            "before_commit": before_commit,
            "after_commit": before_commit,
            "output": out_fetch or "Failed to fetch updates from GitHub origin/main",
        }
    ok_pull, out_pull = _run_git(["pull", "--ff-only", "origin", "main"])
    after_commit = _local_commit_short()
    return {
        "ok": ok_pull,
        "before_commit": before_commit,
        "after_commit": after_commit,
        "output": (out_pull or out_fetch or "Already up to date."),
    }
