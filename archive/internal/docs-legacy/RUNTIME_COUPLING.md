# Runtime coupling (single container)

How the **BirdLense** image wires web, processor, and `PYTHONPATH`, and how we plan to loosen coupling without breaking the default install path. Companion to [ARCHITECTURE](./ARCHITECTURE.md) and [TROUBLESHOOTING](./TROUBLESHOOTING.md) (stuck startup). Tracked as [issue #347](https://github.com/Gfermoto/BirdLense-Hub/issues/347).

[Русский](./RUNTIME_COUPLING.ru.md)

---

## `PYTHONPATH` inventory (container)

| Step | `PYTHONPATH` | Working directory / command |
| ------ | ---------------- | ----------------------------- |
| Gunicorn | `/app` | `cd /app/web` → `gunicorn … app:app` |
| MCP (optional) | `/app` | `python3 /app/web/birdlense_mcp.py …` |
| Processor loop | `/app:/app/web` | `python /app/processor/src/main.py` |

**`/app`** exposes repo-root modules shipped in the image (`ebird_region_core.py`, `shared/`, `processor/` layout). **`/app/web`** remains on the processor path for historical compatibility ([#128](https://github.com/Gfermoto/BirdLense-Hub/issues/128)); a repo-wide grep should show **no** current `from services.*` imports under `app/processor/` — do not remove `/app/web` from the entrypoint until a maintainer re-audits imports and CI.

---

## Web ↔ processor boundaries

| Direction | Mechanism | Notes |
| ----------- | ----------- | -------- |
| **Processor → web** | HTTP client to `API_URL_BASE` (e.g. `http://127.0.0.1:8000/api/processor/...`) | Ingest, notify, activity log; authenticated with `PROCESSOR_SECRET` |
| **Web → processor code** | **Filesystem + `sys.path`**, not a Python package import of `web` from `processor` | `fusion_training_service.ensure_fusion_processor_src_on_path()` adds `processor/src` for `fusion_metrics` / `fusion_model` |
| **Shared code** | `app/shared/` copied to `/app/shared/` | Example: `processor/.../dataset_saver.py` → `from shared.detection_crop_contract import …` |

**Candidates for `app/shared/`** (only if a second consumer appears or tests get simpler):

- Small pure helpers already duplicated between stacks.
- Long-term: optional extraction of **`fusion_*`** modules if both web training and processor should import one package without `sys.path` hacks (larger refactor).

---

## Health: “web ok” vs “processor ok”

| Probe | Meaning |
| ------- | --------- |
| **`GET /api/ui/health`** | Gunicorn/Flask process responds; **does not** check DB or disk. |
| **`GET /api/ui/readiness`** | DB ping, `data/` and `app_config/` writable, component snapshot; **503** if not ready. |
| **Processor** | No dedicated health HTTP endpoint in the default image; infer from application logs, MJPEG/live path via nginx, and successful processor POSTs to the API. |

Compose `healthcheck` today targets **`/api/ui/health`** on port **8000** inside the container (same as `entrypoint.sh` wait).

---

## Compose profile `dev-split` (draft)

**Goal:** optional multi-service layout for development **without** changing default `docker compose up` (no extra `-f` file → current behavior).

**Status:** contract only. The production image still runs **one** CMD (nginx + gunicorn + processor). Splitting into separate containers requires a different image entrypoint or additional images; do not treat future snippets as production-ready.

Validate that the merge file parses with the main stack:

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.dev-split.example.yml config
```

Repository file **`app/docker-compose.dev-split.example.yml`** currently carries only a Compose **`x-`** extension block (metadata). **No** extra `services` are defined yet — when the image supports split roles, add services with **`profiles: ["dev-split"]`** there so default `docker compose up` stays unchanged.
