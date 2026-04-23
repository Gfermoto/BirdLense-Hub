# Быстрый старт — BirdLense Hub

Самые короткие пути для трёх задач: поднять хаб, разрабатывать локально или проверить деплой.

[English](./QUICKSTART.md)

## 1. Запуск на одной машине

Из **корня репозитория** — **одна команда** (Docker, `app/.env`, стек, проверки health):

```bash
./install.sh
```

Готовый образ с ghcr.io (без локальной сборки образа):

```bash
./install.sh --pull
```

То же самое: `make install` или `make install-pull`.

Признаки успеха:

- UI открывается на `http://127.0.0.1:8085`
- Скрипт завершается после проверки `verify-stack`
- Страница настроек открывается, даже если камеры / MQTT ещё не настроены

## 2. Локальная разработка

Из **корня репозитория**:

```bash
cd app
make local
make verify
make test-web
```

Зависимости UI — **Node 22** в `app/ui/`. Подробности: [LOCAL_DEV](./LOCAL_DEV.ru.md).

### Полный CI локально (без push в GitHub)

Из **корня репозитория** (для шага UI нужен Node **≥ 22**):

```bash
make ci-local
```

Появятся **`.venv-ci`** / **`.venv-docs`** (в `.gitignore`). Образ Docker + Playwright smoke: `make ci-local-docker`. См. [CI_AND_QUALITY](./CI_AND_QUALITY.ru.md).

## 3. Деплой на сервер

Из **корня репозитория**:

```bash
make deploy
BASE_URL=https://ВАШ_ХОСТ make verify
```

После деплоя проверьте:

- `/api/ui/health` → `{"status":"ok"}`
- `/api/ui/readiness` → `"ready": true`
- `/api/ui/status` → `"web": "ok"`

Полный путь деплоя, SSH и данные — [INSTALL](./INSTALL.ru.md) и [DEPLOY_SERVER](./DEPLOY_SERVER.ru.md).
