"""Xeno-canto API v3 integration for bird song playback."""

import os
import re
import logging

import requests

from app_config.app_config import app_config

logger = logging.getLogger(__name__)

XENO_CANTO_API = "https://xeno-canto.org/api/3/recordings"
TIMEOUT = 10
# Demo key unreliable; use XENO_CANTO_API_KEY env or secrets.xeno_canto_api_key from Settings
DEFAULT_KEY = "demo"


def _search_term_from_species_name(name: str) -> str:
    """Extract search term from species name for Xeno-canto.
    'Garrulus glandarius (Eurasian Jay)' -> 'Eurasian Jay'
    'Eurasian Jay' -> 'Eurasian Jay'
    'Bird' -> 'Bird'
    """
    if not name or not isinstance(name, str):
        return ""
    name = name.strip()
    # Extract common name from "Scientific (Common)" format
    match = re.search(r"\(([^)]+)\)\s*$", name)
    if match:
        return match.group(1).strip()
    return name


def fetch_recordings(species_name: str, limit: int = 5) -> list[dict]:
    """Fetch bird recordings from Xeno-canto API v3.
    Returns list of {id, file, en, type, rec, cnt} or empty list on error.
    """
    term = _search_term_from_species_name(species_name)
    if not term:
        return []

    api_key = (
        os.environ.get("XENO_CANTO_API_KEY", "").strip()
        or (app_config.get("secrets.xeno_canto_api_key") or "").strip()
        or DEFAULT_KEY
    )
    # API v3 query format: en:"common name" — экранируем " в term
    safe_term = term.replace('"', '\\"')
    query = f'en:"{safe_term}"'

    try:
        r = requests.get(
            XENO_CANTO_API,
            params={"query": query, "key": api_key, "per_page": limit},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("Xeno-canto API request failed: %s", e)
        return []
    except (ValueError, KeyError) as e:
        logger.warning("Xeno-canto API response parse error: %s", e)
        return []

    recordings = data.get("recordings") or []
    result = []
    for rec in recordings[:limit]:
        file_url = rec.get("file")
        if not file_url or not file_url.startswith("http"):
            continue
        result.append(
            {
                "id": rec.get("id"),
                "file": file_url,
                "en": rec.get("en", ""),
                "type": rec.get("type", ""),
                "rec": rec.get("rec", ""),
                "cnt": rec.get("cnt", ""),
            }
        )
    return result
