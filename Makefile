.PHONY: install install-pull deploy build start stop logs verify quality-gate verify-prod-env preflight-deploy verify-strict-quality restore-config docs docs-site diagnose refresh-telegram-proxy proxy-rotation-install proxy-rotation-status proxy-rotation-remove audit-cards validate-weights sync-models export-nabirds-openvino validate-nabirds-ov-parity ci-local ci-local-docker test-web-contract-local security-gitleaks dataset-merge-three-class dataset-dedupe-detector-yolo dataset-report-detector-yolo dataset-dedupe-detector-binary dataset-import-cub dataset-import-roboflow-bird-feeder dataset-download-roboflow-bird-feeder dataset-validate-yolo-labels dataset-verify-quality-gates dataset-verify-hard-negatives bootstrap-detector-data bootstrap-rodents-until-verify bootstrap-bird-coco-only report-detector-bird-sources dataset-rebalance-bird-binary dataset-bootstrap-rodent-oid-fast dataset-import-roboflow-rodent dataset-fetch-lila-california-rodents-sample dataset-build-birds-rodents-quick dataset-build-detector-tz detector-etl-verify-birds-rodents detector-etl-progress detector-etl-progress-watch detector-etl-restart detector-etl-supervise detector-etl-supervise-bg active-learning-trace-to-pool active-learning-pool-from-sqlite curate-hard-negatives retrain-negatives-weekly reid-import-embeddings ml-check-decode ml-export-decision-traces ml-build-registry-entry ml-verify-registry-entry ml-verify-benchmark-slices ml-verify-reid-gates ml-run-reid-execution-report ml-build-eval-dataset ml-build-behavior-dataset ml-export-behavior-onnx ml-build-behavior-train-report ml-verify-behavior-runtime ml-offline-benchmark-gate ml-detector-shortlist snapshot-detector-weights compare-detector-bboxes-help ml-openvino-async-profile ml-decode-path-benchmark ml-track-continuity-eval ml-int8-candidate-eval ml-shadow-rollout-report ml-canary-rollback-report ml-full-rollout-watch-report ml-action-model-shortlist ml-proof ml-proof-local ml-proof-hub ml-fusion-ab-local ml-fusion-ab-hub dedupe-videos-local ml-int8-parity-gate ml-multi-camera-fps-gate reliability-compare-windows trigger-detector-audit trigger-detector-audit-vps

# Тот же сценарий, что ./install.sh (Docker + .env + стек + verify).
install:
	@./install.sh

install-pull:
	@./install.sh --pull

# Все проверки как в CI (Python security, ruff, pytest web, UI, docs). Без Docker по умолчанию.
ci-local:
	@./scripts/ci-full-local.sh

security-gitleaks:
	@gitleaks detect --source=. --config=.gitleaks.toml --verbose --redact

# Плюс сборка образа, make test / test-web и Playwright smoke (как job docker-tests в CI).
ci-local-docker:
	@CI_FULL_DOCKER=1 ./scripts/ci-full-local.sh

# Быстрый web-контракт на хосте (venv в app/, без Docker). См. docs/TESTING.md — Test pyramid (#348).
test-web-contract-local:
	@$(MAKE) -C app test-web-contract-local

deploy:
	@./scripts/deploy.sh

# Post-deploy: verify + offline two_stage probes on VPS (needs deploy.local.sh).
vps-detect-classifier-diagnostic:
	@bash ./scripts/vps_detection_classifier_diagnostic.sh

# Аудит триггер → детектор по SQLite (пропуски, кто виноват). DAYS=3 CAMERAS=BirdBox,Forest
trigger-detector-audit:
	@python3 scripts/trigger_detector_audit.py --days "$${DAYS:-3}" --cameras "$${CAMERAS:-BirdBox,Forest}" \
	  --db-path "$${DB_PATH:-app/data/db/birdlense.db}"

# То же на VPS (нужен scripts/deploy.local.sh)
trigger-detector-audit-vps:
	@set -e; . scripts/deploy.local.sh; \
	ssh -p "$${DEPLOY_SSH_PORT:-22}" "$${DEPLOY_HOST}" \
	  "python3 $${DEPLOY_REMOTE_DIR:-/root/BirdLense}/scripts/trigger_detector_audit.py --days $${DAYS:-3} --cameras '$${CAMERAS:-BirdBox,Forest}' --db-path $${DEPLOY_REMOTE_DIR:-/root/BirdLense}/app/data/db/birdlense.db"

