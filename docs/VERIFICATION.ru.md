# Верификация качества (операторам и мейнтейнерам)

Краткий журнал автоматических проверок перед возвратом к roadmap. Полный цикл — см. [CONTRIBUTING.ru.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.ru.md), [TESTING.ru.md](./TESTING.ru.md).

## 2026-05-14 — Пороговый runtime SLI gate (C2)

Для операционного alerting до/после деплоя:

```bash
make verify-runtime-sli
```

Gate читает `/metrics` и падает при нарушении порогов:
- `birdlense_processor_heartbeat_stale != 0` (по умолчанию строго `0`)
- `birdlense_processor_heartbeat_age_seconds > 240` (дефолтный максимум)
- доля медленных HTTP (`>1000ms`) выше `0.20` при выборке от `20` запросов

Пороги настраиваются через env:
`MAX_HEARTBEAT_AGE_SECONDS`, `MAX_HTTP_OVER_1000MS_RATIO`, `MIN_HTTP_SAMPLE_COUNT`, `REQUIRE_HEARTBEAT_STALE_ZERO`.

## 2026-05-02 — Постоянный ML proof gate (локально + хаб)

Чтобы исключить регрессию вида «сделали в контейнере, потом потерялось после деплоя», используйте единый воспроизводимый gate:

```bash
make ml-proof
```

Что проверяет `ml-proof`:
- `ml-proof-local`: синтетические/unit проверки артефактов Wave 5-12 (OpenVINO profile, decode benchmark, continuity/INT8/shadow/canary/full-rollout/action shortlist + runtime/selector тесты OpenVINO).
- `ml-proof-hub`: проверка реального деплоя через SSH:
  - `detector_continuity_report@v1` на живой SQLite,
  - `track_continuity_eval@v1`,
  - OpenVINO smoke внутри контейнера (`Core().available_devices`, инференс `intel:gpu` с steady latency),
  - итоговый отчёт `ml_proof_hub_report@v1` в `/tmp/bl_metrics/ml_proof_hub_report.v1.json`.

Gate падает (`exit != 0`), если не проходит любой из блоков: continuity, SLO track continuity, видимость GPU, порог latency на GPU или runtime-ошибка OpenVINO модели.

## 2026-05-02 — Fusion A/B gate (дубли + доля YOLO + дельта календаря)

Для проверки fusion-слоя после изменений policy:

```bash
make ml-fusion-ab-hub
```

Локально по снимку БД:

```bash
DB=app/data/db/birdlense.db OUT=/tmp/fusion_ab_report.v1.json make ml-fusion-ab-local
```

Артефакт `fusion_ab_report@v1` включает:
- долю провайдеров YOLO vs Frigate (`yolo_share_vs_frigate`),
- число дублей по записям `video` и по группам `video_species` в выбранном окне,
- долю пересечения generic `Bird` со специфичными видами,
- (опционально) дельту `encounters` vs `max_simultaneous` из `/api/ui/migration-calendar/compare`.

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

## 2026-05-02 — Wave 5 / #412 OpenVINO async+hints profile

Прогоните профили OpenVINO (device + hint + frame_step) на одном и том же наборе роликов и сохраните воспроизводимый артефакт:

```bash
python3 scripts/ml_openvino_async_profile.py \
  --videos-root app/data/recordings \
  --max-videos 3 \
  --out /tmp/ov_async_profile_report.v1.json
```

Артефакт `ov_async_profile_report@v1` содержит:
- строки по каждому профилю (status, runtime, fused/raw tracks, опционально recall из label_eval),
- `best_profile`, выбранный по минимальному mean runtime (при равенстве — recall, затем fused track count),
- итоговый флаг `ok=true`, если успешно завершился хотя бы один профиль.

## 2026-05-02 — Wave 6 / #413 decode path benchmark

Сравните decode/capture пути `opencv` и `ffmpeg_vaapi` на одном и том же replay-клипе:

```bash
python3 scripts/ml_decode_path_benchmark.py \
  --video app/data/file_test/sample.mp4 \
  --frames 300 \
  --out /tmp/decode_path_benchmark.v1.json
```

