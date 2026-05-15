# PostgreSQL for BirdLense Hub — operator guide

[Русский](./POSTGRES_MIGRATION.ru.md)

Single source of truth for running the **web** database on PostgreSQL under higher write concurrency (multi-camera hubs). Related epic: [#424](https://github.com/Gfermoto/BirdLense-Hub/issues/424) (track **B3**).

---

## When to use PostgreSQL

| Situation | Recommendation |
|-----------|------------------|
| Single hub, moderate traffic | Default **SQLite** under `DATA_DIR/db/birdlense.db` is fine |
| Many concurrent writes (multiple cameras, heavy UI + automation) | Set **`DATABASE_URL`** to PostgreSQL and tune the pool |
| Need HA / external backups | PostgreSQL + your standard ops tooling |

The Flask app uses SQLAlchemy with **Alembic** migrations (`app/web/migrations/`). Startup runs `create_app()` → `db.create_all()` then **`upgrade()`** — same path for SQLite and PostgreSQL (see [ARCHITECTURE](./ARCHITECTURE.md) § Database).

---

## Compose overlay and environment

**Example stack** (Postgres 16 + Redis + hub): [`app/docker-compose.stack.example.yml`](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/docker-compose.stack.example.yml).

Run:

```bash
cd app
docker compose -f docker-compose.yml -f docker-compose.stack.example.yml up -d
```

In **`app/.env`** (not overwritten by deploy):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | e.g. `postgresql+psycopg://birdlense:SECRET@postgres:5432/birdlense` |
| `SQLALCHEMY_POOL_SIZE` | Pool size (default `5` in `app/web/config.py`) |
| `SQLALCHEMY_MAX_OVERFLOW` | Extra connections beyond pool (default `15`) |

Implementation reference: `app/web/config.py` — SQLite vs non-SQLite engine options.

Also see [CONFIGURATION](./CONFIGURATION.md) → Environment variables.

---

## Processor SQLite (`birdlense.db`) is separate

The **processor** still uses the file **`DATA_DIR/db/birdlense.db`** for local diagnostics / BirdNET FIFO persistence unless configured otherwise. That path is **not** replaced by `DATABASE_URL`.

Implications:

- **BirdNET FIFO rows** written by the processor into SQLite may be **disabled or limited** when the hub API DB is PostgreSQL without a shared SQLite file — see [CHANGELOG](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) and [CONFIGURATION](./CONFIGURATION.md) (BirdNET / `DATABASE_URL` notes).
- Use **`detection.species_mapping`** in YAML when MQTT strings cannot be matched via SQLite catalog paths documented in [TROUBLESHOOTING](./TROUBLESHOOTING.md).

---

## Deployment paths

### A. Greenfield PostgreSQL (empty database)

1. Provision Postgres and create role/database (match `DATABASE_URL`).
2. Set `DATABASE_URL` + pool env in `app/.env`.
3. Bring up the stack (`docker compose` as above).
4. On first start the app applies migrations; verify **`GET /api/ui/readiness`** and **`/api/ui/status`**.

### B. Migrating data from existing SQLite (hub DB only)

There is **no** first-party one-click SQLite→Postgres copier in this repository. Operators typically:

1. **Backup** the current SQLite file (System → backup or copy `data/db/birdlense.db`).
2. Plan a **maintenance window**: stop writes (stop hub or put behind maintenance).
3. Create an **empty** PostgreSQL database with schema at current revision:
   - Point `DATABASE_URL` at Postgres and start the hub once so Alembic reaches head **or** run your controlled `flask db upgrade` equivalent inside the container image as documented for maintainers.
4. **Bulk-load** historical rows using tooling you trust (`pgloader`, ETL scripts, or vendor migration). Validate row counts and foreign keys; re-run application smoke tests.

Risks: type differences (JSON/JSONB — Alembic revision `004_birdnet_fifo_event` notes JSONB on Postgres), large blobs, and ordering of dependent tables. Prefer validating on a **staging** clone before production cutover.

If migration cost exceeds value, **stay on SQLite** until load requires Postgres, or accept a **fresh** Postgres hub and keep the old SQLite archive read-only for reference.

---

## Verification

After switching `DATABASE_URL`:

- `make verify` / `scripts/verify-stack.sh --base-url ...` — health, readiness, strict checks as configured.
- Optional: `scripts/check-runtime-sli.sh` after deploy (see `.github/workflows/deploy.yml`).

---

## See also

- [DEPLOY_SERVER](./DEPLOY_SERVER.md) · [INSTALL](./INSTALL.md)
- [PUBLIC_RECORDINGS](./PUBLIC_RECORDINGS.md) — VPS exposure checklist (orthogonal to DB engine)
- [RUNBOOKS](./RUNBOOKS.md)