# Долгий прогон до 07:10 МСК: триггер, детектор, классификатор, ReID, behavior (VPS)
overnight-pipeline-watch:
	@set -e; . scripts/deploy.local.sh; \
	python3 scripts/overnight-pipeline-watch.py --end-msk "$${END_MSK:-07:10}" --interval-sec "$${INTERVAL_SEC:-600}" --label "$${LABEL:-msk0710}"

# Восстановить настройки: make restore-config (из .bak на сервере) или make restore-config FROM=local
restore-config:
	@[ "$(FROM)" = "local" ] && ./scripts/restore-config.sh from-local || ./scripts/restore-config.sh

build start stop logs:
	@$(MAKE) -C app $@

verify:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  ./scripts/verify-stack.sh --base-url "$$_url"

check-prod-disk:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	: "$${DEPLOY_HOST:?DEPLOY_HOST is required}"; \
	ssh -p "$${DEPLOY_SSH_PORT:-22}" "$${DEPLOY_HOST}" "set -e; \
	FREE_GB=\$$(df -BG --output=avail / | tail -1 | tr -dc '0-9'); \
	USED_PCT=\$$(df --output=pcent / | tail -1 | tr -dc '0-9'); \
	DIAG_GB=\$$(du -sBG /root/BirdLense/app/data/diagnostics 2>/dev/null | cut -f1 | tr -dc '0-9'); \
	echo disk-check free_gb=\$${FREE_GB:-0} used_pct=\$${USED_PCT:-0} diagnostics_gb=\$${DIAG_GB:-0}"

baseline-snapshot-contract:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  python3 ./scripts/parity_daily_hold.py --base-url "$$_url"; \
	sleep 2; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  python3 ./scripts/parity_daily_hold.py --base-url "$$_url"; \
	python3 ./scripts/verify_baseline_snapshot_contract.py --snapshot-dir docs/reports/parity_daily_hold

quality-gate:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  bash ./scripts/check-quality-gates.sh --base-url "$$_url"

verify-strict-quality:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  ./scripts/verify-stack.sh --base-url "$$_url" --check-domain-health --strict-quality

verify-runtime-sli:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  bash ./scripts/check-runtime-sli.sh --base-url "$$_url"

health-readiness-contract:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  python3 ./scripts/verify_health_readiness_contract.py --base-url "$$_url"

owasp-api-controls:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  python3 ./scripts/verify_owasp_api_controls.py --base-url "$$_url"

dora-metrics:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_dora_metrics.py --window-days "$${DORA_WINDOW_DAYS:-28}"

ssdf-control-map:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_ssdf_control_map.py

secrets-vuln-response-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_sec_vuln_response.py

runbook-coverage-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_runbook_coverage.py --record-validation

deploy-contract-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_deploy_contract.py

ui-contract-guard:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_ui_contract_guard.py

ml-drift-trigger-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_ml_drift_triggers.py \
	  --override-reason "$${BIRDLENSE_ML_DRIFT_OVERRIDE_REASON:-}"

openapi-governance-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_openapi_governance.py

playwright-anti-flake-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_playwright_antiflake.py

critical-ux-suite-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_critical_ux_suite.py

docs-diataxis-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_docs_diataxis.py

docs-drift-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_docs_drift_gate.py

slsa-build-track-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_slsa_build_track.py

integration-contract-registry-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_integration_contract_registry.py

event-burst-reconnect-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_event_burst_reconnect.py

scripts-ownership-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_scripts_ownership.py

champion-challenger-shadow-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_champion_challenger_shadow.py

ml-technical-debt-scorecard-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_ml_technical_debt_scorecard.py

review-board-governance-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_review_board_governance.py

release-policy-as-code-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_release_policy_as_code.py

cli-contract-standardization-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_cli_contract_standardization.py

nas-storage-contract-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_nas_storage_contract.py

