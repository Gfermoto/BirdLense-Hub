# Полное ревью BirdLense Hub — март 2026

Комплексный аудит по 4 направлениям: безопасность, UX/a11y, производительность, конфигурация.

---

## 1. Безопасность

### 1.1 Входные данные

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `ui_system_routes.py:74` | `lines` — нет проверки на отрицательные | `lines = max(1, min(...))` |
| `ui_system_routes.py:90` | `month` — нет проверки диапазона года/месяца | Проверять 2020–2030, месяц 1–12 |
| `ui_routes.py`, `processor_routes.py` | `request.json` без валидации схемы | Pydantic/Marshmallow |
| `processor_routes.py:114` | `active_names` — без ограничения длины/символов | Ограничить длину и набор символов |
| `processor_routes.py:164` | `activity_data = json.dumps(raw_data)` — без лимита размера | Лимит 64 KB |
| `ui_routes.py:251` | `name` в add_birdfood — без проверки | Ограничить длину 100, запретить опасные символы |
| `util.py:36` | `parse_utc_timestamp(param)` — при `param=None` TypeError | Проверка `if param is None` |

### 1.2 Path traversal

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `nginx/default.conf` | `\.\.` не ловит `%2e%2e`, `%252e%252e` | Добавить проверку encoded `..` |

### 1.3 XSS

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `api.tsx:25-28` | `resolveImageUrl` допускает `data:` URL | Запретить `data:` или ограничить MIME `image/*` |

### 1.4 Секреты и сравнение

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `config.py` | Дефолтный SECRET_KEY | В production требовать FLASK_SECRET_KEY |
| `util.py:113`, `processor_routes.py:43`, `ui_routes.py:744` | Сравнение паролей через `==` | `secrets.compare_digest()` |
| `processor_routes.py:37` | Пустой PROCESSOR_SECRET — доступ разрешён | В production требовать PROCESSOR_SECRET |

### 1.5 CORS, CSRF, rate limiting

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `app.py` | Нет CSRF для POST/PATCH/DELETE | Flask-WTF |
| `app.py` | Нет rate limiting | Flask-Limiter |
| `ui_routes.py:733` | verify-password — brute-force | 5 попыток в минуту |

### 1.6 Обработка ошибок

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `ui_routes.py:794`, `ui_system_routes.py:85`, `processor_routes.py:58` | `return {"error": str(e)}` — утечка деталей | Общее сообщение в ответе, детали в лог |

---

## 2. UX, доступность, мобильная версия

### 2.1 Мобильная версия

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **Navigation** | `"Live"` хардкод | `t('nav.liveView')` |
| **VideoPlayer** | Кнопки скорости < 44px touch target | `minWidth: 44`, `minHeight: 44` |
| **VisitCard, DetectedSpecies, IconButton** | `size="small"` ~36px | На xs: `size="medium"` или `minWidth: 44` |
| **FoodManagement** | Таблица — горизонтальный скролл без подсказки | `overflow-x: auto` + подсказка |
| **SettingsForm** | Длинная форма на мобильном | Collapsible секции или табы |
| **Live** | iframe 280px — не адаптивно | `minHeight: 200`, `height: min(50vh, 400)` |

### 2.2 Accessibility

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **Navigation** | `aria-label="menu"` не локализован | `aria-label={t('a11y.menu')}` |
| **LanguageSwitcher** | `aria-label="language"` | `aria-label={t('a11y.selectLanguage')}` |
| **VideoPlayer** | Play/Pause, Fullscreen без aria-label | Добавить aria-label |
| **App** | Нет skip link | «Skip to main content» |
| **Ошибки** | Без `role="alert"` | Alert с role="alert" |

### 2.3 Состояния загрузки и ошибки

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **Overview, Timeline, VideoDetails, BirdDirectory, SpeciesSummary** | Ошибка без retry | Кнопка «Повторить» + refetch |
| **Overview PDF** | `'...'` вместо loading | CircularProgress или t('common.loading') |
| **Все страницы** | Только CircularProgress | Skeleton для списков |

### 2.4 Пустые состояния

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **FoodManagement** | Пустая таблица — нет empty state | «Нет корма» с иконкой |

### 2.5 Навигация

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **VideoDetails, SpeciesSummary** | Нет кнопки «Назад» | ArrowBack + navigate(-1) |
| **VideoDetails, SpeciesSummary** | Нет breadcrumbs | Timeline → Video, Bird Directory → Species |

### 2.6 i18n

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **SettingsForm** | `'Permission denied'`, `'Failed'` хардкод | Вынести в i18n |
| **ProcessorLogs** | `'Failed to load logs'` | `system.logsLoadFailed` |
| **api.tsx** | `'Failed to dispense feed'`, `'Failed to restart'` | Вынести в i18n |
| **a11y** | aria-label хардкод | Секция `a11y.*` в locales |

### 2.7 PWA

| Компонент | Проблема | Рекомендация |
|-----------|----------|--------------|
| **sw.js** | API не кэшируется, offline — данные не загружаются | network-first или offline banner |
| **App** | Нет индикатора offline | useOnlineStatus + banner «Вы offline» |
| **sw.js** | Push: `'BirdLense'`, `'New detection'` хардкод | i18n или сохранённый язык |

---

## 3. Производительность и edge cases

### 3.1 N+1 запросы

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `ui_routes.py` | `get_video_details`, `get_unknowns` — lazy load | `joinedload(Video.video_species).joinedload(VideoSpecies.species)` |
| `util.py` | `format_visit_for_timeline` — lazy load Video | Eager load в запросе |
| `species_summary_service.py` | `recent_visits` — lazy load | joinedload для video_species, video, species |

