# ESPHome — примеры прошивок для BirdLense Hub

Здесь лежат **примеры YAML** для устройств, которые стыкуются с хабом по MQTT (весы, реле кормушки и т.д.). Сборка и прошивка — стандартным [ESPHome](https://esphome.io/).

## Весы у кормушки (`bird-feeder-scale.yaml`)

- Топики по умолчанию: **`birdlense/scale/weight`**, **`birdlense/scale/bird_present`**, **`birdlense/scale/command`** (см. `substitutions` в начале файла).
- В настройках BirdLense: **`integrations.scales.mqtt_topic_prefix: birdlense/scale`**, **`unit: g`**, поле **MQTT topic для веса** оставить пустым (или задать полный топик вручную).
- Секреты вынесите в **`secrets.yaml`** рядом с конфигом (см. пример ниже).

### Секреты

Шаблон: **`secrets.yaml.example`**. Скопируйте в `secrets.yaml` в том же каталоге, куда кладёте конфиг при сборке (или рядом с `bird-feeder-scale.yaml`), и заполните Wi‑Fi и MQTT.

### Сборка

```bash
esphome compile esphome/bird-feeder-scale.yaml
esphome upload esphome/bird-feeder-scale.yaml
```

Путь к файлу укажите от каталога, где лежит ваш `secrets.yaml`, или скопируйте YAML в свой проект ESPHome.

### Примечания

- Калибровку **HX711** (`calibrate_linear`) и пины **GPIO** подставьте под свою плату.
- Сущность температуры HA (`ha_temperature_entity`) замените на свою или временно отключите блок компенсации в лямбде, если HA не используется.
