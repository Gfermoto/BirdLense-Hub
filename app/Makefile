.PHONY: all clean build start stop logs verify deploy pull setup test test-processor-light test-web test-web-contract-local test-web-local venv-web venv-web-reset test-e2e test-coverage test-report local local-build docs docs-python docs-ui docs-check

# Platform: intel_nuc (default) | orin — см. scripts/platform-profile.sh, deploy/profiles/
BIRDLENSE_PLATFORM ?= orin
COMPOSE ?= docker compose
COMPOSE_FILES := docker-compose.yml
ifeq ($(BIRDLENSE_PLATFORM),orin)
COMPOSE_FILES := docker-compose.yml docker-compose.orin.yml
endif
COMPOSE_CMD = $(COMPOSE) $(foreach f,$(COMPOSE_FILES),-f $(f))

all: build

clean:
	@$(COMPOSE_CMD) down --remove-orphans 2>/dev/null || true
	@rm -rf htmlcov .coverage

# Локальный venv для pytest без Docker (тот же requirements, что в CI openapi job).
VENV ?= .venv
# Не подмешивать ~/.local и PIP_USER (иначе pip видит platformio/mkdocs и сыпет ложные dependency conflicts).
WEB_VENV_ENV := env -u PIP_USER -u PYTHONPATH PYTHONNOUSERSITE=1

# Настройка секретов (app/.env) — перед первым запуском
setup:
	@./scripts/setup-env.sh

# Локальная разработка: setup + local-build + start
local: setup local-build start
	@echo ""
	@echo "BirdLense Hub: http://localhost:$${BIRDLENSE_PORT:-8085}"
	@echo "Логи: make logs"

# Полная сборка для локального запуска: UI + Docker-образ
local-build:
	@echo "1. Сборка UI..."
	@(cd ui && npm ci && npm run build) || { echo "Ошибка: npm ci / npm run build. Проверьте Node/npm (см. app/ui/package.json engines)."; exit 1; }
	@echo "2. Сборка Docker-образа (platform=${BIRDLENSE_PLATFORM})..."
	@$(COMPOSE_CMD) build
	@echo "Build finished."

# Сборка и запуск
build:
	@echo "Building BirdLense Hub..."
	@$(COMPOSE_CMD) build
	@echo "Build finished."

start: setup
	@echo "Starting BirdLense Hub..."
	@$(COMPOSE_CMD) up -d
	@echo "BirdLense Hub on port $${BIRDLENSE_PORT:-8085}. Logs: make logs"

# Запуск из готового образа (без сборки)
pull: setup
	@docker compose -f docker-compose.pull.yml pull
	@docker compose -f docker-compose.pull.yml up -d
	@echo "BirdLense Hub on port $${BIRDLENSE_PORT:-8085}. Logs: make logs"

stop:
	@$(COMPOSE_CMD) down

logs:
	@$(COMPOSE_CMD) logs -f --tail=200

verify:
	@set -e; \
	if [ -f ../scripts/deploy.local.sh ]; then set -a; . ../scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:$${BIRDLENSE_PORT:-8085}}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  ../scripts/verify-stack.sh --base-url "$$_url"

# Деплой на сервер: ../scripts/deploy.sh (см. docs/INSTALL.md)
deploy:
	@cd .. && ./scripts/deploy.sh

# Тесты (в контейнере — ultralytics; для two-stage — веса .pt, см. scripts/fetch-processor-weights.sh)
# -v монтирует локальный код: тесты идут по коду на диске, а не по образу
# -v ..:/workspace — корень репо (scripts/export_fusion_training_data.py и др. для _repo_root())
# processor/src в PYTHONPATH — импорты вроде birdnet_fifo_persist без sys.path в каждом тесте.
test:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense \
		bash -c 'cd /workspace/app && export PYTHONPATH=/workspace/app:/workspace/app/web:/workspace/app/processor/src:/workspace/scripts SKIP_HEAVY_PROCESSOR_TESTS=1 && \
		python -m pytest processor/tests/ -q --tb=short -m "not heavy"'

