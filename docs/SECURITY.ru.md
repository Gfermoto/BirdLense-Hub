# Анализ безопасности BirdLense Hub

[English](./SECURITY.md)

---

> Обновлено: март 2026

## Кратко

| Приоритет | Кол-во | Действия |
|-----------|--------|----------|
| Критический | 5 | Path traversal, аутентификация по умолчанию, секреты в API |
| Высокий | 8 | Хранение секретов, rate limiting, root в Docker |
| Средний | 9 | Таймаут сессии, CORS, зависимости |
| Низкий | 6 | Документация, миграции |

**Автоматизация:** в CI подключён **GitHub CodeQL** (Python + TypeScript UI). Подробнее — [CODEQL.ru.md](./CODEQL.ru.md).

---

## 1. Аутентификация и авторизация

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Критический** | По умолчанию API без входа. `/api/ui/*` доступны без проверки. | Для production: API key, JWT или reverse proxy с auth. |
| ~~**Критический**~~ **Исправлено** | Пустой `PROCESSOR_SECRET` — открытый Processor API. | В production блокируется; деплой пишет в `.env`. |
| **Критический** | MCP без токена, если пусты `mcp.token` и `MCP_TOKEN`. | Задавать `MCP_TOKEN` при `mcp.enabled=true`. |
| **Высокий** | Пароль настроек опционален — при пустом значении настройки и система не защищены. | Обязательный пароль в production. |
| ~~**Высокий**~~ **Исправлено** | Сессия `session.permanent = True`, нет idle-таймаута. | `general.session_idle_minutes` (по умолчанию 30; 0 — выкл.), см. [CONFIGURATION](./CONFIGURATION.ru.md). |
| **Средний** | `/api/ui/system/*` защищены только `settings_check_access()`. | Обеспечить обязательный `settings_password`. |

---

## 2. Секреты

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| ~~**Критический**~~ **Исправлено** | Дефолтный `FLASK_SECRET_KEY`. | В `BIRDLENSE_ENV=production` без ключа — RuntimeError; деплой пишет в `.env`. |
| ~~**Критический**~~ **Исправлено** | `GET /api/ui/settings` отдавал полный конфиг с секретами. | Маскирование `***`, placeholder при сохранении не затирает реальное значение. |
| **Высокий** | `user_config.yaml` в открытом виде: токены Telegram, MQTT, ключи API, пароли. | Хранить в env / secret manager, не в YAML. |
| **Высокий** | OpenAPI описывает чувствительные поля в схеме Settings. | `x-sensitive: true`, не светить в примерах. |
| **Средний** | `settings_password` в plain text. | Рассмотреть хеш (bcrypt/argon2). |
| **Низкий** | `.env` в `.gitignore`. | Оставить как есть. |

