# Подготовка BirdLense Hub к публичному open-source релизу

[English](./OPEN_SOURCE_PREP.md)

---

**Цель:** Привести документацию и код в порядок для международной публикации. Ничего лишнего — только инструкции для пользователей и контрибьюторов. Критичный фокус: безопасность и отсутствие утечек.

**Версия плана:** 1.0 | Март 2026

---

## 1. Резюме аудита

### 1.1 Документация (45+ .md файлов)

| Категория | Файлы | Статус |
|-----------|-------|--------|
| **Корневые** | README.md, README.ru.md, CHANGELOG.md, SECURITY.md | Нужна интернационализация (EN приоритет) |
| **docs/** | Гайды в `docs/` | EN — основной текст (`*.md`), RU — зеркала (`*.ru.md`); см. [I18N_STATUS](./I18N_STATUS.md) |
| **docs/archive/** | 8 файлов | Оставить как есть (история) |
| **Лишнее** | article/, scripts/datasets/README | Проверить релевантность |

### 1.2 Утечки и плейсхолдеры

В пользовательских доках — `YOUR_HOST`, `YOUR_SSH_HOST`, `YOUR_REMOTE_DIR`; путь на сервере по умолчанию для `deploy.sh` описан в [INSTALL.ru.md](./INSTALL.ru.md) (`DEPLOY_REMOTE_DIR`). Имя сервера в JSON MCP (`"birdlense"`) — идентификатор клиента, не SSH.

`app/.env.example` может содержать **примерные** частные IP. Правила только для Cursor (деплой) — локально, в репозиторий не коммитятся.

Периодически проверять: нет ли реальных токенов в примерах; `user_config.yaml.bak` — в `.gitignore` (задача 1.1 в фазе 1 ниже).

### 1.3 Безопасность (из docs/SECURITY.md)

- Секреты в user_config.yaml — документировать: хранить в env, не в YAML
- OpenAPI — `x-sensitive: true` для полей с токенами
- Rate limiting на verify-password — в backlog
- Пароль настроек — обязателен для production (документировать)

---

## 2. План работ (команда)

### Фаза 1: Безопасность и утечки (критично)

| # | Задача | Ответственный | Чеклист |
|---|--------|---------------|---------|
| 1.1 | Добавить в .gitignore: `user_config.yaml.bak`, `*.bak` в app_config | — | [x] |
| 1.2 | Заменить все `192.168.1.11`, `ssh birdlense`, `/root/BirdLense` на placeholders в docs | — | [x] |
| 1.3 | Проверить: нет ли реальных токенов, паролей, API keys в истории git | — | [ ] |
| 1.4 | Создать SECURITY.md (корень) — шаблон GitHub Security Policy (EN) | — | [x] |
| 1.5 | docs/SECURITY.md — перевести на EN или дублировать | — | [x] |

### Фаза 2: Документация — структура

| # | Задача | Ответственный | Чеклист |
|---|--------|---------------|---------|
| 2.1 | README.md — сделать основным на **английском**, кратким, без внутреннего жаргона | — | [x] |
| 2.2 | README.ru.md — локализованная версия; `app/README.md` + `app/README.ru.md`; `SHORT_DESCRIPTION*.md` | — | [x] |
| 2.3 | docs/README.md — навигация: EN приоритет, RU опционально | — | [x] |
| 2.4 | CONTRIBUTING.md — создать (как контрибьютить, code style, PR) | — | [x] |
| 2.5 | CODE_OF_CONDUCT.md — добавить (например, Contributor Covenant) | — | [x] |
| 2.6 | LICENSE — проверить, что указан корректно (MIT/Apache) | — | [ ] |

### Фаза 3: Документация — контент (Technical writer)

| # | Задача | Ответственный | Чеклист |
|---|--------|---------------|---------|
| 3.0 | **Ревизия archive/** — удалить лишнее, оставить только исторически значимое | Technical writer | [x] |
| 3.1 | Убрать «наш путь» — только инструкции. Проверить: SCENARIOS, INSTALL, CONFIGURATION | Technical writer | [x] |
| 3.2 | Унифицировать примеры: `YOUR_HOST`, `YOUR_BOT_TOKEN`, `your-api-key` | — | [x] |
| 3.3 | TRAINING.md, DATASETS.md — ссылки на gfermoto/* на Hugging Face: оставить (публичные репо) | — | [ ] |
| 3.4 | deploy.local.sh.example — уже generic (YOUR_HOST, YOUR_SERVER_IP) — OK | — | [ ] |
| 3.5 | Удалить или обобщить упоминания `deploy.local.sh` — «локальный файл с секретами» | — | [ ] |

### Фаза 4: Инфраструктура и финальный чек

| # | Задача | Ответственный | Чеклист |
|---|--------|---------------|---------|
| 4.1 | GitHub: включить Security Advisories, Dependabot | — | [x] |
| 4.2 | GitHub: описание репо, topics, website URL | — | [ ] |
| 4.3 | Проверка: `make test-web`, `make test-e2e` проходят | — | [ ] |
| 4.4 | Документация: все ссылки рабочие (внутренние, внешние) | — | [ ] |

---

## 3. Placeholders (единый стиль)

Использовать в документации вместо реальных значений:

| Тип | Placeholder | Пример |
|-----|-------------|--------|
| Хост/IP | `YOUR_HOST` или `localhost` | `http://YOUR_HOST:8085` |
| Путь на сервере | `YOUR_REMOTE_DIR` | `/opt/birdlense` |
| SSH host | `YOUR_SSH_HOST` | из `~/.ssh/config` |
| Токен/пароль | `your-secret-token`, `xxx` | `MCP_TOKEN=your-secret-token` |
| API key | `your-api-key` | `OPENWEATHER_API_KEY=your-api-key` |
| URL | `https://your-birdlense.example.com` | base_url для Telegram |

---

## 4. Файлы, которые НЕ должны попасть в репо

Проверить .gitignore:

```
app/app_config/user_config.yaml
app/app_config/user_config.yaml.bak   # ДОБАВИТЬ
scripts/deploy.local.sh
.env
*.pem
**/secrets/
**/*password*
**/*secret*
```

---

## 5. Роли в команде (рекомендация)

| Роль | Зона ответственности |
|------|----------------------|
| **Security** | Фаза 1, ревью секретов, .gitignore |
| **Technical writer** | Структура docs, согласование, удаление лишнего (в т.ч. archive), превращение «пути разработки» в инструкции |
| **Translator** | Перевод на EN/RU после ревизии |
| **DevOps** | Фаза 4, GitHub настройки, CI |
| **Maintainer** | Финальное ревью, релиз |

**Порядок работы с документацией:** ревизия (writer) → согласование → удаление лишнего → перевод (translator).

---

## 6. Критерии готовности к публикации

- [ ] Нет IP, hostname, путей, специфичных для текущего инсталла
- [ ] Нет токенов, паролей, API keys (даже замаскированных)
- [ ] README на английском — понятен международной аудитории
- [ ] CONTRIBUTING.md и CODE_OF_CONDUCT.md есть
- [ ] SECURITY.md (корень) — как сообщать об уязвимостях
- [ ] LICENSE корректен
- [ ] Все тесты проходят

---

## 7. Следующие шаги

1. ~~**Сделано:**~~ user_config.yaml.bak в .gitignore, placeholders, SECURITY (EN), CONTRIBUTING, CODE_OF_CONDUCT, README (EN)
2. **LICENSE:** Текущий LICENSE — CC BY-NC-ND для Docker-образа. При открытии исходников рассмотреть добавление лицензии для кода (MIT/Apache) или единую лицензию.
3. **Параллельно:** Назначить ответственных по фазам
4. **Перед релизом:** Полный прогон по критериям готовности
5. **Сайт документации:** MkDocs и workflow уже в репозитории — см. [Documentation.ru.md](./Documentation.ru.md) § *Статический сайт*; в настройках GitHub включить **Pages** (источник: GitHub Actions), публикация при push в **`main`**. Карта разделов: [SITE_MAP.ru.md](./SITE_MAP.ru.md).
