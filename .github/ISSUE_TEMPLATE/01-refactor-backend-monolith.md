---
name: "🔴 Refactor: Backend Monolith (ui_system_routes)"
about: Split the 96k line ui_system_routes.py into modular components
labels: ["refactor", "backend", "high-priority"]
---

## Problem
The file `app/web/routes/ui_system_routes.py` contains ~96,000 lines of code, violating the Single Responsibility Principle.

## Goals
- [ ] Extract business logic into `services/` layer.
- [ ] Split routes into domain-specific files.
- [ ] Introduce Pydantic schemas for validation.

## Proposed Structure
app/web/
├── routes/ (split by domain)
├── services/ (business logic)
└── schemas/ (DTOs)