Артефакт `decode_path_benchmark@v1` содержит:
- строки бэкендов (`video_decode_resize_benchmark@v1`) для `opencv` и `ffmpeg_vaapi`,
- метрики fps, p95 frame delay и drop-rate delta,
- gate `drop_rate_improved_20pct` для проверки качества в Wave 1.

## 2026-05-02 — Wave 7 / #414 track continuity eval

Соберите SLO-вердикт continuity из `detector_continuity_report@v1`:

```bash
python3 scripts/ml_track_continuity_eval.py \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/track_continuity_eval.v1.json
```

Артефакт `track_continuity_eval@v1` содержит:
- `empty_track_with_detection_rate` (цель `<= 1.0%`),
- `track_emit_success_rate` (цель `>= 99.5%`),
- отдельные gate verdicts по метрикам и финальный `ok`.

## 2026-05-02 — Wave 8 / #415 INT8 candidate gate

Оцените INT8-кандидат против baseline по latency/quality/continuity порогам:

```bash
python3 scripts/ml_int8_candidate_eval.py \
  --baseline-report /tmp/baseline_report.json \
  --candidate-report /tmp/int8_candidate_report.json \
  --continuity-report /tmp/detector_continuity_report.v1.json \
  --out /tmp/int8_candidate_eval.v1.json
```

Артефакт `int8_candidate_eval@v1` содержит:
- ratio улучшения latency (цель `>= 20%`),
- деградацию качества в pp (цель `<= 1 pp`),
- статус continuity gate и `go_no_go`,
- rollback instructions для отката в production.

## 2026-05-02 — Wave 9 / #408 shadow rollout кандидата

Соберите gate-вердикт shadow (без влияния на user path) по минимум двум окнам:

```bash
python3 scripts/ml_shadow_rollout_report.py \
  --window-report /tmp/shadow_window_1.json \
  --window-report /tmp/shadow_window_2.json \
  --critical-incidents 0 \
  --out /tmp/shadow_rollout_report.v1.json
```

Артефакт `shadow_rollout_report@v1` содержит:
- disagreement-rate по окнам (из `label_eval` mismatch),
- счётчик критических runtime-инцидентов,
- gate verdict (`canary_ready` / `hold`) и финальный `ok`.

## 2026-05-02 — Wave 10 / #409 canary + auto-stop + rollback drill

Соберите артефакт canary/rollback:

```bash
python3 scripts/ml_canary_rollback_report.py \
  --baseline-sli /tmp/baseline_sli.json \
  --canary-sli /tmp/canary_sli.json \
  --rollback-sli /tmp/rollback_sli.json \
  --out /tmp/canary_rollback_report.v1.json
```

Артефакт `canary_rollback_report@v1` содержит:
- SLO-gates по latency/error для canary,
- gate восстановления baseline после rollback (`rollback_restores_baseline_sli`),
- auto-stop условие и практические rollback-шаги в playbook.

## 2026-05-02 — Wave 11 / #410 full rollout 100% + 72h watch

Соберите финальный отчёт 72h наблюдения и go/no-go:

```bash
python3 scripts/ml_full_rollout_watch_report.py \
  --before-report /tmp/baseline_report.json \
  --after-report /tmp/post_rollout_report.json \
  --watch-window /tmp/watch_d1.json \
  --watch-window /tmp/watch_d2.json \
  --watch-window /tmp/watch_d3.json \
  --out /tmp/full_rollout_watch_report.v1.json
```

Артефакт `full_rollout_watch_report@v1` содержит:
- дельты качества/latency до и после,
- SLI-проверки по окнам (p95/error/uptime),
- итоговый `go_no_go` + backlog следующей итерации detector.

## 2026-05-02 — Wave 12 / #406 shortlist action-моделей + MVP recipe

Соберите shortlist action-моделей и зафиксируйте MVP recipe:

```bash
python3 scripts/ml_action_model_shortlist.py \
  --min-dataset-clips 800 \
  --out /tmp/action_model_shortlist.v1.json
```

Артефакт `action_model_shortlist@v1` содержит:
- ранжированный shortlist action-моделей,
- выбранный MVP-кандидат,
- training recipe (`epochs/lr/sampler/loss/metrics`),
- риски domain shift + mitigation-план.

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
