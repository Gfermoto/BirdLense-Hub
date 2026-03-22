# Модель доступа и роли BirdLense Hub

[English](./ACCESS_CONTROL.md)

---

Проектирование уровней доступа для личного использования, сообщества и донатов.

---

## Текущее состояние

- **`settings_password`** — полный доступ (Admin): настройки, система, кормушка, перезапуск processor.
- **`contributor_password`** (опционально) — уровень Contributor: разметка, отчёты, iNaturalist, экспорт датасета; без настроек и системных операций.
- **Кормушка** — `POST /api/ui/feed/dispense` требует **Admin** (`settings_check_access()`): без разблокировки админским паролем — 403.
- **Коррекция видов** — `contributor_or_admin_access()` (Contributor или Admin).
- **Экспорт датасета** — Contributor или Admin (в зависимости от места в UI).

---

## Роли

| Роль | Описание | Целевая аудитория |
|------|----------|-------------------|
| **Viewer** | Только просмотр | Гости, семья, случайные посетители |
| **Contributor** | Разметка и отчёты | Волонтёры, помогающие с коррекцией видов |
| **Admin** | Полный доступ | Владелец установки |

---

## Матрица доступа

### Viewer (без входа)

| Действие | Доступ |
|----------|--------|
| Overview, Timeline, Live | ✅ |
| Просмотр видео, видов, каталога | ✅ |
| PDF-отчёт (скачать) | ✅ |
| Экспорт Timeline (CSV, JSON, eBird) | ✅ |
| Коррекция видов | ❌ |
| iNaturalist | ❌ |
| Кормушка | ❌ |
| Настройки | ❌ |
| Система (storage, purge, scan) | ❌ |
| Экспорт датасета | ❌ |

### Contributor (пароль помощника)

| Действие | Доступ |
|----------|--------|
| Всё из Viewer | ✅ |
| **Коррекция видов** (Unknowns, VideoDetails) | ✅ |
| **iNaturalist** (отправить кадр) | ✅ |
| **PDF-отчёт** | ✅ |
| **Экспорт Timeline** (CSV, JSON, eBird) | ✅ |
| **Экспорт датасета** | ✅ |
| Кормушка | ❌ |
| Настройки | ❌ |
| Система (purge, scan, restart) | ❌ |

### Admin (полный пароль)

| Действие | Доступ |
|----------|--------|
| Всё из Contributor | ✅ |
| **Кормушка** | ✅ |
| **Настройки** | ✅ |
| **Система** (storage, purge, scan, regenerate) | ✅ |
| **Restart processor** | ✅ |

---

## Конфигурация

```yaml
general:
  # Полный доступ (настройки, кормушка, система)
  settings_password: ""
  
  # Пароль помощника (только разметка и отчёты)
  # Пусто = те же права, что и settings_password (обратная совместимость)
  contributor_password: ""
```

**Логика:**
- `contributor_password` пусто → один пароль на всё (как сейчас).
- Оба заданы → два уровня: Contributor и Admin.
- Только `contributor_password` → Admin = Contributor (редкий кейс).

---

## Сессия

```python
session['access_role'] = 'admin' | 'contributor'  # после verify-password
session['settings_unlocked'] = True  # True для admin; для contributor часто False
```

**API verify-password:**
- `POST /api/ui/settings/verify-password` с `{ "password": "xxx" }`
- Ответ: `{ "ok": true, "role": "admin" }` или `{ "ok": true, "role": "contributor" }`
- Проверка: сначала `settings_password`, потом `contributor_password`.

### Ограничение частоты (rate limit)

Защита от перебора пароля на `verify-password`:

| Правило | Значение |
|---------|----------|
| Окно | **60** с (скользящее), **на IP клиента** |
| Неудачи | **5** неверных паролей подряд → далее **429** до истечения окна |
| HTTP | **429** + `{"ok": false, "error": "Too many attempts"}` + заголовок **`Retry-After: 60`** |
| Успех | Верный пароль **сбрасывает** счётчик неудач для этого IP |

**IP за nginx:** приложение берёт `X-Real-IP`, затем первый адрес из `X-Forwarded-For`, затем `remote_addr` (`client_ip_for_rate_limit()` в `util.py`). Для `/api` заголовки выставляет nginx (`nginx/standalone.conf.template`). Если Gunicorn доступен без доверенного reverse proxy, заголовки теоретически подделываемы — закройте порт 8000 от внешней сети.

Тесты: `TestVerifyPasswordRateLimit` в `app/web/tests/test_api.py` (`make test-web`).

---

## Кормушка (API)

`POST /api/ui/feed/dispense` вызывает `settings_check_access()`: доступ только у **Admin** (разблокировка основным паролем) или при валидном **MCP Bearer** токене, если настроено. Без паролей в конфиге — открыто (как и остальной UI).

---

## Будущее: донаты и сообщество

Сводно на уровне roadmap репозитория: [ROADMAP](./ROADMAP.ru.md) — раздел **«Кандидаты на будущее»**.

### Идеи для монетизации/поддержки

1. **Кнопка «Поддержать проект»** — при попытке Contributor получить Admin-функцию:
   - «Разблокировать кормушку? Поддержите проект» → ссылка на DonationAlerts, Boosty, Patreon.

2. **Страница «Сообщество»** (опционально):
   - Топ помощников за месяц (по числу исправленных детекций).
   - «Вы исправили 47 видов в марте — спасибо!»
   - Opt-in: показывать ник/имя в рейтинге.

3. **Донат = временный Admin:**
   - После доната — временный доступ к кормушке (например, 24 часа).
   - Или: донат разблокирует «гостевую кормушку» (1 раз в день).

4. **Бейджи для Contributors:**
   - «Помощник марта», «100 исправлений», «Первый в iNaturalist».
   - Отображать на странице Unknowns или в профиле (если будет).

### Технические заготовки

- `general.donate_url` — ссылка на страницу донатов.
- `general.community_stats_enabled` — показывать ли рейтинг помощников.
- В БД: `SpeciesVisit` или отдельная таблица `contributor_actions` для учёта (опционально).

---

## План внедрения

### Фаза 1 (минимальная) — выполнено
1. ✅ `feed/dispense` защищён `settings_check_access()`.
2. ✅ Документация модели доступа.

### Фаза 2 (роли) — выполнено
1. ✅ `contributor_password` в конфиге.
2. ✅ `verify-password` возвращает `role`.
3. ✅ `settings_check_access()` (admin), `contributor_or_admin_access()`.
4. ✅ UI: кормушка только при `isAdmin`; коррекция при `canEdit`.
5. ✅ Экспорт датасета в Timeline (доступен Contributor) и в Система (Admin).

### Фаза 3 (сообщество)
1. Страница «Сообщество» с благодарностями.
2. Ссылка на донаты при попытке Admin-действия от Contributor.
3. Опциональная статистика помощников.

---

## Безопасность

- Пароли в конфиге — plain text (как сейчас). Для продакшена: env или хеширование.
- Сессия: `role` хранится в Flask session (cookie). HTTPS обязателен.
- MCP, внутренние API — без изменений (отдельные токены).

---

См. также: [CONFIGURATION](./CONFIGURATION.ru.md), [API](./API.ru.md), [SECURITY](./SECURITY.md), [GLOSSARY](./GLOSSARY.ru.md).
