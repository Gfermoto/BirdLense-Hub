.PHONY: build start stop logs deploy pull setup test test-web test-e2e test-coverage test-report local local-build docs docs-python docs-ui docs-check

# Настройка секретов (app/.env) — перед первым запуском
setup:
	@./scripts/setup-env.sh

# Локальная разработка: setup + local-build + start
local: setup local-build start
	@echo ""
	@echo "BirdLense Hub: http://localhost:${BIRDLENSE_PORT:-8085}"
	@echo "Логи: make logs"

# Полная сборка для локального запуска: UI + Docker-образ
local-build:
	@echo "1. Сборка UI..."
	@(cd ui && npm run build) || { echo "Ошибка: npm run build. Выполните: cd ui && npm ci && npm run build"; exit 1; }
	@echo "2. Сборка Docker-образа..."
	@docker compose build
	@echo "Build finished."

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

# Деплой на сервер: ../scripts/deploy.sh (см. docs/INSTALL.md)
deploy:
	@cd .. && ./scripts/deploy.sh

# Тесты (в контейнере — ultralytics; для two-stage — веса .pt, см. scripts/fetch-processor-weights.sh)
# -v монтирует локальный код: тесты идут по коду на диске, а не по образу
# -v ..:/workspace — корень репо (scripts/export_fusion_training_data.py и др. для _repo_root())
test:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense \
		env PYTHONPATH=/app:/app/web python -m unittest discover processor/tests -v

test-web:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense python -m pytest web/tests/ -v

# Тесты с измерением покрытия (processor + web)
# -v монтирует локальный код (см. test выше). Требует make build (coverage в web/requirements.txt)
test-coverage:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense bash -c '\
		export PYTHONPATH=/app:/app/web && \
		python -m coverage run -m unittest discover -s processor/tests -v && \
		python -m coverage run -a -m pytest web/tests/ -v && \
		python -m coverage report -m'

# Покрытие + HTML-отчёт в app/htmlcov/
test-report:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense bash -c '\
		export PYTHONPATH=/app:/app/web && \
		python -m coverage run -m unittest discover -s processor/tests -v && \
		python -m coverage run -a -m pytest web/tests/ -v && \
		python -m coverage report -m && \
		python -m coverage html'
	@echo "Отчёт: app/htmlcov/index.html"

test-e2e:
	cd e2e && npm ci && npx playwright install chromium && npm test
# Локальный стек: BASE_URL=http://127.0.0.1:8085 make test-e2e
# С паролем: E2E_SETTINGS_PASSWORD=xxx BASE_URL=http://YOUR_HOST:8085 make test-e2e

# Автодокументация
docs: docs-python docs-ui

docs-python:
	@echo "Генерация Python API (pdoc)..."
	@mkdir -p ../docs/api
	@docker compose run --rm -v $$(pwd):/app -v $$(pwd)/../docs:/docs birdlense bash -c '\
		cd /app/web && PYTHONPATH=/app python -m pdoc app util config models routes services -o /docs/api; \
		cd /app/processor/src && PYTHONPATH=. python -m pdoc frame_processor detection_strategy decision_maker species_normalizer light_level_detector api dataset_saver -o /docs/api/processor'
	@echo "Python docs: docs/api/"

docs-check:
	@echo "Проверка docstrings (interrogate, см. app/pyproject.toml)..."
	@docker compose run --rm -v $$(pwd):/app birdlense bash -c 'cd /app/web && interrogate .'

docs-ui:
	@echo "Генерация UI (TypeDoc)..."
	@(cd ui && npm run docs) || echo "TypeDoc: cd app/ui && npm run docs"