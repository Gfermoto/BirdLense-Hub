---
name: "🔴 Chore: Migrate to Poetry Dependency Management"
about: Replace requirements.txt with Poetry
labels: ["chore", "dependencies"]
---

## Problem
Using `requirements.txt` leads to dependency hell.

## Goals
- [ ] Initialize `pyproject.toml` at root.
- [ ] Define dependency groups (web, processor, dev).
- [ ] Remove all `requirements.txt` files.
