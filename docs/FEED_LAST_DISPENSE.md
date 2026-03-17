# Время последней выдачи корма

BirdLense Hub сохраняет время последней успешной выдачи корма в `data/feed_last_dispense.json`. Это работает для **MQTT** и **ESPHome** — время записывается на стороне Hub при успешном вызове dispense.

## Отображение

На Overview в карточке «Управление кормушкой» показывается строка «Последняя выдача: 17 мар, 14:30».

## ESPHome: время с устройства (опционально)

Стандартный REST API ESPHome **не отдаёт** время последнего нажатия кнопки/переключателя. Варианты:

1. **Текущая реализация** — Hub сохраняет время при успешном dispense. Работает для MQTT и ESPHome без изменений в прошивке.

2. **Template sensor в ESPHome** — при желании можно добавить в YAML глобальную переменную и обновлять её в `on_press` кнопки или `on_turn_on` switch. Для отображения в BirdLense Hub потребуется доработка API (опрос ESPHome или MQTT). См. [esphome.io](https://esphome.io) — globals, template sensor.

---

См. также: [CONFIGURATION.md](./CONFIGURATION.md) — раздел Feed.
