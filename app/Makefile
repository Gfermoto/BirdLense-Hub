.PHONY: build-dev start-dev stop-dev build start stop logs

# DEV
build-dev:
	@echo "Building Docker Compose images..."
	@docker compose -f docker-compose.base.yml -f docker-compose.dev.yml build
	@echo "Build finished."

start-dev:
	@echo "Starting Docker Compose services..."
	@docker compose -f docker-compose.base.yml -f docker-compose.dev.yml up
	@echo "Docker Compose services started."

stop-dev:
	@echo "Stopping Docker Compose services..."
	@docker compose -f docker-compose.base.yml -f docker-compose.dev.yml down
	@echo "Docker Compose services stopped."

test:
	python3 -m unittest discover processor/tests

test-web:
	docker compose -f docker-compose.base.yml -f docker-compose.dev.yml run --rm web python -m pytest tests/ -v

test-e2e:
	cd e2e && npm ci && npx playwright install chromium && npm test

# PROD
build:
	@echo "Building Docker Compose services..."
	@docker compose -f docker-compose.base.yml -f docker-compose.prod.yml build
	@echo "Build finished."

start:
	@echo "Starting Docker Compose services..."
	@docker compose -f docker-compose.base.yml -f docker-compose.prod.yml up -d
	@echo "Docker Compose services started."
	@echo "To view application logs, run: make logs"

# PROD + Go2RTC (профиль hybrid)
start-hybrid:
	@echo "Starting with Go2RTC..."
	@docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -f docker-compose.go2rtc.yml --profile hybrid up -d
	@echo "Add cameras at http://localhost:1984"

logs:
	@docker compose -f docker-compose.base.yml -f docker-compose.prod.yml logs -f --tail=200

stop:
	@echo "Stopping Docker Compose services..."
	@docker compose -f docker-compose.base.yml -f docker-compose.prod.yml down
	@echo "Docker Compose services stopped."