# План апгрейда BirdLense

Исследование: март 2026.

---

## Безопасные изменения (выполнено)

| # | Действие | Статус |
|---|----------|--------|
| 1 | Удалить `google-genai` из requirements (web, processor) | ✅ |
| 2 | Обновить Docker base до `ultralytics/ultralytics:8.4.21` | ✅ |
| 3 | Убрать RPi-зависимости (RPi.GPIO, lgpio, gpiozero) | ✅ |

---

## Дальнейшие шаги (не выполнено)

| # | Действие | Сложность | Риск |
|---|----------|-----------|------|
| 4 | Добавить `ultralytics` в processor/requirements.txt с версией | Низкая | Нет |
| 5 | Переобучение моделей на YOLO11 | Высокая | Средний |
| 6 | Апгрейд React 19 + Vite 6 | Средняя | Средний |

---

## Контекст

- **Текущий Ultralytics:** 8.3.231 → 8.4.21 (Docker base)
- **YOLO11:** совместим с YOLOv8 по API; для полного использования — переобучение
- **google-genai:** не использовался (LLM Verifier удалён)
- **RPi:** проект на x86/Docker, Pi Camera и PIR отключены

---

## Дополнительные улучшения (из FORK_ANALYSIS)

- Full screen video (iOS) — средний приоритет
- Track trajectory overlay — низкий приоритет
