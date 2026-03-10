.PHONY: build start stop logs deploy pull setup test test-web test-e2e

# Настройка секретов (app/.env) — перед первым запуском
setup:
	@./scripts/setup-env.sh

# Сборка и запуск
build:
	@echo "Building BirdLense Hub..."
	@docker compose build
	@echo "Build finished."

start: setup
	@echo "Starting BirdLense Hub..."
	@docker compose up -d
	@echo "BirdLense Hub on port ${BIRDLENSE_PORT:-8085}. Logs: make logs"

# Запуск из готового образа (без сборки)
pull: setup
	@docker compose -f docker-compose.pull.yml pull
	@docker compose -f docker-compose.pull.yml up -d
	@echo "BirdLense Hub on port ${BIRDLENSE_PORT:-8085}. Logs: make logs"

stop:
	@docker compose down

logs:
	@docker compose logs -f --tail=200

# Деплой на 192.168.1.11
deploy:
	@cd .. && ./scripts/deploy.sh

# Тесты (в контейнере — нужны ultralytics, ncnn)
test:
	docker compose run --rm birdlense python -m unittest discover processor/tests -v

test-web:
	docker compose run --rm birdlense python -m pytest web/tests/ -v 2>/dev/null || echo "Run: cd app && docker compose run --rm birdlense bash -c 'cd web && python -m pytest tests/ -v'"

test-e2e:
	cd e2e && npm ci && npx playwright install chromium && npm test
# E2E с паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=http://192.168.1.11:8085 make test-e2e