### 3.2 Тяжёлые операции

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `ui_system_routes.py` | `get_storage_stats` — os.listdir + getsize в цикле | Кэш TTL 1–5 мин или фоновое сканирование |

### 3.3 Кэширование

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| Backend | `/species`, `/bird_families`, `/cameras` — без кэша | In-memory TTL 5–10 мин |

### 3.4 None/null

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `VideoDetails/index.tsx` | `!video` — передаётся undefined | Явная проверка + notFound |
| `DetectedSpecies.tsx` | `species` может быть undefined | `species ?? []` |
| `Overview/index.tsx` | `lastDetection.start_time` null → dayjs Invalid | `dayjs(x ?? undefined)`, isValid() |
| `BirdDirectory` | `speciesMap.get(id)!` — возможен undefined | Проверка или фильтрация |

### 3.5 Пустые массивы

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `DetectedSpecies.tsx` | `Math.min(...[])` = Infinity | `if (confidences.length === 0) return '—'` |
| `StorageManagement.tsx` | `formatBytes(bytes < 0)` → NaN | `if (bytes < 0) return '0 B'` |

### 3.6 Таймауты

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `api.tsx` | axios без timeout | `timeout: 30000` в defaults |
| `util.py` | WeatherFetcher requests без timeout | `timeout=10` |

### 3.7 Большие данные

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `ui_routes.py` | timeline `.all()` без limit | limit 500 + пагинация |
| `Timeline/index.tsx` | Рендер всех VisitCard | Виртуализация (react-window) |
| `Unknowns/index.tsx` | До 500 карточек | Виртуализация или пагинация |

### 3.8 Retry и offline

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `api.tsx` | Нет retry для axios | Interceptor: 2–3 попытки с backoff |
| App | Нет обработки offline | `navigator.onLine` + уведомление |

### 3.9 Memory leaks

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `SpectrogramPlayer.tsx` | `image.onload` — обновление после unmount | `cancelled` флаг в cleanup |

---

## 4. Конфигурация, документация, деплой

### 4.1 Конфигурация

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `default_config.yaml` | Нет `video.go2rtc_username/password`, `mqtt.username/password` | Добавить с пустыми значениями |
| `CONFIGURATION.md` | Не описаны env: MQTT_USERNAME, MOTION_ESPHOME_*, ESPHOME_FEEDER_*, HA_URL | Добавить в таблицу |
| `.env.example` | Нет HA_URL, DATABASE_URL | Добавить |

### 4.2 Документация

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `INSTALL.md` | Путь `configs/minimal.yaml` — неявно | «Выполнять из app/» |
| `INSTALL.md` vs `DEPLOYMENT.md` | BirdLense-Hub vs BirdLense | Унифицировать |
| `README.md` | Quick Start без docker compose up | Добавить команду или ссылку |
| `RECOVERY_CONFIG.md` | «user_config в git» — файл в .gitignore | Уточнить |
| `SECURITY.md` | «март 2025» | Обновить на 2026 |

### 4.3 Docker

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `Dockerfile` | USER не задан — root | Непривилегированный пользователь |
| `docker-compose.pull.yml` | Нет env_file: .env | Добавить |

### 4.4 Тесты

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `processor/tests/` | Нет тестов mqtt_aggregator, api, visit_processor | Добавить |
| `web/tests/` | Не покрыты ui_system_routes, processor_routes | Добавить |

### 4.5 Скрипты

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `restore-config.sh` | Нет проверки REMOTE_DIR | `[[ -z "$REMOTE_DIR" ]] && exit 1` |
| `verify-release.sh` | BASE_URL по умолчанию | Параметр или deploy.local.sh |
| `verify-release.sh` | E2E без npm ci | Добавить npm ci или проверку |

### 4.6 Логирование

| Файл | Проблема | Рекомендация |
|------|----------|--------------|
| `util.py:268` | `{e}` может содержать URL с токеном | Маскировать URL |
| `birdlense_mcp.py` | `print()` | Заменить на logger.info |

---

## Сводная таблица приоритетов

| Приоритет | Категория | Примеры |
|-----------|-----------|---------|
| **Высокий** | Безопасность | secrets.compare_digest, блокировка data: URL, rate limit verify-password |
| **Высокий** | UX | Retry при ошибках, touch targets 44px, aria-label VideoPlayer |
| **Высокий** | Производительность | N+1 eager loading, timeout axios, защита от undefined |
| **Средний** | Безопасность | Не раскрывать str(e), валидация month/lines |
| **Средний** | UX | Skeleton, breadcrumbs, empty state FoodManagement |
| **Средний** | Производительность | Кэш storage stats, виртуализация Timeline |
| **Низкий** | Конфиг/документация | Обновить CONFIGURATION.md, SECURITY.md, скрипты |

---

## Рекомендуемый порядок работ

1. **Безопасность (критично):** secrets.compare_digest, блокировка data: в resolveImageUrl
2. **UX (быстрые победы):** Retry на страницах с ошибками, t('nav.liveView') вместо "Live"
3. **Производительность:** Eager loading для timeline/video details, timeout в axios
4. **Защита от падений:** Проверки undefined в DetectedSpecies, VideoDetails, Overview
5. **Документация:** Обновить SECURITY.md, CONFIGURATION.md
6. **Долгосрочно:** CSRF, rate limiting, виртуализация списков, тесты