outcome-metrics-gate:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_quality_outcome_metrics.py \
	  --db-path "$${OUTCOME_DB_PATH:-app/data/db/birdlense.db}" \
	  --data-source "$${OUTCOME_DATA_SOURCE:-local:app/data/db/birdlense.db}" \
	  --lookback-hours "$${OUTCOME_LOOKBACK_HOURS:-24}" \
	  --max-blind-rate "$${OUTCOME_MAX_BLIND_RATE:-0.30}" \
	  --min-tracks-coverage "$${OUTCOME_MIN_TRACKS_COVERAGE:-0.50}" \
	  --max-empty-bbox-rate "$${OUTCOME_MAX_EMPTY_BBOX_RATE:-0.20}" \
	  --min-yolo-frames-with-tracks "$${OUTCOME_MIN_YOLO_FRAMES_WITH_TRACKS:-1}"

pipeline-health-gate:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/pipeline-health-gate.sh; \
	./scripts/pipeline-health-gate.sh

# Replay all favorite mp4 on VPS (#599); creates new processor sessions.
#   source scripts/deploy.local.sh && \
#   BIRDLENSE_ALLOW_REMOTE_MUTATION=1 make replay-favorites-vps
replay-favorites-vps:
	@mkdir -p "$(CURDIR)/.artifacts/replay-favorites"
	@python3 "$(CURDIR)/scripts/replay_favorite_videos.py" \
		--json-out "$(CURDIR)/.artifacts/replay-favorites/replay_favorites_$$(date -u +%Y%m%dT%H%M%SZ).json"

replay-favorites-track-gate:
	@mkdir -p "$(CURDIR)/.artifacts/replay-favorites"
	@python3 "$(CURDIR)/scripts/replay_favorites_track_gate.py" \
		--json-out "$(CURDIR)/.artifacts/replay-favorites/track_gate_$$(date -u +%Y%m%dT%H%M%SZ).json"

failure-mode-funnel:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_failure_mode_funnel.py \
	  --db-path "$${OUTCOME_DB_PATH:-app/data/db/birdlense.db}" \
	  --lookback-hours "$${OUTCOME_LOOKBACK_HOURS:-24}"

runtime-pipeline-profile:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/report_runtime_pipeline_profile.py \
	  --db-path "$${OUTCOME_DB_PATH:-app/data/db/birdlense.db}" \
	  --lookback-hours "$${OUTCOME_LOOKBACK_HOURS:-24}" \
	  --first-bbox-warn-s "$${FIRST_BBOX_WARN_S:-5}" \
	  --finalize-warn-ms "$${FINALIZE_WARN_MS:-5000}"

sota-reality-check:
	@set -e; cd "$(CURDIR)"; \
	_fail_flag=""; \
	if [ "$${SOTA_FAIL_ON_BLOCKED:-0}" = "1" ]; then _fail_flag="--fail-on-blocked"; fi; \
	python3 ./scripts/report_sota_reality_check.py $$_fail_flag

sota-governance-cycle:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/run_sota_governance_cycle.sh; \
	GOVERNANCE_MODE="$${GOVERNANCE_MODE:-nightly}" \
	SOTA_FAIL_ON_BLOCKED="$${SOTA_FAIL_ON_BLOCKED:-1}" \
	./scripts/run_sota_governance_cycle.sh

fetch-prod-db-snapshot:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/fetch_prod_db_snapshot.sh; \
	./scripts/fetch_prod_db_snapshot.sh

sota-governance-prod:
	@set -e; cd "$(CURDIR)"; \
	GOVERNANCE_FETCH_PROD_DB=1 SOTA_FAIL_ON_BLOCKED=0 \
	$(MAKE) sota-governance-cycle

# Once-daily prod metrics (cron / manual); report-only, no fail on KPI.
daily-stats-prod: sota-governance-prod
	@echo "daily-stats-prod: see docs/reports/governance/governance_cycle_latest.json"

apply-prod-detection-tuning:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/apply-prod-detection-tuning-hotfix.sh; \
	./scripts/apply-prod-detection-tuning-hotfix.sh

verify-prod-config-drift:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/verify-prod-config-drift.sh; \
	./scripts/verify-prod-config-drift.sh

verify-prod-detector-smoke:
	@set -e; cd "$(CURDIR)"; \
	chmod +x ./scripts/verify-prod-detector-smoke.sh; \
	./scripts/verify-prod-detector-smoke.sh

verify-processor-config-drift:
	@set -e; cd "$(CURDIR)"; \
	python3 ./scripts/verify_processor_config_drift.py --fail-on-critical

