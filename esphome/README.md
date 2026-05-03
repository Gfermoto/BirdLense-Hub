# ESPHome — примеры прошивок для BirdLense Hub

Здесь лежат **примеры YAML** для устройств, которые стыкуются с хабом по MQTT (весы, реле кормушки и т.д.). Сборка и прошивка — стандартным [ESPHome](https://esphome.io/).

## Реле кормушки (`bird-feeder-relay.yaml`)

- ESP8266, плата **esp01_1m**: шаблонная кнопка включает реле на **5 с** (после задержки **500 ms**).
- Реле по умолчанию на **GPIO0** (для прошивки это неудобный пин); при возможности перенесите на другой GPIO и поправьте `switch` в YAML.
- Wi‑Fi и пароль OTA — из **`secrets.yaml`** (`wifi_ssid`, `wifi_password`, `ota_password`). Точка доступа при сбое: `Bird Feeder Fallback Hotspot` / `12345678` (смените в файле при необходимости).
- Интеграция с хабом: через **Home Assistant** (API ESPHome) или отдельный MQTT/автоматизация — этот конфиг только локальное управление реле и веб/API.

```bash
esphome compile esphome/bird-feeder-relay.yaml
esphome upload esphome/bird-feeder-relay.yaml
```

## Весы у кормушки (`bird-feeder-scale.yaml`)

- Шаблон в репозитории: **`bird-feeder-scale.yaml.example`** → скопируйте в **`bird-feeder-scale.yaml`** (он в `.gitignore`, с паролями не в git).
- В шаблоне можно использовать и **`api:`** (нативная интеграция ESPHome / Home Assistant), и **`mqtt:`**. Для BirdLense оставлены два сценария:
  - **`source: mqtt`** — рекомендовано для этой прошивки: хаб по умолчанию читает `birdlense/scale/weight`, `birdlense/scale/bird_present`, шлёт тару в `birdlense/scale/command`
  - **`source: esphome`** — хаб опрашивает само устройство по ESPHome Web API (`/sensor/<id>`, `/binary_sensor/<id>`, `/button/<id>/press`)
- Журнал дельты за клип и trigger записи по скачку веса в процессоре работают только в **MQTT**-режиме, см. `docs/CONFIGURATION.md`.
- **OTA** (как у реле): `ota_password` в `secrets.yaml`; при желании включите шифрование API (см. комментарий в YAML).
- Пины HX711: **`hx_dout_pin`**, **`hx_clk_pin`** в `substitutions` (по умолчанию GPIO27 / GPIO25).

### Секреты

В **`bird-feeder-scale.yaml`** Wi‑Fi и OTA задаются в **`substitutions`** (без `secrets.yaml`). Для реле и других конфигов по-прежнему можно использовать **`secrets.yaml.example`**.

### Сборка

```bash
esphome compile esphome/bird-feeder-scale.yaml
esphome upload esphome/bird-feeder-scale.yaml
```

**WSL + COM-порт:** проброс USB-UART с Windows — [`scripts/wsl-usb-forward.sh`](../scripts/wsl-usb-forward.sh) и [`scripts/wsl-usb-forward.ps1`](../scripts/wsl-usb-forward.ps1) (нужен [usbipd-win](https://learn.microsoft.com/windows/wsl/connect-usb)).

Путь к файлу укажите от каталога, где лежит ваш `secrets.yaml`, или скопируйте YAML в свой проект ESPHome.

### ESP32: цикл перезагрузок, `invalid segment length 0xffffffff`, «No bootable app»

Так бывает, если в слот **OTA (app0)** попала **битая или обрезанная** прошивка (оборвана OTA/USB, залит **не тот** `.bin`, сбой записи). Бутлоадер ESP-IDF 5.x читает образ и падает в цикл.

**Восстановление по USB (надёжно):**

1. Полное стирание флеша (порт подставьте свой, Windows — `COM3`):

   ```bash
   esptool.py --chip esp32 --port COM3 erase_flash
   ```

   (или `python -m esptool ...`, если так установлен esptool.)

2. Прошивка «с нуля» одной командой ESPHome (подтянет bootloader + factory + таблицу разделов):

   ```bash
   esphome run esphome/bird-feeder-scale.yaml --device COM3
   ```

Не заливайте вручную только `firmware.ota.bin` на `0x10000`, если не уверены в смещениях — для восстановления используйте **`esphome run`** или **`firmware.factory.bin`** с адреса **0x0** по инструкции ESPHome.

### Примечания

- Калибровку **HX711** (`calibrate_linear`) и пины **GPIO** подставьте под свою плату.
- Сущность температуры HA (`ha_temperature_entity`) замените на свою или временно отключите блок компенсации в лямбде, если HA не используется.

## LD2450 (микроволновый радар, ESP-IDF) — `ld2450-native-zones.yaml`

- Прошивка на базе [ESP32_LD2450](https://github.com/53l3cu5/ESP32_LD2450) / [веб-конфигуратор](https://53l3cu5.github.io/): нативный компонент `ld2450`, три HW-зоны, цели 1–3, кнопки записи конфигурации в радар.
- **Секреты:** в `secrets.yaml` добавьте `api_encryption_key`, `hotspot_password` (см. `secrets.yaml.example`) плюс стандартные `wifi_*`, `ota_password`.
- **BirdLense:** триггер записи можно взять из HA через MQTT binary или напрямую `triggers.motion_sensor` с `source: mqtt` / `source: esphome` — см. `app/app_config/default_config.yaml` и `app/processor/src/motion_detectors/factory.py`. Сейчас в конфиге один канал motion; объединение **радар ИЛИ PIR** удобнее сделать в ESPHome template + один MQTT topic или в HA automation (в YAML есть комментарий в конце файла).
- **Карта в HA:** пример `custom:plotly-graph` — `esphome/home-assistant/ld2450-plotly-graph.card.yaml` (подставьте реальные `entity_id` из Developer Tools → States).

### Выбранный сценарий PIR + радар для площадки (issue #376)

Для BirdLense-Hub принят **вариант 1**:

- в ESPHome/HA собираем `radar_has_target OR pir_gpio`,
- публикуем состояние в **один** MQTT topic (например, `birdlense/motion/ld2450_or_pir`),
- в хабе указываем `triggers.motion_sensor.source: mqtt` и этот же `mqtt_topic`.

Почему так:

- в хабе сейчас один канал `motion_sensor`, без мульти-топиков,
- OR на стороне ESPHome/HA даёт простой и предсказуемый контракт для `factory.py`.

```bash
esphome compile esphome/ld2450-native-zones.yaml
esphome upload esphome/ld2450-native-zones.yaml
```
