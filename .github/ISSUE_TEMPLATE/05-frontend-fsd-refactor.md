---
name: "🟡 Refactor: Frontend to Feature-Sliced Design"
about: Reorganize frontend src/ folder using FSD
labels: ["refactor", "frontend", "medium-priority"]
---

## Problem
Flat structure and massive `api.tsx` (34k lines).

## Goals
- [ ] Split src/ into app, pages, widgets, features, entities, shared.
- [ ] Move API logic to shared/api.
