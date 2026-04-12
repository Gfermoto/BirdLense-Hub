"""Heimdall connectivity and metadata probe helpers."""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests


def _extract_title(html: str) -> str | None:
    if not html:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title or None


def probe_heimdall(base_url: str, timeout_sec: float = 4.0) -> dict:
    """Probe Heimdall URL from backend host and return lightweight diagnostics."""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return {
            "configured": False,
            "reachable": False,
            "error": "empty_url",
        }
    t0 = time.monotonic()
    out = {
        "configured": True,
        "reachable": False,
        "http_status": None,
        "latency_ms": None,
        "title": None,
        "version": None,
        "error": None,
    }
    try:
        # Try health endpoint first (some deployments expose it as JSON).
        health_url = urljoin(base + "/", "api/health")
        r = requests.get(health_url, timeout=timeout_sec)
        out["http_status"] = r.status_code
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        if r.ok:
            out["reachable"] = True
            try:
                j = r.json() or {}
                if isinstance(j, dict):
                    out["version"] = j.get("version") or j.get("app_version")
            except ValueError:
                pass
        # Even when /api/health is missing, root page can still be alive.
        if not out["reachable"]:
            r2 = requests.get(base, timeout=timeout_sec)
            out["http_status"] = r2.status_code
            out["latency_ms"] = int((time.monotonic() - t0) * 1000)
            if r2.ok:
                out["reachable"] = True
                out["title"] = _extract_title(r2.text or "")
        elif out.get("title") is None:
            # Optionally fetch title from root page.
            try:
                r3 = requests.get(base, timeout=timeout_sec)
                if r3.ok:
                    out["title"] = _extract_title(r3.text or "")
            except requests.RequestException:
                pass
    except requests.RequestException as e:
        out["latency_ms"] = int((time.monotonic() - t0) * 1000)
        out["error"] = f"{type(e).__name__}: {e}"
    return out
