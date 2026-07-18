.PHONY: deploy build start stop logs verify docs ci-local preflight-deploy

deploy:
	@./scripts/deploy.sh

build:
	@$(MAKE) -C app build

start:
	@$(MAKE) -C app start

stop:
	@$(MAKE) -C app stop

logs:
	@$(MAKE) -C app logs

verify:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  ./scripts/verify-stack.sh --base-url "$$_url"

# Local full CI gate (Bandit, pytest, UI, docs). Alias expected by AGENTS / OpenCode.
ci-local:
	@./scripts/public/ci-full-local.sh

# Deploy preflight: secrets + MCP token + strict auth + config drift for Orin prod path.
preflight-deploy:
	@./scripts/preflight-deploy.sh

docs:
	@mkdocs build
