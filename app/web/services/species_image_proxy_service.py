"""Прокси /api/ui/species-image: allowlist, fetch, диск-кэш (#293)."""

from __future__ import annotations

import hashlib
import os
import time
from urllib.parse import urljoin, urlparse, urlunparse

import ipaddress
import requests
from flask import Response

from util import (
    data_dir,
    _host_is_inaturalist,
    _host_is_inaturalist_open_data_asset,
    _host_is_wikipedia_family,
)

_SPECIES_PROXY_MAX_REDIRECTS = 5


def species_proxy_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    try:
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return bool(
        _host_is_wikipedia_family(host) or _host_is_inaturalist(host) or _host_is_inaturalist_open_data_asset(host)
    )


def species_proxy_sanitized_fetch_url(url: str) -> str | None:
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or p.username or p.password:
        return None
    try:
        host = (p.hostname or "").lower()
        hn = p.hostname
        port = p.port
    except ValueError:
        return None
    if not host or not hn:
        return None
    if not (
        _host_is_wikipedia_family(host) or _host_is_inaturalist(host) or _host_is_inaturalist_open_data_asset(host)
    ):
        return None
    try:
        addr = ipaddress.ip_address(hn)
        host_netloc = f"[{hn}]" if addr.version == 6 else hn
    except ValueError:
        host_netloc = hn
    netloc = f"{host_netloc}:{port}" if port is not None else host_netloc
    return urlunparse((p.scheme, netloc, p.path or "", p.params, p.query, p.fragment))


def species_proxy_client_error_message(last_err: str | None) -> str:
    if not last_err:
        return "image proxy failed"
    if last_err.startswith("upstream status="):
        return last_err
    if last_err == "upstream is not image content":
        return last_err
    return "image proxy failed"


def fetch_species_proxy_upstream(start_url: str):
    current = start_url
    for _ in range(_SPECIES_PROXY_MAX_REDIRECTS + 1):
        if not species_proxy_allowed_url(current):
            return None, "image proxy: redirect to disallowed host"
        fetch_url = species_proxy_sanitized_fetch_url(current)
        if not fetch_url:
            return None, "image proxy: invalid URL"
        try:
            r = requests.get(
                fetch_url,
                timeout=8,
                headers={
                    "User-Agent": "BirdLense-Hub/1.0",
                    "Accept": "image/*,*/*;q=0.8",
                },
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException:
            return None, "image proxy: upstream request failed"
        if 300 <= r.status_code < 400:
            loc = (r.headers.get("Location") or "").strip()
            next_url = urljoin(r.url, loc) if loc else ""
            r.close()
            if not next_url:
                return None, "image proxy: redirect without Location"
            current = next_url
            continue
        return r, None
    return None, "image proxy: too many redirects"


def run_species_image_proxy(raw_url: str, app_logger) -> Response | tuple[dict, int]:
    """Flask Response или (error_json, status)."""
    raw = (raw_url or "").strip()
    if not raw:
        return {"error": "url is required"}, 400
    try:
        parsed = urlparse(raw)
    except ValueError:
        return {"error": "only absolute http/https URLs are allowed"}, 400
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"error": "only absolute http/https URLs are allowed"}, 400
    try:
        host = (parsed.hostname or "").lower()
    except ValueError:
        return {"error": "invalid URL for proxy"}, 400
    if not (
        _host_is_wikipedia_family(host) or _host_is_inaturalist(host) or _host_is_inaturalist_open_data_asset(host)
    ):
        return {"error": "host is not allowed for proxy"}, 400
    if species_proxy_sanitized_fetch_url(raw) is None:
        return {"error": "invalid URL for image proxy"}, 400

    key = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    cache_dir = os.path.join(data_dir(), "cache", "species_proxy")
    body_path = os.path.join(cache_dir, f"{key}.bin")
    ctype_path = os.path.join(cache_dir, f"{key}.ctype")
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        pass

    if os.path.isfile(body_path):
        try:
            with open(body_path, "rb") as fh:
                body = fh.read()
            ctype = "image/jpeg"
            if os.path.isfile(ctype_path):
                with open(ctype_path, "r", encoding="utf-8") as fh:
                    ctype = fh.read().strip() or ctype
            return Response(
                body,
                status=200,
                mimetype=ctype,
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except OSError:
            pass

    last_err = None
    for attempt in range(2):
        upstream = None
        try:
            upstream, fetch_err = fetch_species_proxy_upstream(raw)
            if fetch_err:
                last_err = fetch_err
                if attempt == 0:
                    time.sleep(0.35)
                    continue
                break
            if upstream.status_code >= 400:
                last_err = f"upstream status={upstream.status_code}"
                if attempt == 0:
                    time.sleep(0.35)
                    continue
                break
            ctype = (upstream.headers.get("Content-Type") or "").lower()
            if ctype and not ctype.startswith("image/"):
                last_err = "upstream is not image content"
                break
            body = upstream.content
            try:
                with open(body_path, "wb") as fh:
                    fh.write(body)
                with open(ctype_path, "w", encoding="utf-8") as fh:
                    fh.write(ctype or "image/jpeg")
            except OSError:
                pass
            headers = {"Cache-Control": "public, max-age=86400"}
            return Response(
                body,
                status=200,
                mimetype=ctype or "image/jpeg",
                headers=headers,
            )
        finally:
            if upstream is not None:
                upstream.close()

    app_logger.warning(
        "Species image proxy failed url=%s detail=%s",
        (raw[:512] + "…") if len(raw) > 512 else raw,
        last_err,
    )
    return {"error": species_proxy_client_error_message(last_err)}, 502
