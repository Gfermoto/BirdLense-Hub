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

## See also

[MCP setup](mcp-setup.md) · [Architecture](architecture.md) · [CI and quality](ci-and-quality.md) · [Access control](access-control.md)
