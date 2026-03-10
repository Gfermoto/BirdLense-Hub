.PHONY: build start stop logs deploy test test-web test-e2e

# Сборка и запуск
build:
	@echo "Building BirdLense..."
	@docker compose build
	@echo "Build finished."

start:
	@echo "Starting BirdLense..."
	@docker compose up -d
	@echo "BirdLense on port ${BIRDLENSE_PORT:-8085}. Logs: make logs"

stop:
	@docker compose down

logs:
	@docker compose logs -f --tail=200

# Деплой на 192.168.1.11
deploy:
	@cd .. && ./scripts/deploy.sh

# Тесты
test:
	python3 -m unittest discover processor/tests

test-web:
	docker compose run --rm birdlense python -m pytest web/tests/ -v 2>/dev/null || echo "Run: cd app && docker compose run --rm birdlense bash -c 'cd web && python -m pytest tests/ -v'"

test-e2e:
	cd e2e && npm ci && npx playwright install chromium && npm test
# E2E с паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=http://192.168.1.11:8085 make test-e2e