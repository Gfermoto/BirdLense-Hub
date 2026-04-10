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

## Definition of Done
- [ ] Крупные доменные куски вынесены из `ui_system_routes.py` в отдельные модули в `routes/` (или эквивалент по согласованной схеме).
- [ ] Повторно используемая логика живёт в `services/` без прямой зависимости от Flask `request` в ядре.
- [ ] Для mutating API есть явные схемы валидации (`schemas/` или Pydantic) и согласованные ответы об ошибках.
- [ ] CI зелёный; при изменении контрактов — обновлён OpenAPI/контрактные тесты.

## Proposed Structure
app/web/
├── routes/ (split by domain)
├── services/ (business logic)
└── schemas/ (DTOs)
