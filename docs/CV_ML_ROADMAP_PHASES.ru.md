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
| [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) Эпик | **Ожидает веса** | Phase‑1 в репо сделана; закрытие после новых весов и проверки `ML` на хабе. |
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) Детектор train/ship | **Ожидает веса** | Контракт и скрипты датасета **готовы**; обучение/калибровка/OV-экспорт — один пакет с новыми весами. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) Active learning | **Готово в репо** | Manifest/schema/export/UI/API pool preview **готовы**; retrain automation не блокирует текущий пакет. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) Классификатор | **Ожидает веса** | Энтропия/margin, `classifier_needs_review`, CSV fusion export, fusion-trace UI, Unknowns queue и AL preview готовы; finetune-метрики придут с новыми весами. |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) Инференс-бэкенды | **Готово в репо** | torch + OpenVINO + кэш **готовы**; ORT/TensorRT не входят в текущий пакет. |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) Бенчмарки | **Готово в репо** | Скрипты + CI + docker-smoke + PSI drift gate **готовы**; итоговая таблица обновляется после новых весов. |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) Декод видео | **Готово в репо** | Скрипт замеров + FFmpeg VA-API backend + `video.capture_backend` + UI/API runtime status готовы; матрица платформ — часть операторской валидации. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) Re-ID | **Готово в репо** | Доки + DINOv2 offline embed/cosine/export + SQLite sidecar import + UI/API sidecar summary готовы; продуктовая галерея вынесена за текущий пакет. |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) Federated | **Готово в репо** | Игрушечная симуляция + threat model готовы; prod-channel не входит в текущий пакет. |
| [#379](https://github.com/Gfermoto/BirdLense-Hub/issues/379) Action recognition | **Ожидает веса/данные** | Weightless weak-label API `arrival` / `departure` / `possible_feeding` готов; обучаемый action head ждёт размеченные данные/веса. |

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

### Сводка по подзадачам (ветка ML)

См. таблицу в [CV_ML_ROADMAP_PHASES.md](CV_ML_ROADMAP_PHASES.md) (англ.) — что уже есть в репозитории по [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368)–[#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375). По [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370): поля в трассе, CSV fusion export и шаги fusion-trace в UI; отдельная очередь ревью — позже.

### Эпик [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) — датасет 3-классового детектора (фаза 1)

- Локальная раскладка: ``scripts/datasets/binary/birds``, ``binary/rodent``, ``binary/background`` — см. [binary/README.md](https://github.com/Gfermoto/BirdLense-Hub/blob/main/scripts/datasets/binary/README.md).
- ``merge_datasets_three_class.py`` + ``make dataset-merge-three-class`` → ``dataset.yaml`` Bird/Rodent/Background в ``scripts/datasets/binary/merged/``; обучение/релиз — [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368).
- Опубликованные ZIP для операторского обучения: [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) (`detector_merged_balanced_20260429.zip`, `detector_merged_full_20260429.zip`), рекомендованный путь Stage A -> Stage B в [ML_DETECTOR_COLAB.ru.md](ML_DETECTOR_COLAB.ru.md).
- Опубликованный пакет весов детектора (YOLO + OpenVINO): [weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip).
- ``validate_yolo_labels.py`` + ``make dataset-validate-yolo-labels`` — быстрая проверка class id и bbox до Colab.
- Схема манифеста hard negatives и ``--manifest-out`` — см. [DATASETS.ru.md](DATASETS.ru.md).
- `video.capture_backend: auto|opencv|ffmpeg_vaapi` — путь захвата кадров для live inference; в `auto` VA-API включается только вместе с `video.encoding: intel` и рабочим `/dev/dri`, иначе OpenCV.

## API оператора без новых весов

Эти endpoints не требуют новых `.pt` / OpenVINO весов и нужны для разметки,
ревью и диагностики выката:

| Endpoint | Назначение |
|----------|------------|
| `GET /api/ui/videos/{video_id}/action-events` | Слабые метки поведения (#379): `arrival`, `departure`, `possible_feeding` из треков и изменения веса кормушки. |
| `GET /api/ui/system/active-learning/pool-preview` | Кандидаты из review/uncertainty для active-learning pool (#369). |
| `GET /api/ui/system/reid/summary` | Read-only статус sidecar-таблицы `reid_embedding` (#374). |
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
