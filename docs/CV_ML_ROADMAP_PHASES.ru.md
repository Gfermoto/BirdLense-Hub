# CV / ML roadmap — фазы внедрения

[English](./CV_ML_ROADMAP_PHASES.md)

Фиксирует **порядок работ** по эпику
[#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) и подзадачам после gap analysis. Дополняет
[CV_ML_PREP.ru.md](CV_ML_PREP.ru.md).

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

- [#373] после замеров.

### Фаза 4 — продукт и исследования

- [#369], [#370], [#374], [#375].

---

## Параллельная ветка `ML` (база восстановления — `dev`)

Инференс и бенчмарки сначала в **`ML`**. **`dev`** не трогаем как базу для отката рабочего хаба. **В `main` мержим только когда** система у вас реально проверена (деплой с ветки или иная явная валидация — одного зелёного CI недостаточно). До этого развиваем только **`ML`**; PR [#382](https://github.com/Gfermoto/BirdLense-Hub/pull/382) — черновик слияния, без обязательств по срокам.

---

## Ссылки

- Контракт подготовки: [CV_ML_PREP.ru.md](CV_ML_PREP.ru.md)
- Эпик: [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367)
