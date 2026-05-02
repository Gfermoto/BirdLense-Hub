# CV / ML roadmap — фазы внедрения

[English](./CV_ML_ROADMAP_PHASES.md)

Фиксирует **порядок работ** по эпику
[#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) и подзадачам после gap analysis. Дополняет
[CV_ML_PREP.ru.md](CV_ML_PREP.ru.md).

**Доска GitHub Project:** [BirdLense Hub — Roadmap](https://github.com/users/Gfermoto/projects/2/views/1) — держите поля Status / «Поток» вместе с таблицей ниже.

---

## Статус задач (GitHub)

Условные обозначения: **Готово в репо** — код/доки/скрипты на ветке `ML` готовы. **Ожидает веса** — задача не должна разрастаться новыми продукт-фичами; оставшийся gate — новые `.pt` / OpenVINO-артефакты, метрики и проверка на хабе. **Запланировано** — явно вынесено за текущий срез.

**Правило закрытия на 2026-04-29:** эпик [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367), подзадачи [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)–[#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375), [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383) и [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379) считаются дожатыми по repo-scope. Дальше не добавляем Grafana, ORT/TensorRT, продуктовую Re-ID галерею или отдельный action-recognition UI в этот пакет; они остаются будущими задачами. Текущий пакет ждёт только новые веса/экспорты и короткую операторскую валидацию на хабе.

| Issue | Статус | Комментарий |
|-------|--------|----------------|
| [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) Эпик | **Открыто (execution tracking)** | Repo-scope база доставлена; после аудита открытыми execution-задачами остаются [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379), [#389](https://github.com/Gfermoto/BirdLense-Hub/issues/389), [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392). |
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) Детектор train/ship | **Закрыто** | Контракт/скрипты/новые веса и OpenVINO-экспорт проверены на хабе. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) Active learning | **Готово в репо** | Manifest/schema/export/UI/API pool preview **готовы**; retrain automation не блокирует текущий пакет. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) Классификатор | **Закрыто** | Веса классификатора обновлены, отдельный выбор backend (`torch/openvino/auto`) внедрён. После prod-crash 2026-04-30 безопасный дефолт — `torch`; `auto/openvino` только после явного smoke. |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) Инференс-бэкенды | **Готово в репо** | torch + OpenVINO + кэш **готовы**; после прод-регрессии дефолтный runtime — `torch`; ORT/TensorRT не входят в текущий пакет. |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) Бенчмарки | **Готово в репо** | Скрипты + CI + docker-smoke + PSI drift gate **готовы**; итоговая таблица обновляется после новых весов. |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) Декод видео | **Готово в репо** | Скрипт замеров + FFmpeg VA-API backend + `video.capture_backend` + UI/API runtime status готовы; матрица платформ — часть операторской валидации. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) Re-ID | **Готово в репо** | Доки + DINOv2 offline embed/cosine/export + SQLite sidecar import + UI/API sidecar summary готовы; продуктовая галерея вынесена за текущий пакет. |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) Federated | **Готово в репо** | Игрушечная симуляция + threat model готовы; prod-channel не входит в текущий пакет. |
| [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379) Action recognition | **Открыто (execution-волна)** | Planning/research база есть, но issue снова активен для реального подбора/интеграции модели распознавания действий и прод-валидации. |
| [#388](https://github.com/Gfermoto/BirdLense-Hub/issues/388) CV/ML v2 Epic | **Закрыто (planning scope)** | v2-направления декомпозированы и формализованы, execution-гейты закреплены в дочерних задачах и документах. |
| [#389](https://github.com/Gfermoto/BirdLense-Hub/issues/389) DINOv2 production pipeline | **Открыто (execution pending)** | RFC/контракты/gates в репо есть, но issue остаётся открытым до полного выполнения execution-критериев из тела задачи. |
| [#390](https://github.com/Gfermoto/BirdLense-Hub/issues/390) Re-ID productization | **Закрыто (execution completed)** | Shadow sweep tooling и хабовые evidence доставлены: non-zero окна suggestions, proxy outcomes (`accepted_proxy`), pending-очередь закрыта по отслеживаемой паре, runtime-gates стабильны. |
| [#391](https://github.com/Gfermoto/BirdLense-Hub/issues/391) Benchmark robustness gates | **Закрыто** | Slice-gate скрипты/тесты/интеграция (`verify_benchmark_slice_gates.py`, Makefile, docs) внедрены. |
| [#392](https://github.com/Gfermoto/BirdLense-Hub/issues/392) Action dataset/labeling protocol | **Открыто (execution pending)** | Protocol/spec/gates зафиксированы, но issue остаётся открытым до выполнения dataset ops/training loop и валидации quality bar. |
| [#393](https://github.com/Gfermoto/BirdLense-Hub/issues/393) ML release train | **Закрыто** | Реестр моделей + release gates (`build/verify_model_registry_entry.py`, тесты, docs, Makefile) внедрены. |
| [#394](https://github.com/Gfermoto/BirdLense-Hub/issues/394) Data engine quality gates | **Закрыто** | Dataset quality + hard-negatives integrity gates (`verify_detector_dataset_quality.py`, `verify_hard_negatives_manifest.py`, тесты/docs) внедрены. |
| [#395](https://github.com/Gfermoto/BirdLense-Hub/issues/395) Classifier OpenVINO migration | **Закрыто** | Миграция классификатора на OpenVINO закрыта. |
| [#396](https://github.com/Gfermoto/BirdLense-Hub/issues/396) Product-slice v1 | **Закрыто** | Полный product-срез (nickname + Re-ID hints + action timeline) доставлен и подтверждён smoke/DoD. |
| [#397](https://github.com/Gfermoto/BirdLense-Hub/issues/397) Feedback learning loop | **Закрыто** | Feedback events + export API/script + status-contract наблюдаемости реализованы и проверены. |

*Обновляйте таблицу при закрытии вех или смене фокуса.*

---

## Коррекция порядка (не «сначала декод всего»)

Приоритеты в GitHub отличаются от наивного стека «сначала железный декод»:

| Тема | Issue | Приоритет в трекере | Замечание |
|------|-------|---------------------|-----------|
| Multi-backend inference | [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) | **High** | Абстракция и бэкенды раньше обязательного zero-copy decode. |
| HW video decode | [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) | Low–**Medium** | **Не блокирует** OpenVINO по тексту issue; сначала **замеры и доки**, потом HW path. |
| 3-class detector + контракт | [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) | **High** | Fail-fast имён классов при `processor.detector_weight_contract: enforce`. |
| Active learning | [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) | **High** | После стабильных точек экспорта из инференса. |
| Classifier roadmap | [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) | **High** | Параллельная дорожка. |
| Бенчмарки | [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) | Medium | Скрипты + CI. |
| Re-ID, federated | [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374), [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) | Medium / Low | Не блокируют детектор/классификатор. |

---

## Фазы

### Фаза 1 — фундамент (сделано)

- Общая нормализация меток: `detector_labels.py`.
- Пакет **`inference/`**: селектор бэкенда, загрузка torch/Ultralytics, контракт весов.
- Конфиг и env — см. таблицу в англ. версии документа (ключи те же).
- **Не** менять `go2rtc_stream_source.py` и логику захвата потока в фазе 1.

### Фаза 2 — бэкенды инференса + бенчмарки (база готова; CI/доки)

- OpenVINO для бинарника: `processor.models.binary_openvino`, `BIRDLENSE_BINARY_OPENVINO_PATH`, кэш [#371].
- Общий резолвер `inference/binary_paths.py`: provenance, model lineage, статус весов в UI.
- benchmark/compare + verify + эталон ``reference_smoke_report.json``; CI integration [#372].

### Фаза 3 — оптимизация видеопайплайна

- [#373] скрипт ``benchmark_video_decode_resize.py`` + таблица замеров [CV_ML_DECODE.ru.md](CV_ML_DECODE.ru.md).

### Фаза 4 — продукт и исследования

- [#369] схема пула + ``emit_pool_template.py`` + [ACTIVE_LEARNING.ru.md](ACTIVE_LEARNING.ru.md).
- [#370] точки расширения в ``_classify_crop``; продуктовые флаги — позже.
- [#374] [REID_ROADMAP.ru.md](REID_ROADMAP.ru.md) — **DINO / DINOv2**: Re-ID эмбеддинги и опционально **виды** / AL; на хабе целесообразен **один** backbone на два выхода при интеграции · [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383).
- [#375] ``simulate_fedavg.py`` + [FEDERATED_LEARNING.ru.md](FEDERATED_LEARNING.ru.md).
- [#389] DINOv2 production path: RFC [ML_DINOV2_PRODUCTION_PIPELINE.ru.md](ML_DINOV2_PRODUCTION_PIPELINE.ru.md) + **offline enforcement контракта** (поля JSONL → колонки SQLite → миграция на импорте → `reid_summary@v2.contract`) + phased rollout gates; execution DoD ещё открыт.
- [#390] Re-ID safety: RFC [ML_REID_PRODUCTIZATION.ru.md](ML_REID_PRODUCTIZATION.ru.md) + **YAML policy** (`processor.reid_*`) + **`video_reid_match@v2`** hints + E3 sweep execution evidence; issue закрыт по результатам валидации на хабе.
- [#392] Action dataset/labeling/training protocol: [ML_ACTION_RECOGNITION_PLAN.ru.md](ML_ACTION_RECOGNITION_PLAN.ru.md) + исполняемые protocol-gates; training execution DoD ещё открыт.

### Сводка по подзадачам (ветка ML)

См. таблицу в [CV_ML_ROADMAP_PHASES.md](CV_ML_ROADMAP_PHASES.md) (англ.) — что уже есть в репозитории по [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)–[#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375). По [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370): поля в трассе, CSV fusion export и шаги fusion-trace в UI; отдельная очередь ревью — позже.

### Эпик [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) — датасет 3-классового детектора (фаза 1)

- Локальная раскладка: ``scripts/datasets/binary/birds``, ``binary/rodent``, ``binary/background`` — см. [binary/README.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/datasets/binary/README.md).
- ``merge_datasets_three_class.py`` + ``make dataset-merge-three-class`` → ``dataset.yaml`` Bird/Rodent/Background в ``scripts/datasets/binary/merged/``; обучение/релиз — [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368).
- Опубликованные ZIP для операторского обучения: [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) (`detector_merged_balanced_20260429.zip`, `detector_merged_full_20260429.zip`), рекомендованный путь Stage A -> Stage B в [ML_DETECTOR_COLAB.ru.md](ML_DETECTOR_COLAB.ru.md).
- Опубликованный пакет весов детектора (YOLO + OpenVINO): [weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip).
- ``validate_yolo_labels.py`` + ``make dataset-validate-yolo-labels`` — быстрая проверка class id и bbox до Colab.
- Схема манифеста hard negatives и ``--manifest-out`` — см. [DATASETS.ru.md](./DATASETS.ru.md); **куда что пишется на диске** (`binary/merged` vs **`brg/`** vs имена ZIP на HF vs локальный `BirdLense_detector_brg_*.zip`) — начало [DATASETS.ru.md](./DATASETS.ru.md) (**Актуальные пути**).
- `video.capture_backend: auto|opencv|ffmpeg_vaapi` — путь захвата кадров для live inference; в `auto` VA-API включается только вместе с `video.encoding: intel` и рабочим `/dev/dri`, иначе OpenCV.

## API оператора без новых весов

Эти endpoints не требуют новых `.pt` / OpenVINO весов и нужны для разметки,
ревью и диагностики выката:

| Endpoint | Назначение |
|----------|------------|
| `GET /api/ui/videos/{video_id}/action-events` | Слабые метки поведения (#379): `arrival`, `departure`, `possible_feeding` из треков и изменения веса кормушки. |
| `GET /api/ui/videos/{video_id}/reid-match` | Product hints Re-ID (`video_reid_match@v2`) с policy-gate и candidate match без merge-операций. |
| `GET /api/ui/system/active-learning/pool-preview` | Кандидаты из review/uncertainty для active-learning pool (#369). |
| `GET /api/ui/system/reid/summary` | Read-only статус sidecar-таблицы `reid_embedding` (#374). |
| `GET /api/ui/system/feedback-loop/status` | Статус feedback-loop (#397): объём событий и состояние последнего экспорта. |
| `POST /api/ui/system/feedback-loop/export` | Экспорт feedback dataset (`feedback_learning_export@v1`) для retrain-пакета; поддерживает `dry_run`. |
| `GET /api/ui/system/ml-runtime` | Снимок ML/video runtime config (#373/#372). |

---

## Параллельная ветка `ML` (база восстановления — `dev`)

Инференс и бенчмарки сначала в **`ML`**. **`dev`** не трогаем как базу для отката рабочего хаба. **В `main` мержим только когда** система у вас реально проверена (деплой с ветки или иная явная валидация — одного зелёного CI недостаточно). До этого развиваем только **`ML`**; PR [#382](https://github.com/Gfermoto/BirdLense-Hub/pull/382) — черновик слияния, без обязательств по срокам.

---

## Ссылки

- Контракт подготовки: [CV_ML_PREP.ru.md](CV_ML_PREP.ru.md)
- **Репозиторий vs обучение снаружи:** [ML_OPERATOR_HANDOFF.ru.md](ML_OPERATOR_HANDOFF.ru.md)
- Детектор в Colab: [ML_DETECTOR_COLAB.ru.md](ML_DETECTOR_COLAB.ru.md)
- Эпик: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)
