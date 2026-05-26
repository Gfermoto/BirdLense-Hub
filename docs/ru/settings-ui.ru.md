# Настройки UI — процессор (SOTA-04 / #495)

Оператор может менять критичные `processor.*` и `video.detect_fps` без правки `user_config.yaml` по SSH.

## Где в UI

| Раздел | Поля |
|--------|------|
| **Процессор → Детектор** | `binary_imgsz`, `inference_lores_px`, pipeline, **геометрия потока**, **track regen** |
| **Процессор (расширенный)** | inference backend/device, **OpenVINO**, **MOG2** |
| **Захват и кормушка → Запись** | разрешение, **`video.detect_fps`** (0 = авто/probe) |

## Дефолты в форме

Пустые поля в форме показывают значения из `app/app_config/default_config.yaml` через `processorFieldDefaults.ts` (не магические 640).

Типичная площадка Trapper: `binary_imgsz` / lores **704**, detect substream **704×576**.

## Предупреждения (SOTA-03)

После сохранения настроек UI показывает Alert, если в YAML остались deprecated keys (`_settings_warnings` в ответе PATCH).

Полный аудит: **Система → Аудит конфигурации** (`GET /api/ui/system/config-audit`).

## Проверка

```bash
cd app/ui && npm run typecheck && npm run test -- processorFieldDefaults
```

После изменения inference/OpenVINO — **перезапуск процессора** (кнопка в Настройках или System).
