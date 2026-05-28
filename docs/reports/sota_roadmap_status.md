# SOTA Roadmap — статус (#491)

Эпик: порядок областей 1→6. Закрытие области — код + тесты + полевой smoke.

## Область 1 — Конфигурация

| Issue | Статус | Примечание |
|-------|--------|------------|
| #492 SOTA-01 | **Done** | Pydantic `config_schema.py`, `config_guard.py`, strict processor + hub prod |
| SOTA-02…04 | Open | probe pipeline, migrations UI, settings gaps |

## Область 5 — Потоки

| Issue | Статус | Примечание |
|-------|--------|------------|
| #510 SOTA-19 | **Done** | gauges, `/diagnostics/backpressure`, runbook OOM 137 |
| #511 SOTA-20 | **Done** | `roi_crop.py`, `RoiCropRef` в classifier queue |
| #512 SOTA-21 | Done (prior) | jobs API + regen cancel |

## Область 6 — API/UI

| Issue | Статус |
|-------|--------|
| #513–#515 | Done (prior session) |

## Следующие открытые (вне этой волны)

- #507 калибровка confidence (скрипт `classifier_confusion_report.py` — старт)
- SOTA-02…04, SOTA-05…18 по приоритету полевых болей