sota-governance-weekly:
	@set -e; cd "$(CURDIR)"; \
	GOVERNANCE_MODE=weekly SOTA_FAIL_ON_BLOCKED=1 $(MAKE) sota-governance-cycle

error-budget-gate:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON="$${BIRDLENSE_ERROR_BUDGET_OVERRIDE_REASON:-}" \
	  python3 ./scripts/error_budget_gate.py --base-url "$$_url"

perf-gate-runtime:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  python3 ./scripts/perf_gate_runtime.py \
	    --base-url "$$_url" \
	    --burst-requests "$${PERF_BURST_REQUESTS:-200}" \
	    --burst-concurrency "$${PERF_BURST_CONCURRENCY:-20}" \
	    --metrics-scrapes "$${PERF_METRICS_SCRAPES:-120}" \
	    --metrics-concurrency "$${PERF_METRICS_CONCURRENCY:-12}" \
	    --soak-seconds "$${PERF_SOAK_SECONDS:-60}" \
	    --soak-interval-sec "$${PERF_SOAK_INTERVAL_SEC:-0.75}" \
	    --max-error-rate "$${PERF_MAX_ERROR_RATE:-0.02}" \
	    --max-p95-ms "$${PERF_MAX_P95_MS:-3000}" \
	    --max-p99-ms "$${PERF_MAX_P99_MS:-5000}" \
	    --out "$${PERF_OUT:-/tmp/runtime_perf_gate.v1.json}"

# A1: локальная копия server app/.env (verify-prod-env) + живой хаб (DEPLOY_URL из deploy.local.sh)
patch-hub-primary:
	@python3 scripts/patch_prod_hub_primary.py

patch-hub-primary-dry-run:
	@python3 scripts/patch_prod_hub_primary.py --dry-run

preflight-deploy: verify-prod-env verify
	@echo "preflight-deploy: OK"

# Pre-flight: production .env (secrets, STRICT_API_AUTH). ENV_FILE=path make verify-prod-env
verify-prod-env:
	@set -e; cd "$(CURDIR)"; \
	_ef="$${ENV_FILE:-app/.env}"; \
	if [ ! -f "$$_ef" ]; then \
	  echo "verify-prod-env: $$_ef not found — set ENV_FILE or create app/.env; running with current env only" >&2; \
	  VERIFY_PROD_ENV=1 ./scripts/verify-prod-env.sh; \
	else \
	  VERIFY_PROD_ENV=1 ./scripts/verify-prod-env.sh --env-file "$$_ef"; \
	fi

# Unified ML proof gate: local synthetic tests + deployed hub proof.
# Usage:
#   make ml-proof
#   MAX_GPU_STEADY_MS=90 make ml-proof-hub
ml-proof: ml-proof-local ml-proof-hub

ml-proof-local:
	@python3 -m pytest -q \
		app/processor/tests/test_ml_openvino_async_profile.py \
		app/processor/tests/test_ml_decode_path_benchmark.py \
		app/processor/tests/test_ml_track_continuity_eval.py \
		app/processor/tests/test_ml_int8_candidate_eval.py \
		app/processor/tests/test_ml_shadow_rollout_report.py \
		app/processor/tests/test_ml_canary_rollback_report.py \
		app/processor/tests/test_ml_full_rollout_watch_report.py \
		app/processor/tests/test_ml_fusion_ab_report.py \
		app/processor/tests/test_ml_action_model_shortlist.py \
		app/processor/tests/test_ml_behavior_canary_gate.py \
		app/processor/tests/test_ml_behavior_crop.py \
		app/processor/tests/test_ml_behavior_export_onnx.py \
		app/processor/tests/test_processor_runtime_profile_openvino.py \
		app/processor/tests/test_inference_selector.py

ml-proof-hub:
	@./scripts/ml_proof_hub.sh

ml-int8-parity-gate:
	@test -n "$${FP16_REPORT:-}" || (echo "Set FP16_REPORT=path/to/fp16_report.json" >&2; exit 1)
	@test -n "$${INT8_REPORT:-}" || (echo "Set INT8_REPORT=path/to/int8_report.json" >&2; exit 1)
	@python3 scripts/check_int8_parity.py \
		--fp16 "$${FP16_REPORT}" \
		--int8 "$${INT8_REPORT}" \
		--max-f1-drop "$${MAX_F1_DROP:-0.02}" \
		--max-anchor-drop "$${MAX_ANCHOR_DROP:-0.02}" \
		$$(test -n "$${OUT:-}" && printf -- '--out "%s" ' "$${OUT}")

