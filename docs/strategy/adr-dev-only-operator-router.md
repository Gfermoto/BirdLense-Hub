# ADR: Dev-only operator router (Phase C minimal)

**Status:** accepted  
**Date:** 2026-06-10  
**Issues:** [#632](https://github.com/Gfermoto/BirdLense-Hub/issues/632)  
**Related:** [hands_on_ai_engineering_research.md](hands_on_ai_engineering_research.md) Phase C, [#631](https://github.com/Gfermoto/BirdLense-Hub/issues/631) Phase B

---

## Context

Operators ask mixed questions: live Hub state («orphan visits», «openvino device», «finalize p95») and procedural («how to fix YOLO blind»). Phase B covers grounded doc Q&A. Phase C needs a single **entry point** without adding LLM to prod containers or a vector DB.

Hands-On-AI-Engineering patterns considered: multi-domain router, agentic RAG with grade-before-answer. BirdLense constraints: **no cloud LLM in prod**, Hub MCP already exposes OpenAPI as tools.

---

## Decision

Implement **Phase C minimal** as **dev-only routing**:

1. **Documentation:** MCP tool groups (visits · health · funnel) in `docs/contributor/hub-mcp-dev.md`.
2. **OpenCode agent:** `.opencode/agents/birdlense-operator-router.md` — **keyword rules** map user text → OpenAPI path prefix / MCP tool group; agent may call Hub MCP when connected.
3. **No new runtime service** in `app/web/` (no Flask router, no embeddings, no OpenAI/Gemini requirement).
4. **Fallback chain:** Hub MCP tools → `@birdlense-runbook-qa` (local `.md`) → explicit «не знаю».

Full LLM-based semantic router **deferred** until Phase B proves ≥3 real questions/month and golden-set grounding ≥80%.

---

## Consequences

**Positive**

- Zero prod footprint; reuses `birdlense_mcp.py` and existing REST/SQLite views.
- Deterministic keyword table is debuggable and cheap to extend.
- Meets Phase C exit criteria for **minimal** scope: structured domains, grade-before-answer, no vector DB.

**Negative**

- Synonyms and multi-domain questions need manual keyword updates or future LLM router (still dev-only).
- Hub MCP tool names follow FastMCP/OpenAPI codegen — operators use paths in docs, not memorized tool IDs.

**Out of scope (explicit)**

- React operator chat panel (#627 consortium)
- Chroma/Qdrant, cloud embeddings
- Prod microservice «operator assistant»

---

## Verification

| Check | How |
|-------|-----|
| Router doc exists | `hub-mcp-dev.md` § Operator router |
| Agent exists | `@birdlense-operator-router` in OpenCode |
| No app code | `git diff app/` empty for this ADR delivery |
| Sample routes | «orphan visits» → Group A; «readiness funnel» → Group B; «backpressure» → Group C |

---

## Revisit when

- Phase B golden set fails stop conditions in research doc §6
- Consortium #627 ships operator UI that makes MCP-from-chat redundant
- Request for searchable tool discovery at scale (then: MCPToolset pattern, still dev-only)
