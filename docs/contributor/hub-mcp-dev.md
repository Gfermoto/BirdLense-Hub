# Hub MCP — developer smoke and agent wiring

Operator setup (token, nginx, client JSON): [MCP setup](mcp-setup.md). Security posture: [Security](security.md) §1.

---

## What runs where

| Component | Role |
|-----------|------|
| `app/web/birdlense_mcp.py` | **MCP server** — OpenAPI → FastMCP tools; HTTP client to Hub `/api/ui` |
| `mcp.enabled` + entrypoint | Starts streamable HTTP on `127.0.0.1:8001`; nginx proxies **`/mcp`** |
| `MCP_TOKEN` / `mcp.token` | Bearer for MCP clients and (when set) MCP server auth |
| `birdlense-repo` (OpenCode) | **Filesystem** MCP — not Hub API; do not confuse with Hub MCP |

---

## Local smoke (`--check`)

Verifies OpenAPI → tool registration without starting HTTP. Needs `fastmcp` from `app/web/requirements.txt` (web venv):

```bash
cd app
make venv-web
PYTHONPATH=.:web .venv/bin/python web/birdlense_mcp.py --check
```

Expected stdout: tool/resource counts and up to eight tool names, e.g. `BirdLense Hub MCP: N tools, …`.

Optional env for auth wiring (not required for `--check`):

```bash
export MCP_TOKEN='dev-token-min-16-chars'   # same precedence as runtime: env > mcp.token in YAML
```

---

## Stack: `mcp.enabled` and streamable `/mcp`

1. **Settings → MCP** — enable server (`mcp.enabled: true` in config).
2. Set **`MCP_TOKEN`** in `app/.env` (or `mcp.token` in UI; env wins). Empty token = no MCP auth — **do not use in production** ([security](security.md)).
3. Restart container. Entrypoint runs:

   `python3 /app/web/birdlense_mcp.py --transport streamable-http --port 8001 --host 127.0.0.1`

4. Clients connect to **`http://<hub-host>:<port>/mcp`** with `Authorization: Bearer <MCP_TOKEN>` (see [mcp-setup](mcp-setup.md)).

Stdio transport (local IDE / OpenCode MCP config without nginx):

```bash
cd app && PYTHONPATH=.:web .venv/bin/python web/birdlense_mcp.py
```

---

## `@birdlense-ci` — fast vs full gates

OpenCode agent: `.opencode/agents/birdlense-ci.md` (read-only; reports pass/fail, no file edits).

| Scenario | Command | When |
|----------|---------|------|
| **Full gate** | `make ci-local` | Substantial changes before merge; Bandit, pip-audit, Ruff, full `pytest web/tests/`, UI codegen drift, Vitest, typecheck, lint, build, MkDocs strict |
| **Fast contract** | `make test-web-contract-local` | After OpenAPI or strict UI auth changes only (~minutes, host venv, no Docker) |
| **UI-only** | `cd app/ui && npm run typecheck` | React/TS changes without API contract |
| **Docker parity** | `make ci-local-docker` | Before release; adds image build, processor/web tests in container, Playwright smoke |

If pytest imports fail with stray `PYTHONPATH`, run `unset PYTHONPATH` and retry. Full matrix: [CI and quality](ci-and-quality.md), `AGENTS.md`.

**Reviewer vs CI:** `@birdlense-reviewer` suggests which gate to run; `@birdlense-ci` executes it — neither replaces GitHub Actions.

---

## Runbook Q&A (Phase B, dev-only)

Grounded answers from repo markdown — **no** new Python service in `app/web/`, **no** required OpenAI/Gemini.

| Piece | Path |
|-------|------|
| OpenCode agent | `.opencode/agents/birdlense-runbook-qa.md` — invoke `@birdlense-runbook-qa` |
| Prompt template | `.opencode/prompts/runbook-qa.md` |
| RU operator index | `docs/ru/runbooks.ru.md` |
| EN runbooks | `docs/runbooks/*.md` |
| Strategy | `docs/strategy/hands_on_ai_engineering_research.md` § Phase B |

**Workflow**

