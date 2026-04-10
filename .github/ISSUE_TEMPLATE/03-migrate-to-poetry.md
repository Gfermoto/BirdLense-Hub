---
name: "🔴 Chore: Migrate to Poetry Dependency Management"
about: Replace requirements.txt with Poetry
labels: ["chore", "dependencies"]
---

## Problem
Using `requirements.txt` complicates reproducible installs and environment splits:
- No lock file for identical CI vs developer installs
- Harder to separate web / processor / dev dependencies cleanly
- Version bumps often surface conflicts and transitive dependency surprises

## Goals
- [ ] Initialize `pyproject.toml` at root.
- [ ] Define dependency groups (web, processor, dev).
- [ ] Configure Poetry (virtualenvs, cache) and migrate version pins from current requirements.
- [ ] Generate and commit `poetry.lock`.
- [ ] Update GitHub Actions to use `poetry install` (or equivalent).
- [ ] Verify clean install and full CI test run.
- [ ] Update README/CONTRIBUTING for developers.
- [ ] Remove all `requirements.txt` files.
