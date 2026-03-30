#!/usr/bin/env bash
# Автоподбор рабочего Telegram-прокси (SOCKS5) из ProxyGenerator.
# Запускается локально, тестирует прокси с удалённого хоста BirdLense через SSH.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "${SCRIPT_DIR}/deploy.local.sh" ] && . "${SCRIPT_DIR}/deploy.local.sh"

HOST="${DEPLOY_HOST:-birdlense}"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/root/BirdLense}"
SSH_PORT="${DEPLOY_SSH_PORT:-22}"
SSH_OPTS="-p ${SSH_PORT} -o ServerAliveInterval=30 -o ServerAliveCountMax=20"

TOP_N="${TOP_N:-40}"                  # сколько прокси максимум проверять
MAX_TIME="${MAX_TIME:-12}"            # timeout curl на одну проверку
BOT_PATH="${BOT_PATH:-botINVALID/getMe}" # invalid bot: 401/404 означает, что канал к Telegram есть

echo "=== Telegram proxy refresh on ${HOST} ==="
if [[ "${BIRDLENSE_PROXY_LOCAL:-0}" == "1" || "${HOST}" == "localhost" || "${HOST}" == "127.0.0.1" ]]; then
python3 - <<'PY'
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import yaml

REMOTE_CFG = Path("/root/BirdLense/app/app_config/user_config.yaml")
MAX_CANDIDATES = int(os.environ.get("TOP_N", "40"))
MAX_TIME = int(os.environ.get("MAX_TIME", "12"))
BOT_PATH = os.environ.get("BOT_PATH", "botINVALID/getMe")
REMOTE_DIR = os.environ.get("REMOTE_DIR", "/root/BirdLense")

URLS = [
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks5.txt",
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/socks5.txt",
]

def fetch_lines(url: str) -> list[str]:
    with urlopen(url, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return [x.strip() for x in raw.splitlines() if x.strip() and ":" in x]

def probe(proxy: str) -> tuple[bool, float, str]:
    p = f"socks5h://{proxy}"
    cmd = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--max-time",
        str(MAX_TIME),
        "--proxy",
        p,
        f"https://api.telegram.org/{BOT_PATH}",
    ]
    t0 = time.monotonic()
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return (False, 999.0, "ERR")
    dt = time.monotonic() - t0
    return (out in ("401", "404"), dt, out)

proxies = []
seen = set()
for u in URLS:
    for item in fetch_lines(u):
        if item not in seen:
            seen.add(item)
            proxies.append(item)

candidates = proxies[:MAX_CANDIDATES]
results = []
for prx in candidates:
    ok, dt, code = probe(prx)
    if ok:
        results.append((dt, prx, code))

if not results:
    raise SystemExit("No working SOCKS5 proxy found for Telegram API")

results.sort(key=lambda x: x[0])
best_dt, best_proxy, best_code = results[0]
best_url = f"socks5h://{best_proxy}"

cfg = yaml.safe_load(REMOTE_CFG.read_text(encoding="utf-8")) or {}
notif = cfg.setdefault("notifications", {})
current_type = (notif.get("telegram_proxy_type") or "").strip()
current_url = (notif.get("telegram_proxy_url") or "").strip()

changed = (current_type != "socks_http") or (current_url != best_url)
notif["telegram_proxy_type"] = "socks_http"
notif["telegram_proxy_url"] = best_url

if changed:
    bak = REMOTE_CFG.with_name(f"user_config.yaml.bak.proxy-{int(time.time())}")
    bak.write_text(REMOTE_CFG.read_text(encoding="utf-8"), encoding="utf-8")
    REMOTE_CFG.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    subprocess.check_call(["bash", "-lc", f"cd {REMOTE_DIR}/app && make stop && make start >/tmp/bl-proxy-restart.log 2>&1"])

print(json.dumps({
    "checked": len(candidates),
    "working": len(results),
    "best_proxy": best_url,
    "best_code": best_code,
    "best_latency_sec": round(best_dt, 3),
    "changed": changed,
}, ensure_ascii=False))
PY
else
ssh ${SSH_OPTS} "${HOST}" \
  TOP_N="${TOP_N}" MAX_TIME="${MAX_TIME}" BOT_PATH="${BOT_PATH}" REMOTE_DIR="${REMOTE_DIR}" \
  'python3 -' <<'PY'
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import yaml

REMOTE_CFG = Path("/root/BirdLense/app/app_config/user_config.yaml")
MAX_CANDIDATES = int(os.environ.get("TOP_N", "40"))
MAX_TIME = int(os.environ.get("MAX_TIME", "12"))
BOT_PATH = os.environ.get("BOT_PATH", "botINVALID/getMe")
REMOTE_DIR = os.environ.get("REMOTE_DIR", "/root/BirdLense")

URLS = [
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks5.txt",
    "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/socks5.txt",
]

def fetch_lines(url: str) -> list[str]:
    with urlopen(url, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return [x.strip() for x in raw.splitlines() if x.strip() and ":" in x]

def probe(proxy: str) -> tuple[bool, float, str]:
    p = f"socks5h://{proxy}"
    cmd = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--max-time",
        str(MAX_TIME),
        "--proxy",
        p,
        f"https://api.telegram.org/{BOT_PATH}",
    ]
    t0 = time.monotonic()
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return (False, 999.0, "ERR")
    dt = time.monotonic() - t0
    return (out in ("401", "404"), dt, out)

proxies = []
seen = set()
for u in URLS:
    for item in fetch_lines(u):
        if item not in seen:
            seen.add(item)
            proxies.append(item)

candidates = proxies[:MAX_CANDIDATES]
results = []
for prx in candidates:
    ok, dt, code = probe(prx)
    if ok:
        results.append((dt, prx, code))

if not results:
    raise SystemExit("No working SOCKS5 proxy found for Telegram API")

results.sort(key=lambda x: x[0])
best_dt, best_proxy, best_code = results[0]
best_url = f"socks5h://{best_proxy}"

cfg = yaml.safe_load(REMOTE_CFG.read_text(encoding="utf-8")) or {}
notif = cfg.setdefault("notifications", {})
current_type = (notif.get("telegram_proxy_type") or "").strip()
current_url = (notif.get("telegram_proxy_url") or "").strip()

changed = (current_type != "socks_http") or (current_url != best_url)
notif["telegram_proxy_type"] = "socks_http"
notif["telegram_proxy_url"] = best_url

if changed:
    bak = REMOTE_CFG.with_name(f"user_config.yaml.bak.proxy-{int(time.time())}")
    bak.write_text(REMOTE_CFG.read_text(encoding="utf-8"), encoding="utf-8")
    REMOTE_CFG.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    subprocess.check_call(["bash", "-lc", f"cd {REMOTE_DIR}/app && make stop && make start >/tmp/bl-proxy-restart.log 2>&1"])

print(json.dumps({
    "checked": len(candidates),
    "working": len(results),
    "best_proxy": best_url,
    "best_code": best_code,
    "best_latency_sec": round(best_dt, 3),
    "changed": changed,
}, ensure_ascii=False))
PY
fi
