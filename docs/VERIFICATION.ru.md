# Верификация качества (операторам и мейнтейнерам)

Краткий журнал автоматических проверок перед возвратом к roadmap. Полный цикл — см. [CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md), [TESTING.ru.md](./TESTING.ru.md).

## 2026-05-02 — Wave 1 / #402 detector-first baseline

Минимальный пакет для задач [#403](https://github.com/Gfermoto/BirdLense-Hub/issues/403) и [#411](https://github.com/Gfermoto/BirdLense-Hub/issues/411): отдельный отчёт continuity из SQLite и baseline protocol gate над benchmark JSON.

1. Снять continuity-артефакт на реальной БД:

```bash
python3 scripts/ml_detector_continuity_report.py --db app/data/db/birdlense.db --days 14 --out /tmp/detector_continuity_report.v1.json
```

2. Собрать baseline protocol (`benchmark_track_regen@v1` baseline vs candidate):

```bash
python3 scripts/ml_baseline_protocol.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/ml_baseline_protocol.v1.json
```

3. Gate считается пройденным, если в `ml_baseline_protocol@v1` поле `ok=true` и в `detector_continuity_report@v1` `track_gate_ok=true`, `crop_gate_ok=true`.

## 2026-05-02 — Wave 2 / #404 versioned eval dataset

Чтобы offline benchmark-gates (`#407`) были воспроизводимыми, фиксируйте eval-набор как версионированный артефакт:

```bash
python3 scripts/ml_build_eval_dataset.py \
  --videos-root app/data/recordings \
  --labels-json /tmp/gold_labels.json \
  --out-dir app/data/eval_datasets
```

Выход: `app/data/eval_datasets/<dataset_id>/manifest.json` (+ `gold_labels.json`, если передан labels JSON).  
`manifest.json` содержит `sha256` каждого ролика, размер, mtime и покрытие labels (`labels_coverage`), чтобы сравнения baseline/candidate использовали один и тот же frozen набор.

## 2026-05-02 — Wave 3 / #407 offline benchmark gate

Единый gate-раннер для detector-first миграции:

```bash
python3 scripts/ml_offline_benchmark_gate.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/offline_benchmark_gate.v1.json
```

Скрипт объединяет:
- `compare_benchmark_reports` (регрессии recall),
- `ml_baseline_protocol@v1` (quality + continuity),
- проверку достаточности выборки `label_eval`.

Финальный verdict — `offline_benchmark_gate@v1` поле `ok`.

## 2026-05-02 — Wave 4 / #405 detector shortlist + license/compliance

Генерация shortlist-артефакта по кандидатам:

```bash
python3 scripts/ml_detector_shortlist.py \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --offline-gate-report /tmp/offline_benchmark_gate.v1.json \
  --out /tmp/detector_shortlist_report.v1.json
```

Артефакт `detector_shortlist_report@v1` включает:
- таблицу кандидатов (quality/latency/openvino/license/risk),
- shortlist (2-3 кандидата, без `license.status=blocked`),
- `compliance_verdict`,
- отдельный `bird_only_verdict` (`viable` / `not_viable`).

## 2026-04-28 — синхронизация документации (roadmap, security, индекс CV/ML)

| Проверка | Результат |
|----------|-----------|
| `python3 scripts/check-docs-version.py` | OK (`VERSION` ↔ `mkdocs.yml`, `app/ui/package.json`, `app/web/openapi.yaml`) |
| `python3 scripts/check_site_map_meta_paths.py` | OK |
| `mkdocs build --strict` | OK |

**Что обновлено в репозитории:** ROADMAP EN/RU — метки backlog на апрель 2026, примечание про UI **v0.3.7+**, формулировка outcome реестра; SECURITY EN/RU — дата обновления / baseline gitleaks на апрель 2026; docs README EN/RU — строка с эпиком [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367); [CV_ML_PREP.ru.md](./CV_ML_PREP.ru.md) — связка prep с эпиком **#367**; [HUB_EPICS_TRACKER.ru.md](./HUB_EPICS_TRACKER.ru.md) — отдельная секция CV/ML.

## Offline-оценка fusion-калибровки

1. Выгрузить decision traces процессора в CSV:

```bash
python3 scripts/export_fusion_training_data.py --out /tmp/fusion_traces.csv --source db
```

2. Посчитать calibration-метрики и selective prediction:

```bash
python3 scripts/eval_fusion_calibration.py --data /tmp/fusion_traces.csv --label-col valid_track_label --slice-field audio_evidence --slice-field decision_kind
```

3. Если есть обученный fusion state, добавьте `--model-path app/processor/models/fusion/fusion_state.pt`.

## 2026-04-02 — cleanup, удаление backend-хвостов и финальная полировка

| Проверка | Результат |
|----------|-----------|
| `python -m pytest tests/test_api.py tests/test_species_registry.py -q` (`app/web`) | 96 passed |
| `npm run build` (`app/ui`) | OK |
| Public `GET /api/ui/health` | `200 {"status":"ok"}` |
| Public `GET /api/ui/status/debug` без авторизации | `403 {"error":"Password required"}` |
| Public `POST /api/ui/system/species-registry/enrich-metadata` | `404 Not Found` |
| Public `POST /api/ui/system/species-registry/repair-cards` | `404 Not Found` |
| Диагностика каталога на production | duplicate names `0`, classifier/catalog drift `0`, dataset drift `0` |

**Какие фиксы внесены в репозиторий:**
- Удалены мёртвые legacy UI-файлы, из-за которых старые опасные Library-контролы могли пережить рефакторинг в дереве проекта.
- Публичный debug surface закрыт за доступом к settings, а неиспользуемые sync routes species-registry удалены.
- TESTING / CONFIGURATION / ARCHITECTURE приведены к текущему поведению роутов и актуальной модели UI.

## 2026-03-29 — критический фикс UI

| Проверка | Результат |
|----------|-----------|
| Кнопки «предыдущая / следующая запись» на `/videos/:id` | Исправлен `ReferenceError` (`listReturnState` не был объявлён); см. [CHANGELOG.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md) [Unreleased] |
| `make test-web` (Docker, `app/`) | 100 passed |
| `npm run build` (`app/ui`) | OK |

**Рекомендуется вручную на стенде:** открыть ролик с Timeline → шаг prev/next → «Назад» возвращает в список; прямой заход по URL без `state` — навигация между роликами работает, «Назад» в браузере — по истории.

**Вне объёма автопрогона:** E2E Playwright по расписанию (ежедневный workflow; см. [TESTING.ru](./TESTING.ru.md) §1), полный `make docs` при изменении MkDocs.

## 2026-04-01 — аудит стабилизации и hardening

| Проверка | Результат |
|----------|-----------|
| `python -m pytest app/web/tests/test_system_stabilization.py app/web/tests/test_security_hardening.py -q` | 12 passed |
| `python -m pytest app/web/tests/test_species_catalog_reconcile.py -q` | 4 passed |
| `npm run build` (`app/ui`) | OK |
| Production `storage/stats` после 2026-03-24 | Файлы на диске есть вплоть до 2026-04-01 |
| Production `overview` / `timeline` после 2026-03-24 | Детекций и визитов после 2026-03-24 нет; архив есть, но ingest не создал `video_species` / `species_visit` |

**Какие фиксы внесены в репозиторий:**
- Library теперь показывает реальный архив записей и больше не выставляет опасные maintenance-потоки.
- Обслуживание БД в System поддерживает честный preview/apply для cleanup orphaned visits и realign visit times.
- В production больше нельзя неявно получить доступ к settings/system через «пустой пароль».
- Merge видов сохраняет недостающие metadata у итоговой карточки.
- Overview учитывает визиты, пересекающие выбранный день, включая переход через полночь.

**Как интерпретировать live-хаб:** если день подсвечен в Library, но пуст в Overview или Timeline, значит файлы записей на диске есть, а детекции за этот день не были сохранены в БД. После разведения Library и System это видно и диагностируется заметно проще.
