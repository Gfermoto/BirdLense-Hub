.PHONY: deploy build start stop logs verify docs ci-local preflight-deploy validate-pipeline-golden validate-detector-golden validate-species-golden hub-only-baseline

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

# Detector/track golden (RC6). Unit fallback is NOT a taxonomy pass.
validate-detector-golden:
	@python3 scripts/pipeline_golden_gate.py --skip-heavy --enforce

# Alias kept for older runbooks / enforce scripts.
validate-pipeline-golden: validate-detector-golden

# Taxonomy / named Hub-only cases (RC6). Required for species product CI.
validate-species-golden:
	@python3 scripts/species_golden_gate.py --enforce

# Hub-only named_share from Orin session summaries / DB (Frigate rows excluded).
hub-only-baseline:
	@python3 scripts/hub_only_baseline.py

docs:
	@mkdocs build