# Тот же образ, но без интеграции TwoStageStrategy с реальными .pt (меньше RAM; #282).
# Один прогон pytest по processor/tests (включая unittest.TestCase); ``-m "not heavy"`` оставляет немаркированные тесты.
test-processor-light:
	docker compose run --rm -e SKIP_HEAVY_PROCESSOR_TESTS=1 -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense \
		bash -c 'cd /workspace/app && export PYTHONPATH=/workspace/app:/workspace/app/web:/workspace/app/processor/src:/workspace/scripts SKIP_HEAVY_PROCESSOR_TESTS=1 && \
		python -m pytest processor/tests/ -q --tb=short -m "not heavy"'

# По умолчанию -q: 400+ тестов с -v раздувают лог CI (обрыв/лимит раннера). Для отладки: TEST_WEB_VERBOSE=1 make test-web
test-web:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense \
		bash -c 'if [ "$$TEST_WEB_VERBOSE" = 1 ]; then exec python -m pytest web/tests/ -v; else exec python -m pytest web/tests/ -q --tb=short; fi'

# Узкий набор: OpenAPI-контракт + жёсткий gate API auth (~минуты на хосте, без Docker). См. docs/TESTING.md § Test pyramid (#348).
test-web-contract-local: venv-web
	$(WEB_VENV_ENV) PYTHONPATH=$(CURDIR):$(CURDIR)/web "$(VENV)/bin/python" -m pytest \
		web/tests/test_openapi_contract.py \
		web/tests/test_strict_ui_api_auth.py \
		-q --tb=line

# Один раз: venv + pip install -r web/requirements.txt (см. WEB_VENV_ENV — без ~/.local в PYTHONPATH).
venv-web:
	@if [ ! -x "$(VENV)/bin/python" ]; then \
		$(WEB_VENV_ENV) python3 -m venv "$(VENV)" && \
		$(WEB_VENV_ENV) "$(VENV)/bin/python" -m pip install -U pip; \
	fi
	$(WEB_VENV_ENV) "$(VENV)/bin/python" -m pip install -U -r web/requirements.txt
	@echo "venv-web: готово $(abspath $(VENV)) (используйте: make test-web-local)"

# Полная пересборка web venv: удалить $(VENV) и заново только web/requirements.txt
# (убирает «мусор» вроде platformio из старых ручных pip install в том же каталоге).
venv-web-reset:
	@echo "venv-web-reset: удаляю $(abspath $(VENV)) ..."
	@rm -rf "$(VENV)"
	@$(MAKE) venv-web

# Pytest на хосте (без sqlalchemy в системном python тесты падают — используйте этот таргет или Docker test-web).
# PYTHONNOUSERSITE=1 — не подмешивать пакеты из ~/.local (иначе версии Flask и др. отличаются от venv).
test-web-local: venv-web
	$(WEB_VENV_ENV) PYTHONPATH=$(CURDIR)/web:$(CURDIR):$(CURDIR)/processor/src "$(VENV)/bin/python" -m pytest web/tests/ -q --tb=line

# Тесты с измерением покрытия (processor + web)
# -v монтирует локальный код (см. test выше). Требует make build (coverage в web/requirements.txt)
test-coverage:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense bash -c '\
		export PYTHONPATH=/app:/app/web:/app/processor/src && \
		python -m coverage run -m unittest discover -s processor/tests -v && \
		python -m coverage run -a -m pytest web/tests/ -v && \
		python -m coverage report -m'

test-coverage-critical:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense bash -c '\
		export PYTHONPATH=/app:/app/web:/app/processor/src && \
		python -m coverage run -m pytest \
			web/tests/test_csrf_service.py \
			web/tests/test_strict_ui_api_auth.py \
			web/tests/test_config.py -q && \
		python -m coverage report \
			--include="web/config.py,web/services/csrf_service.py,web/services/strict_ui_api_auth_service.py" \
			--fail-under=80'

# Покрытие + HTML-отчёт в app/htmlcov/
test-report:
	docker compose run --rm -v $$(pwd):/app -v $$(pwd)/..:/workspace birdlense bash -c '\
		export PYTHONPATH=/app:/app/web:/app/processor/src && \
		python -m coverage run -m unittest discover -s processor/tests -v && \
		python -m coverage run -a -m pytest web/tests/ -v && \
		python -m coverage report -m && \
		python -m coverage html'
	@echo "Отчёт: app/htmlcov/index.html"

test-e2e:
	cd e2e && npm ci && npx playwright install chromium && env -u NO_COLOR -u FORCE_COLOR NODE_NO_WARNINGS=1 npm test
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