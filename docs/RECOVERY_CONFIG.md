# Восстановление настроек

## Если настройки сбросились

### 0. Скрипт восстановления (быстро)

```bash
# Восстановить из .bak на сервере (если есть)
./scripts/restore-config.sh

# Или скопировать ЛОКАЛЬНЫЙ конфиг на сервер
./scripts/restore-config.sh from-local
```

После восстановления перезапустите: `ssh birdlense "cd /root/BirdLense/app && make stop && make start"`

### 1. Вручную: бэкап (с версии с бэкапом)

Перед каждым сохранением создаётся `user_config.yaml.bak`:

```bash
# Локально
cp app/app_config/user_config.yaml.bak app/app_config/user_config.yaml

# На сервере
ssh birdlense "cp /root/BirdLense/app/app_config/user_config.yaml.bak /root/BirdLense/app/app_config/user_config.yaml"
# Затем перезапустить: make restart (или подождать перезапуска процессора)
```

### 2. Проверить user_config на сервере

Деплой **не перезаписывает** `user_config.yaml` на сервере. Если настройки были на сервере, они могут быть целы:

```bash
ssh birdlense "cat /root/BirdLense/app/app_config/user_config.yaml"
```

Если файл полный — скопировать локально или оставить как есть.

### 3. Git

Если `user_config.yaml` был в git (не рекомендуется для секретов):

```bash
git checkout app/app_config/user_config.yaml
```

### 4. Ручное восстановление

Восстановить ключевые параметры через Настройки в UI или напрямую в `app/app_config/user_config.yaml`:

- `video.cameras`, `video.go2rtc_url`
- `mqtt.broker`, `mqtt.password`
- `notifications.telegram_bot_token`, `notifications.telegram_chat_id`
- `general.settings_password`
- и т.д.

См. [CONFIGURATION.md](./CONFIGURATION.md).
