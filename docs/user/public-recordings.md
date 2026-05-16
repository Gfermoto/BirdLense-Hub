# Public / VPS recording exposure (single checklist)

Canonical contour for **internet-facing** BirdLense Hub: how clips leave the container, what nginx does, and how **`/api/ui/videos/:id/stream`** relates to **`BIRDLENSE_STRICT_API_AUTH`**.

[Russian](./PUBLIC_RECORDINGS.ru.md)

---

## Data paths (two layers)

1. **Nginx (static):** Optional `location` for **`/data/recordings/`** → `alias` to files on disk. If present, URLs like `/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4` work **without** Flask session (only HTTP).
2. **Flask (authenticated policy inside the app):** **`GET /api/ui/videos/<id>/stream`** serves the same files with **`send_file`**, Range support, and optional **`general.require_auth_for_video_stream`**.

Other **`/data/*`** paths (DB, datasets, cache) are **not** served as static files — see [SECURITY.md §3](./SECURITY.md).

---

## Recommended baseline (public VPS)

Use this block together; it matches [Roadmap #418 A2](https://github.com/Gfermoto/BirdLense-Hub/issues/423) / release hardening.

| Step | Setting | Why |
|------|---------|-----|
| 1 | **`BIRDLENSE_HIDE_DIRECT_RECORDINGS=1`** in **`app/.env`** | Omits nginx static `location` for **`/data/recordings/`** (see [CONFIGURATION](./CONFIGURATION.md)). Anonymous predictable **`GET /data/recordings/...`** → **403**. Playback stays on **`/api/ui/videos/:id/stream`**. |
| 2 | **`BIRDLENSE_STRICT_API_AUTH=1`** + [production gates](https://github.com/Gfermoto/BirdLense-Hub/blob/main/AGENTS.md#production-gates) | Locks mutating **`/api/ui/*`**; many read-only dashboard GETs remain public per [ACCESS_CONTROL](./ACCESS_CONTROL.md). |
| 3 | *(Optional)* **`general.require_auth_for_video_stream: true`** | Requires Contributor/Admin session (or equivalent) **inside** the stream handler even when strict mode allows **`GET /api/ui/videos/*`** through the middleware — use when guests must not fetch MP4 bytes. |

Env wiring: **`BIRDLENSE_HIDE_DIRECT_RECORDINGS`** is applied at container start (`app/scripts/entrypoint.sh` substitutes **`__RECORDINGS_LOCATION_BLOCK__`** in `app/nginx/standalone.conf.template`).

---

## Alternatives (not the default checklist)

- **LAN / lab:** you may leave direct nginx recordings enabled (default) for simpler debugging.
- **IP allowlist on `/data/recordings/`:** `app/nginx/examples/recordings_allowlist.conf.snippet` — merge carefully with **`entrypoint.sh`** output or front proxy.
- **External reverse proxy only** exposing **`/api/…`**, or **`auth_request`** — operator integration, not shipped as the default image story.

Details stay in [SECURITY.md §3](./SECURITY.md) for threat framing; **this page** is the operator “what to turn on” SSOT.

---

## Verify

```bash
# Direct path must not leak MP4 when hide flag is on (expect 403)
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/recordings/2099/01/01/120000/video.mp4"

# DB must never be static-served (expect 403)
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/db/birdlense.db"

# Path traversal hardening (expect 403)
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/../.env"
```

Stream behaviour depends on **`require_auth_for_video_stream`** and session — exercise from the browser after login as needed.

---

## See also

- [DEPLOY_SERVER.md §8](./DEPLOY_SERVER.md) — short pointer from deploy checklist  
- [CONFIGURATION.md](./CONFIGURATION.md) — **`BIRDLENSE_HIDE_DIRECT_RECORDINGS`**, **`require_auth_for_video_stream`**  
- [ACCESS_CONTROL.md](./ACCESS_CONTROL.md) — strict **`/api/ui/*`** allowlists  
