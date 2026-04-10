---
name: "🟡 Refactor: Processor Clean Architecture"
about: Apply Clean Architecture to app/processor
labels: ["refactor", "processor", "medium-priority"]
---

## Problem
Modules like `detection_strategy.py` mix domain logic with infrastructure.

## Goals
- [ ] Separate Domain, Application, Infrastructure layers.
- [ ] Define interfaces for repositories.

## Definition of Done
- [ ] Направление зависимостей: Infrastructure → Application → Domain (без обратных импортов домена в инфраструктуру).
- [ ] Unit-тесты Domain/Application проходят без реальной ФС/сети (инфраструктура заменена заглушками).
- [ ] В `docs/` или в issue зафиксированы заметки по миграции для затронутых модулей.
