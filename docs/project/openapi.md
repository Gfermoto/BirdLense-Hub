# OpenAPI specification

Authoritative HTTP contract (paths, schemas, auth):

[`app/web/openapi.yaml` on GitHub](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml)

Import the YAML into Redoc, Stoplight, Postman, or your IDE. The file defines **two** `servers` entries: **`/api/ui`** (browser UI + MCP) and **`/api/processor`** (processor ingest). Narrative overview: [API](../API.md) · [Russian API page](../API.ru.md).

To regenerate the bulk of UI paths merged from `scripts/generate_openapi_remaining_paths.py`, run: `python3 scripts/merge_openapi_fragments.py` (rewrites `app/web/openapi.yaml`; keep the repo clean and review the diff).
