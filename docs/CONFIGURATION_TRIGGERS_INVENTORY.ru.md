# Инвентаризация конфигурации — триггеры, merge, Frigate/MQTT

[English](./CONFIGURATION_TRIGGERS_INVENTORY.md)

Живой список, чтобы не путать **legacy-ключи**, dotted YAML и то, что видит UI после merge. Полный справочник ключей — [CONFIGURATION](./CONFIGURATION.ru.md).

## Топовые пересечения

| Тема | Ключи / где в UI | Заметки |
|------|------------------|---------|
| Источник движения | `motion.source`; блоки в **Настройки → Захват и кормушка** | Процессор читает итоговый merge; сверяйте audit и YAML export. |
| Frigate без YOLO | `detection.frigate_standalone_when_no_yolo` | Режим standalone при осознанном отключении YOLO + Frigate/MQTT. Симптомы в логах — см. [RUNBOOKS](./RUNBOOKS.ru.md) и **System → config audit**. |
| Bool из YAML | строка `"false"` vs boolean `false` | Смотрите тип в экспорте; бэкенд нормализует через helpers вида `_bool_config`. |

## Согласованность

- Логика fusion в коде процессора и текст в **config audit** / **Settings → Processor** должны совпадать по смыслу.
- RFC на единую схему триггеров — отдельное ишью; здесь только карта и ссылки.

Трекинг: [BirdLense-Hub#329](https://github.com/Gfermoto/BirdLense-Hub/issues/329).
