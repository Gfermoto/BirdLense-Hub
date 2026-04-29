# CV / ML roadmap — фазы внедрения

[English](./CV_ML_ROADMAP_PHASES.md)

Фиксирует **порядок работ** по эпику
[#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) и подзадачам после gap analysis. Дополняет
[CV_ML_PREP.ru.md](CV_ML_PREP.ru.md).

**Доска GitHub Project:** [BirdLense Hub — Roadmap](https://github.com/users/Gfermoto/projects/2/views/1) — держите поля Status / «Поток» вместе с таблицей ниже.

---

## Статус задач (GitHub)

Условные обозначения: **Готово** — уже в репозитории (ветка `ML`). **В работе** — идёт сейчас (обучение весов, замеры на вашем железе, проверка деплоя). **Запланировано** — следующая фаза / не начато.

| Issue | Статус | Комментарий |
|-------|--------|----------------|
| [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) Эпик | **В работе** | Phase‑1 в репо сделана; **ваши** новые веса и при необходимости merge `ML`→`main` после проверки на хабе. |
| [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368) Детектор train/ship | **В работе** | Контракт и скрипты датасета **готовы** в репо; **обучение детектора** (Colab) — оператор. |
| [#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369) Active learning | **Готово** (репо фаза 1) / **Запланировано** (продукт) | Схема манифеста + шаблон + **`decision_trace_to_pool_manifest.py`** + SQLite **`export_pool_from_sqlite.py`** + доки **готовы**; расписание retrain — позже. |
| [#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370) Классификатор | **В работе** / **Запланировано** | Дообучение в Colab ([TRAINING.ru.md](./TRAINING.ru.md)) — оператор; **энтропия/margin и `classifier_needs_review`** — трасса, CSV fusion export, fusion-trace UI и Unknowns review queue; **DINO/DINOv2** — [REID_ROADMAP.ru.md](./REID_ROADMAP.ru.md); [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383). |
| [#371](https://github.com/Gfermoto/BirdLense-Hub/issues/371) Инференс-бэкенды | **Готово** / **Запланировано** | torch + OpenVINO + кэш **готовы**; ONNX Runtime / TensorRT — **запланировано**. |
| [#372](https://github.com/Gfermoto/BirdLense-Hub/issues/372) Бенчмарки | **Готово** / **Запланировано** | Скрипты + CI + docker-smoke + **PSI drift gate** **готовы**; Grafana — **запланировано**. |
| [#373](https://github.com/Gfermoto/BirdLense-Hub/issues/373) Декод видео | **В работе** | Скрипт замеров + FFmpeg VA-API backend + `video.capture_backend` **готовы**; **заполнение матрицы платформ** у вас — в работе. |
| [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) Re-ID | **В работе** / **Запланировано** | Доки + DINO; офлайн embed/cosine/export + SQLite sidecar import **готовы**; галерея/UI — **запланировано**. Один backbone на виды + Re-ID — см. REID. |
| [#375](https://github.com/Gfermoto/BirdLense-Hub/issues/375) Federated | **Готово** (исслед.) / **Запланировано** (прод) | Игрушечная симуляция + threat model **готовы**; прод-канал — **запланировано**. |

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
- Схема манифеста hard negatives и ``--manifest-out`` — см. [DATASETS.ru.md](DATASETS.ru.md).
- `video.capture_backend: auto|opencv|ffmpeg_vaapi` — путь захвата кадров для live inference; в `auto` VA-API включается только вместе с `video.encoding: intel` и рабочим `/dev/dri`, иначе OpenCV.

---

## Параллельная ветка `ML` (база восстановления — `dev`)

Инференс и бенчмарки сначала в **`ML`**. **`dev`** не трогаем как базу для отката рабочего хаба. **В `main` мержим только когда** система у вас реально проверена (деплой с ветки или иная явная валидация — одного зелёного CI недостаточно). До этого развиваем только **`ML`**; PR [#382](https://github.com/Gfermoto/BirdLense-Hub/pull/382) — черновик слияния, без обязательств по срокам.

---

## Ссылки

- Контракт подготовки: [CV_ML_PREP.ru.md](CV_ML_PREP.ru.md)
- **Репозиторий vs обучение снаружи:** [ML_OPERATOR_HANDOFF.ru.md](ML_OPERATOR_HANDOFF.ru.md)
- Детектор в Colab: [ML_DETECTOR_COLAB.ru.md](ML_DETECTOR_COLAB.ru.md)
- Эпик: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)
