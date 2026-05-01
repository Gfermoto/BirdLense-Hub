# CV/ML сценарии: A -> B

Цель: не терять покрытие по уже реализованным фичам и гонять их по единому сценарию:

- **A (локально, без поля):** быстрые/детерминированные проверки в репо.
- **B (хаб/площадка):** прогоны на реальных роликах и рабочем инстансе.

---

## Что покрываем

- Re-ID / DINO pipeline (контракт эмбеддингов, import, gate-проверки).
- Product hints и safety-gates (`video_reid_match@v2`, `reid_summary@v2`).
- Action labeling protocol (`video_action_events@v1` + gate).
- Feedback loop (`detection_feedback_event`, export/status API).
- Product-slice UX/contract (клички, action timeline, Re-ID hints).
- Интеграции, влияющие на CV/ML эксплуатацию (SFTP mirror/NAS, весы, радар).

---

## Этап A (локально)

Один вход:

```bash
./scripts/run-cv-ml-scenarios.sh
```

Быстрый режим (без расширенных web checks):

```bash
./scripts/run-cv-ml-scenarios.sh --quick
```

Что делает полный прогон:

1. Запускает `scripts/run-cv-ml-synthetic-checks.sh`.
2. Догоняет локальные web-проверки:
   - `web/tests/test_feedback_loop_service.py`
   - `web/tests/test_recordings_mirror_ui_api.py`
3. Печатает хабовый handoff-чеклист (этап B).

---

## Этап B (хаб/реальные ролики)

Запускать, когда вы готовы к стенду/площадке:

1. **Product-slice smoke**  
   `scripts/prod/smoke-cv-ml-no-events.sh`
2. **Re-ID gates** по snapshot payload  
   `make ml-verify-reid-gates ...`
3. **Action labeling gates**  
   `make ml-verify-action-labeling ...`  
   (быстрый детерминированный smoke по фикстурам: `make ml-verify-action-labeling-fixtures`)
4. **Feedback loop export dry-run**  
   `POST /api/ui/system/feedback-loop/export` с `dry_run=true`
5. **NAS mirror connectivity**  
   `POST /api/ui/storage/recordings-mirror/test`

Отдельные полевые issues-reminder (держим открытыми до реального прогона):

- [#243](https://github.com/Gfermoto/BirdLense-Hub/issues/243) — весы (ESPHome HX711)
- [#376](https://github.com/Gfermoto/BirdLense-Hub/issues/376) — радар LD2450
- [#350](https://github.com/Gfermoto/BirdLense-Hub/issues/350) — NAS/SFTP mirror

---

## Правило завершения

- Сначала всегда закрываем **A** (локальный детерминированный контроль).
- Потом идём в **B** (хаб/ролики/поле) и фиксируем результаты в issue-комментариях.
