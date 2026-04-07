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
- Uploaded canonical weight `app/yolo11n.pt` to draft Release `weights/v1`.
- Added `CHECKSUMS` with SHA256 for `app/yolo11n.pt`.
- Added `scripts/fetch-processor-weights.sh` to download+verify release assets.
- Added fusion scaffold and unit tests (branch `feature/fusion-calibration`).

Planned next steps (safe, reversible)
------------------------------------
1. Review files under `app/processor/src/legacy/` and move anything needed into a single `app/processor/legacy_archive/<date>/` if requested.  
2. Remove tracked large weight files from repository if still tracked (use git filter-repo / BFG if historical purge requested).  
3. Add CI smoke step that fetches weights via `scripts/fetch-processor-weights.sh` and runs inference on a control set.  
4. Create PR that applies the safe moves and runs full CI before merging.

Notes and safety
----------------
- No files with user recordings or databases will be deleted. Data in `app/data/` is preserved and not modified by these steps.  
- Any destructive history rewrite will require explicit authorization.

If you approve, I will prepare a PR that:
- Adds this file (this PR),
- Optionally moves `app/processor/src/legacy/*` → `app/processor/legacy_archive/2026-04-07/` (keeps all files),
- Runs full test suite and reports results in the PR.

