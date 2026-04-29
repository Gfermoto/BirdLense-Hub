# План productization Re-ID (v1)

[English](./ML_REID_PRODUCTIZATION.md)

Родительская задача: [#390](https://github.com/Gfermoto/BirdLense-Hub/issues/390)

## Цель

Зафиксировать безопасную продуктовую логику `same-individual` до любой автоматизации merge.

## Decision policy

Re-ID должен выдавать ровно один статус:

- `suggest_same_individual`
- `inconclusive`
- `suggest_different_individual`

Auto-merge по умолчанию выключен. Merge только после подтверждения оператором.

## Входы policy

- cosine similarity
- совпадение/несовпадение вида
- camera id и временное окно
- свежесть эмбеддингов и совместимость схемы

## Правила безопасности

- запрет suggestions для cross-species merge
- усиленные пороги для cross-camera suggestions
- suppression при mixed/stale embedding schema
- cooldown окно по identity, чтобы исключить агрессивные повторные слияния

## Пороговая стратегия

- таблица порогов per-species (дефолт + override)
- опциональные per-camera offsets
- консервативный fallback для unknown/new species

## Метрики качества

- `precision_at_1`
- `false_merge_rate`
- `coverage` (доля событий с уверенной подсказкой)

Gate для включения в продукт:

- нет роста false merges относительно baseline
- precision/coverage растут или остаются в согласованном допуске

## Стратегия валидации

1. offline eval на фиксированном размеченном срезе
2. shadow режим в проде (без пользовательских merge-действий)
3. guarded UI suggestions с confirm/reject
4. опциональный A/B по операторской нагрузке и correction outcomes

## Минимальный UI-контур

- System/Library status card:
  - свежесть эмбеддингов
  - объём suggestions
  - reject/accept ratio
- review queue с audit trail решения

## Контроль рисков

- hard kill-switch потока Re-ID suggestions
- rollback в read-only summary mode
- полный export decision trace для incident review
