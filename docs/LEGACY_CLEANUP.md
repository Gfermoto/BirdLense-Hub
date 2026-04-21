Legacy cleanup plan and actions performed

Summary
-------
This repository contains several legacy/backup copies and large binary artifacts.
The goal of the cleanup is to:

- Centralize legacy source copies under a single archival area.
- Remove tracked large binary weights from git history and use Releases instead.
- Keep reproducible fetch/install scripts and checksums in the repo.
- Avoid removing data or environment artefacts (recordings, venvs) from disk.

Actions already performed (by automation)
----------------------------------------
- Uploaded legacy compatibility weight `app/yolo11n.pt` to draft Release `weights/v1`.
- Added `CHECKSUMS` with SHA256 for `app/yolo11n.pt`.
- Reworked `scripts/fetch-processor-weights.sh` so the default path is the active two-stage runtime and the legacy asset is opt-in.
- Added fusion scaffold and unit tests (branch `feature/fusion-calibration`).

Current inventory
-----------------
| Item | Status | Notes |
|------|--------|-------|
| `app/yolo11n.pt` | keep-for-now | Compatibility-only asset. Use `scripts/fetch-processor-weights.sh --legacy-single-stage` when needed. |
| `app/processor/models/detection/weights/best.pt` | active | Runtime detector weight for the two-stage pipeline. |
| `app/processor/models/classification/weights/best.pt` | active | EU runtime classifier ([HF birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu)). |
| `app/processor/models/**/results.csv`, `args.yaml`, NCNN exports | removed | Training/export leftovers cleaned from the tree. |
| `datasets/birdlense_export/` | keep-for-now | Generated export directory. Leave until a dedicated data-retention decision is made. |
| `datasets/birdlense_ready_flat.zip` | keep-for-now | Regenerable artifact; do not delete without a fresh export/rebuild plan. |
| `app/data/`, `app/app_config/user_config.yaml` | keep | Runtime data and user config are intentionally preserved during deploy/cleanup. |
| `.pytest_cache`, `app/ui/dist`, `app/e2e/node_modules`, `processor.log*` | removed | Generated clutter removed from the repo checkout. |

Repeatable cleanup checklist
---------------------------
1. Run a reference search for any path you plan to delete.
2. Confirm the path is not used by runtime, tests, or docs.
3. If the item is regenerable, prefer removing it from the working tree and documenting the regeneration command.
4. If the item is ambiguous, mark it `keep-for-now` and split it into a follow-up issue.
5. After cleanup, run focused smoke tests for the runtime path and the export path.

Planned next steps (safe, reversible)
------------------------------------
1. Add CI smoke step that fetches weights via `scripts/fetch-processor-weights.sh` and runs inference on a control set.  
2. If more legacy source copies appear, move them into a dated archive instead of rediscovering them ad hoc.  
3. If a future cleanup decision is made for `datasets/birdlense_export/` or `datasets/birdlense_ready_flat.zip`, split it into a separate issue/PR.

Notes and safety
----------------
- No files with user recordings or databases will be deleted. Data in `app/data/` is preserved and not modified by these steps.  
- Any destructive history rewrite will require explicit authorization.

If you approve, I will prepare a PR that:
- Adds this file (this PR),
- Optionally moves `app/processor/src/legacy/*` → `app/processor/legacy_archive/2026-04-07/` (keeps all files),
- Runs full test suite and reports results in the PR.

