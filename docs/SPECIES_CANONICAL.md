# Канонические имена видов

Проект использует **Common name** (Eurasian Jay, Great Tit) как канонический формат, а не Scientific (Common).

---

## Зачем

- **Wikipedia** — картинки лучше подтягиваются по common name (Eurasian Jay), чем по scientific (Garrulus glandarius)
- **Xeno-canto** — голос ищется по common name
- **Единый вид** — Garrulus glandarius (Eurasian Jay) и Eurasian Jay сливаются в один

---

## Маппинг

### Конфиг `detection.species_mapping`

В `default_config.yaml` и `user_config.yaml`:

```yaml
detection:
  species_mapping:
    "Garrulus glandarius (Eurasian Jay)": "Eurasian Jay"
    "Parus major (Great Tit)": "Great Tit"
    # ... и т.д.
```

Все варианты → каноническое (Common name).

### Файл `app/web/seed/species_canonical_mapping.txt`

Формат: `variant|canonical`

Используется для:
- API «Объединить дубликаты видов» (System → Записи)
- Скрипт `scripts/merge_duplicate_species.py`

Добавляйте новые виды в этот файл для миграции существующих дубликатов.

---

## Объединение дубликатов

**Через UI:** System → Управление хранилищем → «Объединить дубликаты видов»

**Через CLI:**
```bash
cd app && python ../scripts/merge_duplicate_species.py
```

---

## Слияние датасетов

`scripts/datasets/merge_classification_datasets.py` теперь выводит папки в формате Common name (Eurasian_Jay, Great_Tit). Варианты Scientific (Common) автоматически сливаются в один класс.

---

См. также: [DETECTION_SOURCES.md](./DETECTION_SOURCES.md), [CONFIGURATION.md](./CONFIGURATION.md).
