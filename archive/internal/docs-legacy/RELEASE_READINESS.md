# Release Readiness — BirdLense Hub

[Русский](./RELEASE_READINESS.ru.md)

**Short one-page gate:** [Definition of Done](./DEFINITION_OF_DONE.md) (`make ci-local` + `verify-stack` + 5-minute smoke).  
**Public release sequence:** [Public Release Checklist](./PUBLIC_RELEASE_CHECKLIST.md).

---

Checklist before a release, deployment, or claiming that stabilization work is complete.

## Core checks

- `GET /api/ui/system/domain-health`
- `GET /api/ui/system/species-registry/health`
- `GET /api/ui/system/config-audit`
- `make verify`
- `BASE_URL=http://YOUR_HOST:8085 ./scripts/verify-release.sh`
- full locked-hub mode:
  `BIRDLENSE_UI_API_KEY=... REQUIRE_SETTINGS_HEALTH=1 BASE_URL=http://YOUR_HOST:8085 ./scripts/verify-release.sh`

## GitHub Actions (`deploy.yml`)

Optional but recommended when the hub uses strict UI API auth: add repository secret **`BIRDLENSE_UI_API_KEY`** with the same value as `BIRDLENSE_UI_API_KEY` in the server `app/.env`. When the secret is set, the post-deploy **Verify** step runs `verify-stack.sh` with **`--check-domain-health`** and then **`verify-release.sh`** with **`REQUIRE_SETTINGS_HEALTH=1`**. If the secret is absent, CI only checks health, readiness, and status so the workflow does not fail on authenticated domain endpoints.

## Expected baseline

- `orphaned_visits = 0`
- `visit_species_mismatches = 0`
- `species_resolution_mismatches = 0`
- review-only detections do not inflate visits or monthly stats
- `decision_trace` exposes `decision_kind`, `decision_reason`, `outcome_bucket`, `trust_band`, and recording context

## Blocking conditions

Do not call the release ready when any of the following is true:

- silent auto-decisions are still present
- review-only rows leak into visits or reports
- the species registry drifts between `Species`, `SpeciesTaxon`, and resolver output
- smoke checks pass only partially or with unexplained warnings
