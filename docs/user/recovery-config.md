# Восстановление конфигурации

## Симптом

- user_config.yaml повреждён
- система не стартует из-за ошибки в конфиге
- случайно удалён user_config.yaml

## Восстановление

### Из бэкапа (рекомендуется)

```bash
make restore-config
# ищет app/app_config/user_config.yaml.bak.*
# восстанавливает последний бэкап
```

### Из шаблона

```bash
cp app/app_config/user_config.orin.example.yaml app/app_config/user_config.yaml
# затем отредактировать под свою конфигурацию
```

### Если нет ни бэкапа, ни шаблона

```bash
# Временно запустить с default_config.yaml
# (содержит безопасные значения по умолчанию)
# затем настроить через веб-UI
```

## Предотвращение

Система автоматически создаёт бэкап `user_config.yaml.bak.YYYYMMDD_<reason>` при изменении конфига через веб-UI.

Перед ручным редактированием:

```bash
cp user_config.yaml user_config.yaml.bak.$(date +%Y%m%d)
```