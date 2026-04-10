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

## Definition of Done
- [ ] В репозитории видно целевое дерево FSD (каталоги `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/` — или согласованный вариант).
- [ ] Монолитный `api.tsx` декомпозирован: клиенты API лежат в `shared/api` (или `shared/api/*`) по доменным модулям.
- [ ] `npm run build` и линтер в CI проходят; нет регрессии по основным пользовательским сценариям (smoke/E2E по наличию).
