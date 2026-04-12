"""Telegram proxy refresh helpers used by UI and notification fallback."""

from __future__ import annotations

import time
from statistics import median
from urllib.request import urlopen

import requests

from app_config.app_config import app_config

PROXY_LIST_URLS = (
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks5.txt",
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/socks5.txt",
)


def _fetch_proxy_lines(url: str) -> list[str]:
    with urlopen(url, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="ignore")
    return [line.strip() for line in raw.splitlines() if line.strip() and ":" in line]


def _probe_proxy(
    proxy: str,
    *,
    bot_path: str,
    max_time: int,
) -> tuple[bool, float, str]:
    proxy_url = f"socks5h://{proxy}"
    t0 = time.monotonic()
    try:
        response = requests.get(
            f"https://api.telegram.org/{bot_path}",
            timeout=max_time,
            proxies={"http": proxy_url, "https": proxy_url},
        )
        elapsed = time.monotonic() - t0
        return response.status_code in (401, 404), elapsed, str(response.status_code)
    except Exception:
        elapsed = time.monotonic() - t0
        return False, elapsed, "ERR"


def refresh_telegram_proxy(
    *,
    top_n: int = 40,
    max_time: int = 12,
    bot_path: str = "botINVALID/getMe",
) -> dict:
    """Pick the fastest working SOCKS5 proxy and persist it in app_config."""
    candidates: list[str] = []
    seen: set[str] = set()
    for url in PROXY_LIST_URLS:
        for line in _fetch_proxy_lines(url):
            if line not in seen:
                seen.add(line)
                candidates.append(line)

    probes = candidates[: max(1, int(top_n or 40))]
    results = []
    for candidate in probes:
        ok, elapsed, code = _probe_proxy(
            candidate,
            bot_path=bot_path,
            max_time=max_time,
        )
        if ok:
            results.append((elapsed, candidate, code))

    if not results:
        raise RuntimeError("No working SOCKS5 proxy found for Telegram API")

    results.sort(key=lambda item: item[0])
    best_latency, best_proxy, best_code = results[0]
    best_url = f"socks5h://{best_proxy}"

    current_type = (app_config.get("notifications.telegram_proxy_type") or "").strip()
    current_url = (app_config.get("notifications.telegram_proxy_url") or "").strip()
    changed = current_type != "socks_http" or current_url != best_url

    app_config.set("notifications.telegram_proxy_type", "socks_http")
    app_config.set("notifications.telegram_proxy_url", best_url)
    if changed:
        app_config.save()

    return {
        "checked": len(probes),
        "working": len(results),
        "best_proxy": best_url,
        "best_code": best_code,
        "best_latency_sec": round(best_latency, 3),
        "changed": changed,
        "latency_stats_sec": {
            "median": round(median([item[0] for item in results]), 3),
            "min": round(min(item[0] for item in results), 3),
            "max": round(max(item[0] for item in results), 3),
        },
    }
