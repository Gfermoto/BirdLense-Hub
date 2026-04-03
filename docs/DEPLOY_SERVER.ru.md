# Деплой BirdLense Hub на сервер (RU)

Короткая рабочая инструкция для прод-сервера без лишних шагов. Контекст и ссылки: [INSTALL.ru](./INSTALL.ru.md) § *Деплой на сервер*.

[English](./DEPLOY_SERVER.md)

## 1) Подготовка

- На локальной машине должен быть доступ к серверу по SSH.
- В корне репозитория создайте `scripts/deploy.local.sh` (можно копией из `scripts/deploy.local.sh.example`).
- Минимум нужно задать:
  - `DEPLOY_HOST` — SSH-адрес сервера
  - `DEPLOY_URL` — публичный URL хаба
  - при необходимости `DEPLOY_REMOTE_DIR`

Пример:

```bash
export DEPLOY_HOST="root@192.168.1.11"
export DEPLOY_URL="http://192.168.1.11:8085"
```

## 2) Деплой

Из корня репозитория:

```bash
make deploy
```

Что делает команда:

1. Синхронизирует код на сервер (без `app/data`, `site/`, локальных служебных каталогов).
2. На сервере выполняет `make stop`, `make build`, `make start`.
3. Проверяет health и базовую доступность API.

## 3) Проверка после деплоя

- Откройте UI: `http://<server>:8085`
- Проверьте health:

```bash
curl -sS http://<server>:8085/api/ui/health
```

Ожидается:

```json
{"status":"ok"}
```

## 4) Важно про данные

При стандартном деплое не перезаписываются:

- `app/data/` (записи и БД),
- `app/app_config/user_config.yaml` (пользовательские настройки).

## 5) Частые проблемы

- **`Password required` в system API**  
  Нужна авторизованная сессия (через UI или `verify-password` endpoint).
- **UI показывает старую версию**  
  Очистите кэш PWA/Service Worker в браузере и перезагрузите страницу.
- **Порт занят**  
  Проверьте значение `BIRDLENSE_PORT` и занятые порты на сервере.