1. Ask in OpenCode TUI: `@birdlense-runbook-qa почему YOLO слепой?`
2. Agent reads `docs/ru/yolo-blind-runbook.ru.md` (and related) via filesystem / `birdlense-repo` MCP.
3. Optional **webfetch** only for your published MkDocs URL (same host as `DEPLOY_URL/docs/`) — not web search.
4. Answer must cite `path/to/file.md` + section; no invented metric values.

**Cursor:** same agent file applies; or paste template from `.opencode/prompts/runbook-qa.md`.

**When to use `@birdlense-operator-router` instead:** question needs **live** Hub JSON (orphan count, readiness funnel, backpressure) — see below.

---

## Hub MCP tool groups (visits · health · funnel)

`birdlense_mcp.py` registers **all** OpenAPI operations with `x-tool: true` as MCP tools. Names follow FastMCP/OpenAPI (path + method); use **path prefixes** for routing.

| Group | Use when | OpenAPI paths (under `/api/ui` unless noted) |
|-------|----------|-----------------------------------------------|
| **Visits / videos** | timeline, detections, orphans, species overview | `/videos/`, `/timeline`, `/overview`, `/unknowns`, `/detections/`, `/system/visitors`, `/system/activity`, `/system/clean-orphaned-visits` |
| **Health / config** | readiness, status, settings, YOLO blind, cameras | `/health`, `/readiness`, `/status`, `/settings`, `/cameras`, `/system/config-audit`, `/system/domain-health`, `/system/yolo-detector-health`, `/system/ml-runtime`, `/system/metrics` |
| **Funnel / perf** | finalize queue, drops, OOM, Prometheus, runtime stats | `/system/diagnostics/backpressure`, `/system/diagnostics/processor-runtime`, `/system/metrics/history`, `/api/debug/scoring`; root `/metrics`, `/api/metrics`; readiness body fields `pipeline_funnel`, `yolo_detector` |

**Confused with filesystem MCP?** `birdlense-repo` in `opencode.json` reads files on disk; Hub MCP calls the running API.

Smoke (tool count):

```bash
cd app && PYTHONPATH=.:web .venv/bin/python web/birdlense_mcp.py --check
```

Connect Hub MCP in OpenCode (user-level, token not in repo):

```bash
# stdio example — adjust path and env
export MCP_TOKEN='your-dev-token'
opencode mcp add birdlense-hub -- \
  python3 /path/to/BirdLense/app/web/birdlense_mcp.py
```

Streamable HTTP (stack with `mcp.enabled`): `http://<host>:8085/mcp` + Bearer — [MCP setup](mcp-setup.md).

---

## Operator router (Phase C minimal, dev-only)

**Not** a prod LLM service. Keyword router + MCP tool groups; honest scope per [ADR: dev-only operator router](../strategy/adr-dev-only-operator-router.md).

| Piece | Path |
|-------|------|
| OpenCode agent | `.opencode/agents/birdlense-operator-router.md` — `@birdlense-operator-router` |
| Doc Q&A fallback | `@birdlense-runbook-qa` |
| ADR | `docs/strategy/adr-dev-only-operator-router.md` |

**Example routing**

| User question | Group | First tools / paths |
|---------------|-------|---------------------|
| «Сколько orphan visits?» | Visits | `GET /system/clean-orphaned-visits` (preview), `/system/activity` |
| «Readiness и YOLO blind?» | Health | `GET /readiness`, `GET /system/yolo-detector-health` |
| «Finalize queue / OOM 137?» | Funnel | `GET /system/diagnostics/backpressure`, runbook `docs/runbooks/processor-oom-137.md` |

**Fallback chain:** Hub MCP → local runbooks (`@birdlense-runbook-qa`) → «не знаю».

**Deferred:** semantic/cloud LLM router, vector DB, operator chat UI in React (#627).

---

## See also

[MCP setup](mcp-setup.md) · [Architecture](architecture.md) · [CI and quality](ci-and-quality.md) · [Access control](access-control.md) · [AI tooling research](../strategy/hands_on_ai_engineering_research.md)
