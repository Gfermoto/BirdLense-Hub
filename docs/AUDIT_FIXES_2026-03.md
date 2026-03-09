# Аудит и исправления (март 2026)

## 1. Погода — координаты с запятой

**Проблема:** OpenWeather API возвращает 400 при `lat=55,934` (запятая вместо точки).

**Исправления:**
- `app/web/util.py`: функция `_normalize_coord()` заменяет запятую на точку
- `app/ui/src/pages/Settings/SettingsForm.tsx`: при вводе координат автоматическая замена запятой на точку + подсказка

## 2. Камеры — stream proxy

**Проблема:** Прокси к Go2RTC возвращал пустой поток (нет MJPEG или недоступность frigate).

**Исправления:**
- `app/web/routes/ui_routes.py`: при ошибке или пустом ответе — redirect 302 на `/processor/live/{idx}` (fallback на processor)
- Дефолт `go2rtc_url` унифицирован с конфигом
- `docker-compose.server.yml`: `extra_hosts` для `host.docker.internal` (если Go2RTC на хосте — задать `GO2RTC_URL=http://host.docker.internal:1984`)

## 3. Записи — путь к data/recordings

**Проблема:** `RECORDINGS_DIR = "data/recordings"` не учитывал `DATA_DIR`, scan не находил файлы.

**Исправления:**
- `app/web/routes/ui_system_routes.py`: `_recordings_dir()` использует `DATA_DIR`
- `app/web/services/retention_service.py`: то же
- `app/docker-compose.base.yml`: `DATA_DIR=/app/data` для web
- Пути в БД: `data/recordings/YYYY/MM/DD/HHMMSS/video.mp4` (консистентно с processor)

## 4. Рекомендации

- **Погода:** Проверить координаты в Настройках — должны быть с точкой (55.934, 36.61)
- **Камеры:** Если потоки пустые — Go2RTC может не иметь MJPEG для этих stream. Добавить в go2rtc.yaml: `ffmpeg:stream_name#video=mjpeg`
- **Записи:** Нажать «Сканировать и импортировать» в System → Storage Management для импорта старых записей
