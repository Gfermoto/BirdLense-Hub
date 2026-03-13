# План апгрейда BirdLense Hub

Исследование: март 2026.

---

## Безопасные изменения (выполнено)

| # | Действие | Статус |
|---|----------|--------|
| 1 | Обновить Docker base до `ultralytics/ultralytics:8.4.21` | ✅ |
| 2 | Исправление уязвимостей: npm (Vite 6, @tanstack/form 0.42), Python (requests, PyYAML, numpy 2) | ✅ |
| 3 | Конфликт numpy/opencv: lapx удалён, librosa 0.11, matplotlib 3.8 | ✅ |

---

## Дальнейшие шаги (не выполнено)

| # | Действие | Сложность | Риск |
|---|----------|-----------|------|
| 4 | Добавить `ultralytics` в processor/requirements.txt с версией | Низкая | Нет |
| 5 | EU-классификатор на YOLO11n-cls | В процессе | [COLAB_TRAINING.md](./COLAB_TRAINING.md) |
| 6 | Апгрейд React 19 (Vite 6 выполнен) | Средняя | Средний |

---

## Контекст

| | Было (текущее) | Стало / планируется |
|---|----------------|---------------------|
| **Ultralytics** | 8.4.21 (Docker base) | 8.4.21 |
| **Архитектура** | YOLOv8n | YOLO11n (переобучение) |
| **Детектор** | nabirds_yolov8n, NABirds+COCO+OIDv4 | — |
| **Классификатор** | YOLOv8n-cls (US) / YOLO11n-cls (EU) | NABirds / birds-525 + iNaturalist |

EU-модель: [COLAB_TRAINING.md](./COLAB_TRAINING.md).

---

## Дополнительные улучшения

- Full screen video (iOS) — средний приоритет
- Track trajectory overlay — низкий приоритет

---

См. также: [TESTING.md](./TESTING.md), [CONFIGURATION.md](./CONFIGURATION.md), [DEPLOYMENT.md](./DEPLOYMENT.md).
