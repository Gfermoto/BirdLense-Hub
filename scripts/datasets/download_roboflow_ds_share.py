#!/usr/bin/env python3
"""
Скачивание ZIP экспорта Roboflow по **короткой ссылке Universe** вида
``https://universe.roboflow.com/ds/<id>?key=<download_key>``.

Roboflow отдаёт редирект на ``storage.googleapis.com``; ``curl`` из консоли
иногда обрывается (HTTP/2 / TLS), а запрос через ``requests`` к
``https://app.roboflow.com/ds/...`` обычно стабильнее для первого хопа.

**Не коммитьте ключ в репозиторий.** При утечке отзовите ключ на Roboflow.

Пример::

    pip install requests
    python3 scripts/datasets/download_roboflow_ds_share.py \\
      --url 'https://universe.roboflow.com/ds/XXXX?key=YYYY' \\
      --out-zip datasets/downloads/roboflow_share/export.zip

Дальше импорт (птицы или грызуны)::

    python3 scripts/datasets/import_roboflow_bird_feeder_birds.py \\
      --root datasets/new/detector --zip datasets/downloads/roboflow_share/export.zip \\
      --binary-subdir rodent --prefix rf_univ_
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Установите: pip install requests", file=sys.stderr)
    raise SystemExit(2)


def _share_url_to_app_api(url: str) -> str:
    """Universe /ds/… часто за Cloudflare; тот же путь на app.roboflow.com даёт 302 на GCS."""
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        url = "https://" + url.strip()
        parsed = urlparse(url)
    path = parsed.path or ""
    qs = f"?{parsed.query}" if parsed.query else ""
    if "/ds/" not in path:
        raise ValueError(f"Ожидался путь с /ds/<id>: {url!r}")
    return f"https://app.roboflow.com{path}{qs}"


def _resolve_download_link(session: requests.Session, url: str, *, timeout: float) -> str:
    app_url = _share_url_to_app_api(url)
    r = session.get(app_url, allow_redirects=False, timeout=timeout)
    if r.status_code not in (301, 302, 303, 307, 308):
        raise RuntimeError(
            f"Ожидался редирект с app.roboflow.com, получено HTTP {r.status_code}: {app_url}"
        )
    loc = r.headers.get("Location")
    if not loc:
        raise RuntimeError("Редирект без заголовка Location")
    if loc.startswith("/"):
        loc = f"{urlparse(app_url).scheme}://{urlparse(app_url).netloc}{loc}"
    if "storage.googleapis.com" not in loc and not re.match(r"^https?://", loc):
        raise RuntimeError(f"Неожиданный Location: {loc[:200]}")
    return loc


def _session_with_retries() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--url",
        required=True,
        help="Ссылка Universe или app.roboflow.com с /ds/<id>?key=…",
    )
    ap.add_argument(
        "--out-zip",
        type=Path,
        required=True,
        help="Куда сохранить ZIP",
    )
    ap.add_argument(
        "--timeout-connect",
        type=float,
        default=120.0,
        help="Таймаут TCP+TLS (сек)",
    )
    ap.add_argument(
        "--timeout-read",
        type=float,
        default=1200.0,
        help="Таймаут чтения тела ответа (сек)",
    )
    args = ap.parse_args()

    out_zip = args.out_zip.resolve()
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    timeout = (args.timeout_connect, args.timeout_read)
    session = _session_with_retries()

    try:
        gcs_url = _resolve_download_link(session, args.url, timeout=timeout)
    except Exception as e:
        print(f"Не удалось получить ссылку на архив: {e}", file=sys.stderr)
        return 2

    print(f"Скачивание → {out_zip}", flush=True)
    try:
        r = session.get(gcs_url, stream=True, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        print(
            f"Ошибка загрузки с GCS (часто блокировка сети до storage.googleapis.com): {e}",
            file=sys.stderr,
        )
        print(
            "Обход: скачайте ZIP в браузере по исходной ссылке Universe "
            "или с другой машины/VPN, затем --zip в import_roboflow_bird_feeder_birds.py.",
            file=sys.stderr,
        )
        return 2

    total = int(r.headers.get("content-length") or 0)
    n = 0
    with out_zip.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                f.write(chunk)
                n += len(chunk)
                if total and n % (100 * 1024 * 1024) < 512 * 1024:
                    print(f"  … {n / 1e6:.1f} MB", flush=True)

    print(f"Готово: {n} байт → {out_zip}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
