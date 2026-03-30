.PHONY: deploy build start stop logs restore-config docs docs-site diagnose refresh-telegram-proxy proxy-rotation-install proxy-rotation-status proxy-rotation-remove

deploy:
	@./scripts/deploy.sh

# Восстановить настройки: make restore-config (из .bak на сервере) или make restore-config FROM=local
restore-config:
	@[ "$(FROM)" = "local" ] && ./scripts/restore-config.sh from-local || ./scripts/restore-config.sh

build start stop logs:
	@$(MAKE) -C app $@

docs:
	@$(MAKE) -C app docs

# Статический сайт документации (MkDocs): см. docs/Documentation.md
docs-site:
	@command -v mkdocs >/dev/null 2>&1 || { echo "Установите: python3 -m venv .venv-docs && .venv-docs/bin/pip install -r requirements-docs.txt"; exit 1; }
	mkdocs serve

# Диагностика перезапусков на сервере (ssh birdlense)
diagnose:
	@./scripts/diagnose.sh

# Подобрать рабочий SOCKS5-прокси для Telegram API и применить на сервере
refresh-telegram-proxy:
	@./scripts/refresh-telegram-proxy.sh

# Поставить cron-авторотацию прокси на сервере (по умолчанию каждые 6 часов)
proxy-rotation-install:
	@./scripts/manage-telegram-proxy-rotation.sh install

# Проверить cron и последние логи ротации на сервере
proxy-rotation-status:
	@./scripts/manage-telegram-proxy-rotation.sh status

# Удалить cron-авторотацию прокси на сервере
proxy-rotation-remove:
	@./scripts/manage-telegram-proxy-rotation.sh remove
