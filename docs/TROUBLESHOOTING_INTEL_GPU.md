# Запись идёт как (CPU) при выборе Intel GPU

**Как устроено:** приложение работает на любом хосте. В **Настройках → Видео → Кодирование записи** можно выбрать **CPU** или **Intel GPU**. Без дополнительных действий используется CPU; на хосте с Intel можно включить GPU через override.

Если в логах процессора видно **«Starting FFmpeg recording ... (CPU)»**, хотя в настройках выбрано **«Intel GPU»**, в контейнере **нет доступа к устройству VA-API** (`/dev/dri/renderD128`).

**Что сделать на хосте с Intel:** скопировать пример override (рядом с `docker-compose.yml`):

```bash
cp app/docker-compose.intel.example.yml app/docker-compose.override.yml
```

Затем `make stop && make start` (или `docker compose up -d`) и в настройках выбрать «Intel GPU». На странице System в блоке «Кодирование записи» должно появиться «Сейчас: Intel GPU (VA-API)».

В логах при отсутствии устройства будет предупреждение:  
`video.encoding=intel but /dev/dri/renderD128 not found — recording with CPU. Для GPU: добавьте devices в compose (см. docker-compose.intel.example.yml).`
