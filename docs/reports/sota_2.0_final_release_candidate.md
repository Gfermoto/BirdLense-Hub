# SOTA 2.0 — Final Release Candidate (2026-05-20)

**Verdict: Ready to merge to `main` and public announcement** (pending green GitHub Actions on `dev`).

---

## 1. Stress test results

Command: `make stress-test-offline` · optional: `python3 scripts/stress_test_offline.py --storm-video app/data/stress_clips/storm_bird.mp4` (Docker + weights).

| Scenario | Criterion | Result |
|----------|-----------|--------|
| **A — Dead silence** (synthetic, 400 frames, phantom boxes 0.32–0.36) | `accepted_boxes == 0` | **PASS** (0) |
| **B — Storm golden** (24 synthetic bird probes) | Recall = 1.0 | **PASS** (12/12 birds) |
| **B — Storm video** (prod clip `2026/05/18/074247`, YOLO+Scoring) | Recall = 1.0 on YOLO frames | **PASS** (2/2) |

Auto-tune grid: not required (first config green).

Artifacts: `scripts/stress_test_offline.py` · report format `stress_test_offline@v1`.

---

## 2. Golden Gate (CI)

| Gate | Threshold | Local run |
|------|-----------|-----------|
| `test_pipeline_golden_gate` (synthetic) | F1 ≥ **0.9** | PASS (5 passed, 1 skipped) |
| Real `manifest.json` | F1 ≥ 0.9 when clips present | skip if empty |

Env: `GOLDEN_GATE_MIN_F1=0.9` · `STRESS_MAX_SILENCE_ACCEPTED=0`.

---

## 3. CI/CD integration

**Workflow:** `.github/workflows/ci-pr.yml` → job `openapi-contract`:

- `scripts/check_legacy_processor_config.py`
- `make validate-pipeline-golden`
- `python3 scripts/stress_test_offline.py --no-yolo`

**Pre-commit:** `.pre-commit-config.yaml` — legacy config + golden gate quick smoke.

**Merge policy:** PR fails if F1 &lt; 0.9 or silence stress accepts &gt; 0.

---

## 4. Observability

| Surface | Path |
|---------|------|
| Debug API | `GET /api/debug/scoring` (settings password) |
| Black Box | `data/decision_traces/**/*.jsonl` |
| Review degradation | `degradation_alert` when review &gt; 20% / 5 min |
| OpenAPI | `/api/debug/scoring` documented |

Web reads traces cross-process via `scoring_debug_service.py` (processor telemetry is in-process only).

---

## 5. Documentation

| Doc | Purpose |
|-----|---------|
| [README.md](../../README.md) | “How detection decisions work (SOTA 2.0)” |
| [TROUBLESHOOTING_SCORING.md](../user/TROUBLESHOOTING_SCORING.md) | Silent / spam / config checklist |
| [sota_2.0_launch_report.md](./sota_2.0_launch_report.md) | Deploy + architecture delta |

---

## 6. Code hygiene

- **ScoringEngine** replaces runtime cascade when `scoring_engine_enabled: true`.
- **Legacy filters** (`static_object_filter.py`, MOG2 in `scene_adaptive.py`) retained for rollback/tests; marked LEGACY in module docs.
- **Not deleted:** unit tests + `validate_static_object_filter.py` still valid for regression.

---

## 7. Production status

- Deployed: `089db6dd` / `a55fe106` on VPS `185.218.111.196:8085`
- `patch_prod_sota20_user_config.py` applied
- Golden v2: **50 clips** on server

---

## 8. Wave 3 unlocked

- Active Learning (#479) — stable accept/reject signal
- ReID (#480) — consistent bbox gate
- INT8 (#481) · Mask UI (#482)

---

## Sign-off

| Check | Status |
|-------|--------|
| Stress A/B | ✅ |
| Golden F1 ≥ 0.9 | ✅ |
| CI wired | ✅ |
| Docs | ✅ |
| Debug endpoint | ✅ |
| OSS announce | ✅ **GO** after CI green on latest `dev` push |

*Next command for maintainer: `gh pr create` dev → main · monitor Actions tab for `SOTA Golden Gate + offline stress`.*
