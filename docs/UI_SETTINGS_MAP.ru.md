# Карта настроек в UI (Library → Settings → System)

[English](./UI_SETTINGS_MAP.md)

Одна страница: **где в интерфейсе** меняется зона ответственности. Где есть якоря — указаны hash-ссылки.

| Зона | Маршрут / вход | Что настраивается |
|------|----------------|-------------------|
| **Library** | `/timeline` | Клипы, ревью, экспорт — не глобальный стек. |
| **Settings** (админ) | `/settings` | YAML хаба и процессора; секции — аккордеоны: **Общее**, **Подключения**, **Захват и кормушка**, **Интеграции**, **Процессор и детекция** и др. |
| **Процессор** | `/settings#processor-weights` или `/settings#processor-models` | Открывает аккордеон процессора и прокручивает к весам/моделям. |
| **System** | `/system` | Readiness, **config audit**, ремонт каталога, статус весов, диагностика. |
| **Live** | `/live` | Потоки и оверлеи — рантайм. |
| **Миграция / виды** | `/migration-calendar` | Сравнение с регионом и сценарии из Overview. |

## Ссылки

- Короткие ворота релиза: [Definition of Done](./DEFINITION_OF_DONE.ru.md).
- Runbook по VPS и логам: [RUNBOOKS](./RUNBOOKS.ru.md).
- Ключи конфига: [CONFIGURATION](./CONFIGURATION.ru.md).
- Инвентаризация триггеров / Frigate: [CONFIGURATION_TRIGGERS_INVENTORY](./CONFIGURATION_TRIGGERS_INVENTORY.ru.md).

Трекинг: [BirdLense-Hub#325](https://github.com/Gfermoto/BirdLense-Hub/issues/325).
