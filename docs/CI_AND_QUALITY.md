# CI and code quality policy

[Русский](./CI_AND_QUALITY.ru.md)

This document describes what runs in GitHub Actions, how to reproduce checks locally, and how we extend quality gates without breaking the default green pipeline.

## Workflows (summary)

| Workflow / job | Purpose |
|----------------|---------|
| **CI → python-security** | `bandit` on `web/` + `processor/src/`; `pip-audit` on both `requirements.txt` files. |
| **CI → openapi-contract** | `ruff check` + **`ruff format --check`** on `web/` + `processor/src/`; **radon cc** summary (non-blocking); docs version script; focused pytest slices. |
| **CI → ui-build** | `npm ci`; **`npm run codegen:openapi`** + `git diff` on `src/generated/openapi-types.ts`; `npm run lint`; `npm run build` in `app/ui`. |
| **CI → docs** | MkDocs strict, settings UI coverage script, version check. |
| **CI → docker-tests** | Full image build; processor + web tests; Playwright smoke; catalog audit script. |

Source: `.github/workflows/ci-pr.yml`.

## Ruff

- **Config:** `app/pyproject.toml` (`[tool.ruff]`, line length 120, target Python 3.11).
- **Lint:** `ruff check web/ processor/src/` (must pass in CI).
- **Format:** `ruff format web/ processor/src/` — output is enforced in CI (`--check`). Apply locally before push:
  ```bash
  cd app && docker compose run --rm -v "$(pwd)":/app birdlense \
    bash -c 'pip install ruff==0.9.2 && ruff format web/ processor/src/'
  ```
- **Exceptions:** `processor/src/main.py` uses a deliberate import order (OpenCV init before bootstrap); `E402` is ignored for that file in `pyproject.toml`.

## pip-audit

- Run in **python-security** with both requirement files.
- Known ignore: `PYSEC-2022-42969` (transitive `py` via dev/docs tooling); documented inline in the workflow.

## npm audit

- Weekly / manual workflow: `.github/workflows/npm-audit-scheduled.yml` (policy in workflow comments; see [#284](https://github.com/Gfermoto/BirdLense-Hub/issues/284)). Not a required PR check.

## Mutating API JSON validation

- Helpers: `app/web/services/api_json_validation.py` — `parse_request_json_dict` (strict object body), `parse_request_json_object_allow_empty` (object or empty → `{}`), `parse_request_json_array_allow_empty` (array or empty → `[]`), `validation_error`.
- Endpoints are listed in that module’s docstring; regression tests: `web/tests/test_api_json_validation.py`.
- Introduced in [#281](https://github.com/Gfermoto/BirdLense-Hub/issues/281); extend the same pattern for remaining mutating routes as needed.

## OpenAPI → TypeScript

- Spec: `app/web/openapi.yaml`. Contract tests: `web/tests/test_openapi_contract.py`.
- **Codegen:** `app/ui` — `npm run codegen:openapi` ([openapi-typescript](https://github.com/openapi-ts/openapi-typescript)) writes `src/generated/openapi-types.ts`. The **ui-build** job regenerates from the spec and fails if the committed file drifts. Regenerate after OpenAPI changes:
  ```bash
  cd app/ui && npm ci && npm run codegen:openapi
  ```

## Complexity / radon

- **CI:** `openapi-contract` appends a **radon cc** summary to the job log (informational; no failure threshold).
- Locally: `pip install radon && radon cc app/web app/processor/src -a -s` (from repo root; paths match the tree on disk).
