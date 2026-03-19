# Запись идёт как (CPU) при выборе Intel GPU

Если в логах процессора видно **«Starting FFmpeg recording ... (CPU)»**, хотя в настройках выбрано **«Кодирование записи: Intel GPU»**, значит в контейнере процессора **нет доступа к устройству VA-API** (`/dev/dri/renderD128`).

**Что сделать:** добавить проброс GPU-устройства в Docker. Скопируйте секцию `processor` из `app/docker-compose.intel.example.yml` в свой `docker-compose.override.yml` (или в основной compose на сервере):

```yaml
services:
  processor:
    devices:
      - /dev/dri/renderD128
```

После изменения compose выполните `docker compose up -d` (или `make stop && make start`) и при необходимости нажмите в UI «Перезапустить процессор».

В логах при отсутствии устройства будет предупреждение:  
`video.encoding=intel but /dev/dri/renderD128 not found — recording with CPU. Для GPU: добавьте devices в compose (см. docker-compose.intel.example.yml).`
