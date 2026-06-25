# Быстрый старт (Orin)

```bash
# 1. Клонировать репозиторий
git clone <url> /home/birdlense/hub
cd /home/birdlense/hub

# 2. Переключиться на ветку Orin
git checkout orin

# 3. Создать .env из шаблона
cp app/.env.example app/.env
# Отредактировать: FLASK_SECRET_KEY, PROCESSOR_SECRET, MCP_TOKEN

# 4. Поменять user_config под Orin
cp app/app_config/user_config.orin.example.yaml app/app_config/user_config.yaml

# 5. Собрать и запустить
cd app && make build && make start

# 6. Проверить
make verify
```

После запуска веб-интерфейс: `http://<orin-ip>:8085/`

Подробнее: [`INSTALL.md`](INSTALL.md) · [`user/quickstart.md`](user/quickstart.md)