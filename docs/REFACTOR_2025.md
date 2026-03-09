# Рефакторинг BirdLense (март 2025)

## Что сделано

### 1. Один docker-compose.yml

Удалены:
- docker-compose.base.yml
- docker-compose.prod.yml
- docker-compose.dev.yml
- docker-compose.server.yml
- docker-compose.go2rtc.yml
- docker-compose.standalone.yml

Остался: **docker-compose.yml** — один контейнер birdlense.

### 2. Деплой

- **scripts/deploy.sh** — единственный скрипт деплоя
- **Критично:** `--exclude='app/data'` — данные на сервере не перезаписываются
- Раньше tar включал app/data/db — локальная БД перезаписывала серверную, записи «пропадали»

### 3. Восстановление записей

Если записи не видны после деплоя:

1. Видеофайлы должны быть на сервере: `./app/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4`
2. System → «Сканировать и импортировать» — добавит их в БД
3. Если БД была перезаписана старым деплоем — метаданные потеряны, но файлы на диске. Скан восстановит.

### 4. Makefile

| Команда | Описание |
|---------|----------|
| `make build` | Сборка |
| `make start` | Запуск |
| `make stop` | Остановка |
| `make logs` | Логи |
| `make deploy` | Деплой на 192.168.1.11 |

Из корня репозитория или из app/.

### 5. Структура

```
BirdLense/
├── app/
│   ├── docker-compose.yml   # единственный compose
│   ├── Dockerfile           # один образ
│   ├── Makefile
│   ├── app_config/
│   ├── data/                # НЕ синхронизируется при деплое
│   ├── processor/
│   ├── web/
│   ├── ui/
│   └── nginx/
├── scripts/
│   └── deploy.sh
└── Makefile                 # make deploy, make build, ...
```