**Runbook для оператора:** [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) — перечень секретов, шаги ротации, проверка, откат, шаблон экстренной заметки ([issue #119](https://github.com/Gfermoto/BirdLense-Hub/issues/119)).

---

## 3. Path traversal (nginx)

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| ~~**Критический**~~ **Исправлено** | `location /data/` + `alias` — запрос `/data/../.env`. | Проверка `..` в URI → 403 во всех конфигах nginx. |
| **Высокий** | `/data/recordings/` без аутентификации; предсказуемые пути к `video.mp4`. | Выдача через API с auth или ограничение по IP. |

**Смягчение (на выбор при публичном доступе):** (1) **allowlist по IP** — отдельный `location ^~ /data/recordings/` с `allow`/`deny` (пример `app/nginx/examples/recordings_allowlist.conf.snippet`, [DEPLOY_SERVER.ru.md §8](./DEPLOY_SERVER.ru.md)); (2) **без прямой раздачи медиа** — снаружи только reverse proxy на `/api/…` и авторизованные stream-роуты; (3) **`auth_request`** к сессии Hub — сложнее, в образ по умолчанию не входит.

**Проверка:** `curl -I "http://YOUR_HOST:8085/data/../.env"` — при уязвимости будет 200.

---

## 4. API

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Высокий** | Нет rate limiting. | Flask-Limiter или аналог. |
| **Средний** | CORS: `supports_credentials: True`; allowlist из `CORS_LOCAL_DEV_ORIGINS` (дефолт — локальная разработка), `CORS_DEFAULT_ORIGINS`, `CORS_ORIGINS`. | Документировать для внешнего доступа; пустой `CORS_LOCAL_DEV_ORIGINS` — без встроенного локального набора. |
| **Средний** | Валидация входных данных частичная. | Схемы и лимиты для мутирующих эндпоинтов. |
| ~~**Средний**~~ **Исправлено** | `X-Real-IP` / `X-Forwarded-For` учитывались без trusted proxy. | Заголовки используются только при `TRUSTED_PROXY=1`; иначе rate-limit берёт `remote_addr`. |
| ~~**Средний**~~ **Исправлено** | Web Push подписка могла включить `web_push.enabled` без доступа к настройкам. | `POST /api/ui/push/subscribe` теперь требует `settings_check_access()`. |
| ~~**Высокий**~~ **Исправлено** | `webhook.url` мог указывать на loopback / private IP и использоваться как SSRF. | Разрешены только публичные `http`/`https` адреса; приватные диапазоны блокируются. |

---

## 5. База данных

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Низкий** | SQLAlchemy ORM, параметризованные запросы. | Продолжать ORM. |
| **Низкий** | SQLite в `app/data/db/`, не отдаётся напрямую. | Ок. |
| **Средний** | Миграции в `app.py` строками. | Рассмотреть Alembic. |

---

## 6. Файловая система

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Средний** | `scan_recordings` — проверки года и regex. | Убедиться, что путь остаётся внутри `recordings_dir()`. |
| **Низкий** | `processor_routes`: жёсткий `VIDEO_PATH_RE`. | Ок. |

---

## 7. Сеть

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Средний** | Порт 8085 снаружи. | Reverse proxy + TLS. |
| **Низкий** | Gunicorn/MCP на 127.0.0.1, наружу только nginx. | Ок. |

---

## 8. Зависимости

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Средний** | Нет автоматического аудита уязвимостей. | Периодически: `pip audit`, `npm audit`. |
| **Низкий** | Версии в requirements зафиксированы. | Обновлять по результатам аудита. |

---

## 8.1 Скан истории git на секреты (гигиена maintainer)

- Команда: `bash scripts/security/scan_git_history_secrets.sh`
- Инструмент: Gitleaks в Docker-образе `zricethezav/gitleaks:latest`
- Отчёт: `.artifacts/gitleaks-history.json`

Текущая база (март 2026): полный проход истории git завершён, **утечек не найдено**.

---

## 9. Docker

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| ~~**Высокий**~~ **Исправлено** | Процессы в контейнере под root. | Nginx/Gunicorn/processor под `birdlense` (uid **1000**); entrypoint при старте от root делает `chown` на примонтированные `./data` и `./app_config`. См. [INSTALL](./INSTALL.ru.md). |
| **Средний** | Тяжёлый базовый образ. | Multi-stage при необходимости. |
| **Низкий** | Без `--privileged`. | Не добавлять. |

---

## 10. Конфигурация

| Риск | Описание | Рекомендация |
|------|----------|--------------|
| **Высокий** | Чувствительные поля в `user_config.yaml`. | Env / secret manager. |
| **Низкий** | Деплой не затирает `user_config.yaml`. | Ок. |

---

## Быстрый чеклист для production

1. ~~Секреты~~ ✅ Деплой: `PROCESSOR_SECRET`, `FLASK_SECRET_KEY`, `BIRDLENSE_ENV=production`.
2. **Пароль настроек:** `general.settings_password`.
3. ~~Path traversal~~ ✅ Nginx блокирует `..`, `%2e%2e`; пути изображений проверяются.
4. **Ограничить** доступ к `/data/recordings/` (auth или IP).
5. ~~**Rate limiting**~~ ✅ `POST /api/ui/settings/verify-password`: **5** неудач за **60** с на IP клиента → **429** + `Retry-After`; успешный вход сбрасывает счётчик. IP из `X-Real-IP` / `X-Forwarded-For` за nginx — см. [ACCESS_CONTROL](./ACCESS_CONTROL.ru.md).
6. ~~**Docker:** не root в контейнере.~~ ✅ Процессы под uid 1000 (`birdlense`).
7. ~~Маскирование секретов~~ ✅ в `GET /api/ui/settings`.
8. **Ротация секретов:** [SECRETS_ROTATION.ru.md](./SECRETS_ROTATION.ru.md) (операции в проде).

---

## Контакты

Сообщить об уязвимости: GitHub Security Advisory или maintainers. См. [политику безопасности](./project/security-policy.md) в корне репозитория.