ml-multi-camera-fps-gate:
	@test -n "$${FPS_REPORT:-}" || (echo "Set FPS_REPORT=path/to/runtime_fps_report.json" >&2; exit 1)
	@python3 scripts/multi_camera_fps_gate.py \
		--input "$${FPS_REPORT}" \
		--min-per-camera-fps "$${MIN_PER_CAMERA_FPS:-6.0}" \
		--min-total-fps "$${MIN_TOTAL_FPS:-18.0}" \
		$$(test -n "$${OUT:-}" && printf -- '--out "%s" ' "$${OUT}")

reliability-compare-windows:
	@test -n "$${BASELINE_REPORT:-}" || (echo "Set BASELINE_REPORT=path/to/windowA.jsonl" >&2; exit 1)
	@test -n "$${CANDIDATE_REPORT:-}" || (echo "Set CANDIDATE_REPORT=path/to/windowB.jsonl" >&2; exit 1)
	@python3 scripts/reliability_compare_windows.py \
		--baseline "$${BASELINE_REPORT}" \
		--candidate "$${CANDIDATE_REPORT}" \
		--max-sli-fail-increase "$${MAX_SLI_FAIL_INCREASE:-0}" \
		$$(test -n "$${OUT:-}" && printf -- '--out "%s" ' "$${OUT}")

# Fusion A/B gate:
# - provider split YOLO vs Frigate
# - duplicate groups in video and video_species
# - generic Bird overlap ratio
# - optional calendar compare delta via API
#
# Usage:
#   make ml-fusion-ab-local DB=app/data/db/birdlense.db OUT=/tmp/fusion_ab_report.v1.json
#   make ml-fusion-ab-hub
ml-fusion-ab-local:
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/fusion_ab_report.v1.json" >&2; exit 1)
	@python3 scripts/ml_fusion_ab_report.py \
		--db "$${DB}" \
		$$(test -n "$${DAYS:-}" && printf -- '--days "%s" ' "$${DAYS}") \
		$$(test -n "$${BASE_URL:-}" && printf -- '--base-url "%s" ' "$${BASE_URL}") \
		$$(test -n "$${API_KEY:-}" && printf -- '--api-key "%s" ' "$${API_KEY}") \
		$$(test -n "$${API_TIMEOUT_SECONDS:-}" && printf -- '--api-timeout-seconds "%s" ' "$${API_TIMEOUT_SECONDS}") \
		$$(test -n "$${MIN_YOLO_SHARE:-}" && printf -- '--min-yolo-share "%s" ' "$${MIN_YOLO_SHARE}") \
		$$(test -n "$${MAX_DUPLICATE_VIDEO_GROUPS:-}" && printf -- '--max-duplicate-video-groups "%s" ' "$${MAX_DUPLICATE_VIDEO_GROUPS}") \
		$$(test -n "$${MAX_DUPLICATE_DETECTION_GROUPS:-}" && printf -- '--max-duplicate-detection-groups "%s" ' "$${MAX_DUPLICATE_DETECTION_GROUPS}") \
		$$(test -n "$${MAX_GENERIC_OVERLAP_RATIO:-}" && printf -- '--max-generic-overlap-ratio "%s" ' "$${MAX_GENERIC_OVERLAP_RATIO}") \
		$$(test -n "$${MAX_CALENDAR_DELTA_RATIO:-}" && printf -- '--max-calendar-delta-ratio "%s" ' "$${MAX_CALENDAR_DELTA_RATIO}") \
		--out "$${OUT}"

ml-fusion-ab-hub:
	@./scripts/ml_fusion_ab_hub.sh

dedupe-videos-local:
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/dedupe_video_records.v1.json" >&2; exit 1)
	@python3 scripts/dedupe_video_records.py \
		--db "$${DB}" \
		$$(test "$${DRY_RUN:-0}" = "1" && printf -- '--dry-run ') \
		--out "$${OUT}"

docs:
	@mkdocs build
