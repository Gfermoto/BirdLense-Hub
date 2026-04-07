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
