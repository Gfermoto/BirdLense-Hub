# Quality verification (operators & maintainers)

Short log of automated checks. Full cycle: [CONTRIBUTING.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), [TESTING.md](./TESTING.md).

Shared install/deploy smoke contract: `make verify` (or `scripts/verify-stack.sh --base-url ...`) checks `/api/ui/health`, `/api/ui/readiness`, and `/api/ui/status`.

## Offline fusion calibration

1. Export processor decision traces to CSV:

```bash
python3 scripts/export_fusion_training_data.py --out /tmp/fusion_traces.csv --source db
```

2. Evaluate calibration and selective-prediction metrics:

```bash
python3 scripts/eval_fusion_calibration.py --data /tmp/fusion_traces.csv --label-col valid_track_label --slice-field audio_evidence --slice-field decision_kind
```

3. If you have a trained fusion state, add `--model-path app/processor/models/fusion/fusion_state.pt`.

## 2026-04-02 — cleanup, backend tail removal, final polish

| Check | Result |
|-------|--------|
| `python -m pytest tests/test_api.py tests/test_species_registry.py -q` (`app/web`) | 96 passed |
| `npm run build` (`app/ui`) | OK |
| Public `GET /api/ui/health` | `200 {"status":"ok"}` |
| Public `GET /api/ui/status/debug` without auth | `403 {"error":"Password required"}` |
| Public `POST /api/ui/system/species-registry/enrich-metadata` | `404 Not Found` |
| Public `POST /api/ui/system/species-registry/repair-cards` | `404 Not Found` |
| Production catalog diagnostics | duplicate names `0`, classifier/catalog drift `0`, dataset drift `0` |

**Key fixes shipped in repo:**
- Removed dead legacy UI files that previously allowed old dangerous Library controls to survive in the tree.
- Closed the public debug surface behind settings access and removed unused sync species-registry maintenance routes.
- Synced TESTING / CONFIGURATION / ARCHITECTURE docs with the live route behavior and current UI model.

## 2026-03-29 — critical UI fix

| Check | Result |
|-------|--------|
| Prev/next recording on `/videos/:id` | Fixed `ReferenceError` (undefined `listReturnState`); see [CHANGELOG.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Manual smoke on hub:** open a clip from Timeline → prev/next → back returns to list; direct URL (no `state`) → stepping still works; browser back follows history.

**Not run here:** weekly Playwright E2E, full `make docs` unless MkDocs changed.

## 2026-04-01 — stabilization audit and safety hardening

| Check | Result |
|-------|--------|
| `python -m pytest app/web/tests/test_system_stabilization.py app/web/tests/test_security_hardening.py -q` | 12 passed |
| `python -m pytest app/web/tests/test_species_catalog_reconcile.py -q` | 4 passed |
| `npm run build` (`app/ui`) | OK |
| Production `storage/stats` after 2026-03-24 | Files present on disk through 2026-04-01 |
| Production `overview` / `timeline` after 2026-03-24 | No detections / visits after 2026-03-24; archive exists but ingest did not produce `video_species` / `species_visit` |

**Key fixes shipped in repo:**
- Library now reflects real archived recordings and no longer exposes dangerous maintenance flows.
- System maintenance supports honest preview/apply for orphan cleanup and visit time realignment.
- Production safety no longer allows empty-password bootstrap for settings/system access.
- Species merge preserves missing metadata on the surviving catalog row.
- Overview includes visits that overlap the selected day, including cross-midnight cases.

**Operator interpretation for the live hub:** if a day is highlighted in Library but empty in Overview or Timeline, recordings exist on disk but detections were not stored for that day. This is now easier to diagnose without mixing archive visibility and DB maintenance in one screen.
