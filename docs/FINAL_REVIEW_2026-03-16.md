# Финальное ревью BirdLense Hub — 16 марта 2026

**Ветка:** dev  
**Цель:** подготовка к MR dev→main

---

## 1. Состояние после исправлений (повторное ревью)

### 1.1 Критичные — закрыты ✅

| # | Проблема | Файл | Статус |
|---|----------|------|--------|
| 1 | **FLASK_SECRET_KEY** fallback | `config.py` | ✅ В production требует env, иначе RuntimeError |
| 2 | **PROCESSOR_SECRET** пустой → доступ | `processor_routes.py` | ✅ В production блокирует при пустом |
| 3 | **SpectrogramPlayer** image.onload после unmount | `SpectrogramPlayer.tsx` | ✅ Добавлен `cancelled` в cleanup |

### 1.2 Высокий приоритет — закрыты ✅

| # | Проблема | Файл | Статус |
|---|----------|------|--------|
| 4 | Nginx path traversal: `%2e%2e` | `nginx/default.conf` | ✅ `\.\.|%2e%2e|%252e%252e` |
| 5 | N+1 в timeline/export | `ui_routes.py` | ✅ joinedload для video_species + video, species |
| 7 | `formatBytes(bytes < 0)` → NaN | `StorageManagement.tsx` | ✅ Проверка `!Number.isFinite(bytes) \|\| bytes < 0` |

### 1.3 Средний приоритет — закрыты ✅

| # | Проблема | Файл | Статус |
|---|----------|------|--------|
| 8 | Rate limiting verify-password | `util.py`, `ui_routes.py` | ✅ 5 failed/60 sec per IP |
| 9 | Валидация processor_routes | `processor_routes.py` | ✅ active_names (max 500, 100 chars), activity_data (64 KB) |
| 11 | Eager loading timeline | `ui_routes.py` | ✅ joinedload |

### 1.4 Wikipedia API

`util.py` уже проверяет `if not pages: return None, None` — IndexError не возникает.

---

## 2. Архитектура

- **Детекция:** two_stage (binary + YOLO11n-cls EU) / single_stage
- **Триггеры:** OpenCV, Frigate MQTT, MQTT binary, ESPHome
- **Интеграции:** Go2RTC, BirdNET MQTT, Telegram, Web Push, HA MQTT Discovery
- **Роли:** Admin, Contributor, Viewer

---

## 3. Тесты

| Тип | Команда | Статус |
|-----|---------|--------|
| Processor | `make test` | 12 passed |
| Web API | `make test-web` | 41 passed |
| E2E | `BASE_URL=... E2E_SETTINGS_PASSWORD=... make test-e2e` | 14 passed |

---

## 4. Чеклист перед MR

- [ ] `make test` — processor
- [ ] `make test-web` — web API
- [ ] `make test-e2e` — E2E (на https://birdlense.eyera.info)
- [ ] `make build` — сборка
- [ ] PROCESSOR_SECRET и FLASK_SECRET_KEY заданы на сервере
- [ ] CHANGELOG обновлён (если нужен релиз)
- [ ] Dependabot — проверить уязвимости в main

---

## 5. Сводка

| Категория | Оценка |
|-----------|--------|
| Структура | ✅ Понятная |
| Безопасность | ✅ Критичные фиксы внедрены |
| Тесты | ✅ Unit + API + E2E |
| Документация | ✅ 29 MD-файлов |
| **Готовность к merge** | **Готова** — все пункты ревью закрыты |
