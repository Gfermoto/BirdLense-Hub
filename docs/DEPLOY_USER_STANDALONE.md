# Развёртывание из готового образа (без сборки)

Пользователь может развернуть BirdLense **без клонирования репозитория и сборки** — только образ и конфиг.

## Быстрый старт

```bash
# 1. Каталог и конфиг
mkdir -p birdlense-app && cd birdlense-app
mkdir -p data/recordings data/db app_config

# 2. Файл окружения (скопировать из репозитория app/.env.example или создать вручную)
# Минимум: PROCESSOR_SECRET, FLASK_SECRET_KEY. Остальное — в UI или позже.
# Сгенерировать секреты: openssl rand -hex 16
cat > .env << 'EOF'
PROCESSOR_SECRET=ваш_секрет_16_символов
FLASK_SECRET_KEY=ваш_секрет_32_символа
BIRDLENSE_ENV=production
# GO2RTC_URL=http://IP_go2rtc:1984
# MQTT_BROKER=mqtt.local
# MQTT_PASSWORD=...
EOF
# Замените значения на свои (или сгенерируйте: openssl rand -hex 16)

# 3. Compose для образа (один файл — см. ниже или скачать из репо)
# Сохранить как docker-compose.yml или использовать -f docker-compose.image.yml

# 4. Запуск
docker compose -f docker-compose.image.yml up -d
# или если переименовали в docker-compose.yml:
# docker compose up -d

# 5. Открыть UI
# http://localhost:8085  (или BIRDLENSE_PORT из .env)
```

## Откуда брать образ

- **GitHub Container Registry:** `ghcr.io/gfermoto/birdlense-hub:latest` (если настроена публикация из репозитория).
- **Свой registry:** собрать образ один раз (`cd app && docker build -t myreg/birdlense-hub:latest .`), запушить, в `.env` указать `BIRDLENSE_IMAGE=myreg/birdlense-hub:latest`.

При использовании `docker-compose.image.yml` из репозитория по умолчанию подставляется `BIRDLENSE_IMAGE=ghcr.io/gfermoto/birdlense-hub:latest`. Переопределение: `export BIRDLENSE_IMAGE=myreg/birdlense:1.0`.

## Минимальный набор файлов у пользователя

В каталоге `birdlense-app/` достаточно:

| Файл / каталог | Назначение |
|----------------|------------|
| `docker-compose.image.yml` | Compose с `image:` (скопировать из репо `app/docker-compose.image.yml`) |
| `.env` | Секреты и переменные (PROCESSOR_SECRET, FLASK_SECRET_KEY, GO2RTC_URL, MQTT_* и т.д.) |
| `app_config/` | Пустой или с `default_config.yaml`; после первого запуска появится `user_config.yaml` |
| `data/` | Записи и БД создаются автоматически |

Каталоги `data/recordings`, `data/db`, `app_config` нужно создать до первого запуска (или дать права на запись контейнеру).

## Intel GPU

На хосте с Intel (NUC, Celeron и т.д.) — один раз скопировать override:

```bash
cp docker-compose.intel.example.yml docker-compose.override.yml
docker compose -f docker-compose.image.yml up -d
```

Override подмешивается к основному compose. В настройках Hub выбрать «Кодирование записи: Intel GPU».

## Публикация образа (для разработчика)

Чтобы пользователи могли `docker pull` образ:

1. **Вручную:** в каталоге `app/`:  
   `docker build -t ghcr.io/gfermoto/birdlense-hub:latest .`  
   Затем `docker push ghcr.io/gfermoto/birdlense-hub:latest` (нужен логин в ghcr.io).

2. **CI (GitHub Actions):** добавить job в `.github/workflows/`: на push в `main` или по тегу — build и push в ghcr.io. Пример есть в документации GitHub Container Registry.

После публикации пользователю достаточно скопировать `docker-compose.image.yml` и `.env.example`, заполнить `.env` и выполнить `docker compose -f docker-compose.image.yml up -d`.
