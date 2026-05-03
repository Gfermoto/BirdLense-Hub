.PHONY: install install-pull deploy build start stop logs verify verify-strict-quality restore-config docs docs-site diagnose refresh-telegram-proxy proxy-rotation-install proxy-rotation-status proxy-rotation-remove audit-cards validate-weights ci-local ci-local-docker test-web-contract-local security-gitleaks dataset-merge-three-class dataset-validate-yolo-labels bootstrap-detector-data active-learning-trace-to-pool active-learning-pool-from-sqlite reid-import-embeddings ml-check-decode ml-export-decision-traces ml-build-eval-dataset ml-build-behavior-dataset ml-build-behavior-train-report ml-offline-benchmark-gate ml-detector-shortlist ml-openvino-async-profile ml-decode-path-benchmark ml-track-continuity-eval ml-int8-candidate-eval ml-shadow-rollout-report ml-canary-rollback-report ml-full-rollout-watch-report ml-action-model-shortlist ml-proof ml-proof-local ml-proof-hub ml-fusion-ab-local ml-fusion-ab-hub dedupe-videos-local

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

verify-strict-quality:
	@set -e; cd "$(CURDIR)"; \
	if [ -f scripts/deploy.local.sh ]; then set -a; . scripts/deploy.local.sh; set +a; fi; \
	_url="$${BASE_URL:-$${DEPLOY_URL:-http://127.0.0.1:8085}}"; \
	MCP_TOKEN="$${MCP_TOKEN:-}" BIRDLENSE_UI_API_KEY="$${BIRDLENSE_UI_API_KEY:-}" \
	  ./scripts/verify-stack.sh --base-url "$$_url" --check-domain-health --strict-quality

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
		app/processor/tests/test_processor_runtime_profile_openvino.py \
		app/processor/tests/test_inference_selector.py

ml-proof-hub:
	@./scripts/ml_proof_hub.sh

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
	@$(MAKE) -C app docs

# Статический сайт документации (MkDocs): см. docs/Documentation.md
docs-site:
	@if [ -x .venv-docs/bin/mkdocs ]; then \
		.venv-docs/bin/mkdocs serve; \
	elif command -v mkdocs >/dev/null 2>&1; then \
		mkdocs serve; \
	else \
		echo "Установите: python3 -m venv .venv-docs && .venv-docs/bin/pip install -r requirements-docs.txt"; exit 1; \
	fi

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

# Аудит карточек видов (фото/описание/доступность через proxy)
# Примеры:
#   make audit-cards
#   BASE_URL=https://hub.example.com make audit-cards
# По умолчанию — меньше параллели и игнор HTTP 429 на прямых запросах к Wikimedia (внешний rate limit).
# Строго все изображения: AUDIT_CARDS_STRICT=1 make audit-cards
audit-cards:
	@if [ "$${AUDIT_CARDS_STRICT:-0}" = 1 ]; then \
		python3 scripts/audit_species_cards.py --base-url "$${BASE_URL:-http://127.0.0.1:8085}" --workers "$${AUDIT_CARDS_WORKERS:-12}"; \
	else \
		python3 scripts/audit_species_cards.py --base-url "$${BASE_URL:-http://127.0.0.1:8085}" --workers "$${AUDIT_CARDS_WORKERS:-6}" --ignore-direct-image-429; \
	fi

# Валидация rollout-кандидата весов перед загрузкой в Hub/UI.
# Пример:
#   make validate-weights DATASET_INFO=app/data/dataset/exports/latest/dataset_info.json
# Epic #367 Phase 1 — YOLO detection Bird/Rodent/Background (see scripts/datasets/README.md).
# Requires binary/birds, binary/rodent, binary/background under scripts/datasets/.
dataset-merge-three-class:
	@cd scripts/datasets && python3 merge_datasets_three_class.py \
	  --birds-dir binary/birds \
	  --rodent-dir binary/rodent \
	  --background-dir binary/background \
	  --output-dir binary/merged

# Скачать стартовые подмножества COCO + Open Images в три каталога (нужен pip install fiftyone).
# Переопределение лимитов: make bootstrap-detector-data ARGS='--birds-train 50 --birds-val 20'
bootstrap-detector-data:
	@cd scripts/datasets && python3 bootstrap_detector_yolo.py $(ARGS)

# Validate YOLO labels before Colab training. Example:
# LABELS_DIR=scripts/datasets/binary/merged/labels/train CLASS_COUNT=3 make dataset-validate-yolo-labels
dataset-validate-yolo-labels:
	@test -n "$${LABELS_DIR:-}" || (echo "Set LABELS_DIR=path/to/labels" >&2; exit 1)
	@python3 scripts/datasets/validate_yolo_labels.py "$${LABELS_DIR}" --class-count "$${CLASS_COUNT:-3}"

# Экспорт decision_trace JSON → JSONL манифеста AL (см. scripts/active_learning/README.md). Пример: INPUT=trace.json make active-learning-trace-to-pool
active-learning-trace-to-pool:
	@test -n "$${INPUT:-}" || (echo "Set INPUT=path/to/decision_trace.json" >&2; exit 1)
	@python3 scripts/active_learning/decision_trace_to_pool_manifest.py "$${INPUT}"

# SQLite activity_log decision_trace → active-learning JSONL.
# Example: DB=app/data/db/birdlense.db OUT=pool.jsonl make active-learning-pool-from-sqlite
active-learning-pool-from-sqlite:
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=pool.jsonl" >&2; exit 1)
	@python3 scripts/active_learning/export_pool_from_sqlite.py --db "$${DB}" --output "$${OUT}" $${ARGS:-}

# Import DINO JSONL embeddings into local SQLite sidecar table reid_embedding.
reid-import-embeddings:
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${JSONL:-}" || (echo "Set JSONL=embeddings.jsonl" >&2; exit 1)
	@python3 scripts/reid/import_embeddings_sqlite.py --db "$${DB}" --jsonl "$${JSONL}" $$(test -n "$${MANIFEST:-}" && printf -- '--manifest "%s" ' "$${MANIFEST}") $${ARGS:-}

# VA-API /dev/dri preflight (#373). Example: make ml-check-decode
ml-check-decode:
	@python3 scripts/check_video_decode_environment.py

# Export decision_trace rows from SQLite (#369 tooling). Set OUT=dir and DB=path/to/birdlense.db
ml-export-decision-traces:
	@test -n "$${OUT:-}" || (echo "Set OUT=output/dir and DB=app/data/db/birdlense.db (or your path)" >&2; exit 1)
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@python3 scripts/export_decision_traces_sqlite.py --db "$${DB}" --out-dir "$${OUT}"

# Build versioned eval dataset manifest for ML migration (#404).
# Example:
# VIDEOS_ROOT=app/data/recordings LABELS_JSON=/tmp/gold.json OUT=app/data/eval_datasets make ml-build-eval-dataset
ml-build-eval-dataset:
	@test -n "$${VIDEOS_ROOT:-}" || (echo "Set VIDEOS_ROOT=path/to/eval/videos" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=output/dir (e.g. app/data/eval_datasets)" >&2; exit 1)
	@python3 scripts/ml_build_eval_dataset.py \
		--videos-root "$${VIDEOS_ROOT}" \
		$$(test -n "$${LABELS_JSON:-}" && printf -- '--labels-json "%s" ' "$${LABELS_JSON}") \
		$$(test -n "$${DATASET_ID:-}" && printf -- '--dataset-id "%s" ' "$${DATASET_ID}") \
		--out-dir "$${OUT}" \
		$${ARGS:-}

# Build behavior dataset manifest with deterministic splits (Wave 1 / #416).
# Example:
# ANNOTATIONS_ROOT=/data/Visual-WetlandBirds/annotations OUT=/tmp/behavior_dataset_manifest.v1.json make ml-build-behavior-dataset
ml-build-behavior-dataset:
	@test -n "$${ANNOTATIONS_ROOT:-}" || (echo "Set ANNOTATIONS_ROOT=path/to/annotations" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/behavior_dataset_manifest.v1.json" >&2; exit 1)
	@python3 scripts/ml_behavior_dataset_manifest.py \
		--annotations-root "$${ANNOTATIONS_ROOT}" \
		$$(test -n "$${DATASET_ID:-}" && printf -- '--dataset-id "%s" ' "$${DATASET_ID}") \
		$$(test -n "$${TAXONOMY_JSON:-}" && printf -- '--taxonomy-json "%s" ' "$${TAXONOMY_JSON}") \
		$$(test -n "$${SPLIT_SEED:-}" && printf -- '--split-seed "%s" ' "$${SPLIT_SEED}") \
		$$(test -n "$${TRAIN_RATIO:-}" && printf -- '--train-ratio "%s" ' "$${TRAIN_RATIO}") \
		$$(test -n "$${VAL_RATIO:-}" && printf -- '--val-ratio "%s" ' "$${VAL_RATIO}") \
		$$(test -n "$${TEST_RATIO:-}" && printf -- '--test-ratio "%s" ' "$${TEST_RATIO}") \
		--out "$${OUT}" \
		$${ARGS:-}

# Build behavior training/eval report from predictions and manifest (Wave 2 / #416).
# Example:
# MANIFEST=/tmp/behavior_dataset_manifest.v1.json PREDICTIONS=/tmp/behavior_predictions.v1.json OUT=/tmp/behavior_train_report.v1.json make ml-build-behavior-train-report
ml-build-behavior-train-report:
	@test -n "$${MANIFEST:-}" || (echo "Set MANIFEST=path/to/behavior_dataset_manifest.v1.json" >&2; exit 1)
	@test -n "$${PREDICTIONS:-}" || (echo "Set PREDICTIONS=path/to/behavior_predictions.v1.json" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/behavior_train_report.v1.json" >&2; exit 1)
	@python3 scripts/ml_behavior_train_report.py \
		--manifest "$${MANIFEST}" \
		--predictions "$${PREDICTIONS}" \
		$$(test -n "$${SPLIT:-}" && printf -- '--split "%s" ' "$${SPLIT}") \
		$$(test -n "$${MIN_MACRO_F1:-}" && printf -- '--min-macro-f1 "%s" ' "$${MIN_MACRO_F1}") \
		--out "$${OUT}" \
		$${ARGS:-}

# Run offline detector-first gate for candidate vs baseline (#407).
# Example:
# BASELINE=/tmp/base.json CANDIDATE=/tmp/candidate.json CONTINUITY=/tmp/detector_continuity_report.v1.json OUT=/tmp/offline_gate.json make ml-offline-benchmark-gate
ml-offline-benchmark-gate:
	@test -n "$${BASELINE:-}" || (echo "Set BASELINE=path/to/baseline_report.json" >&2; exit 1)
	@test -n "$${CANDIDATE:-}" || (echo "Set CANDIDATE=path/to/candidate_report.json" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/offline_gate_report.json" >&2; exit 1)
	@python3 scripts/ml_offline_benchmark_gate.py \
		--baseline-report "$${BASELINE}" \
		--candidate-report "$${CANDIDATE}" \
		$$(test -n "$${CONTINUITY:-}" && printf -- '--continuity-report "%s" ' "$${CONTINUITY}") \
		--out "$${OUT}" \
		$${ARGS:-}

# Build detector candidate shortlist and compliance/bird-only verdict (#405).
# Example:
# CONTINUITY=/tmp/detector_continuity_report.v1.json OFFLINE_GATE=/tmp/offline_gate.json OUT=/tmp/detector_shortlist.v1.json make ml-detector-shortlist
ml-detector-shortlist:
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/detector_shortlist_report.json" >&2; exit 1)
	@python3 scripts/ml_detector_shortlist.py \
		$$(test -n "$${CONTINUITY:-}" && printf -- '--continuity-report "%s" ' "$${CONTINUITY}") \
		$$(test -n "$${OFFLINE_GATE:-}" && printf -- '--offline-gate-report "%s" ' "$${OFFLINE_GATE}") \
		$$(test -n "$${SHORTLIST_SIZE:-}" && printf -- '--shortlist-size "%s" ' "$${SHORTLIST_SIZE}") \
		--out "$${OUT}" \
		$${ARGS:-}

# Profile OpenVINO device/hint combos and emit ov_async_profile_report@v1 (#412).
# Example:
# VIDEOS_ROOT=app/data/recordings OUT=/tmp/ov_async_profile.json make ml-openvino-async-profile
ml-openvino-async-profile:
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/ov_async_profile_report.json" >&2; exit 1)
	@python3 scripts/ml_openvino_async_profile.py \
		$$(test -n "$${VIDEOS_ROOT:-}" && printf -- '--videos-root "%s" ' "$${VIDEOS_ROOT}") \
		$$(test -n "$${LABELS_JSON:-}" && printf -- '--labels-json "%s" ' "$${LABELS_JSON}") \
		$$(test -n "$${MAX_VIDEOS:-}" && printf -- '--max-videos "%s" ' "$${MAX_VIDEOS}") \
		$$(test -n "$${MAX_RUNTIME_SEC:-}" && printf -- '--max-runtime-sec "%s" ' "$${MAX_RUNTIME_SEC}") \
		$${VIDEO_ARGS:-} \
		$${PROFILE_ARGS:-} \
		--out "$${OUT}"

# Compare opencv vs ffmpeg_vaapi decode paths and emit decode_path_benchmark@v1 (#413).
# Example:
# VIDEO=app/data/file_test/sample.mp4 OUT=/tmp/decode_path_benchmark.v1.json make ml-decode-path-benchmark
ml-decode-path-benchmark:
	@test -n "$${VIDEO:-}" || (echo "Set VIDEO=path/to/video.mp4" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/decode_path_benchmark_report.json" >&2; exit 1)
	@python3 scripts/ml_decode_path_benchmark.py \
		--video "$${VIDEO}" \
		$$(test -n "$${FRAMES:-}" && printf -- '--frames "%s" ' "$${FRAMES}") \
		$$(test -n "$${WIDTH:-}" && printf -- '--width "%s" ' "$${WIDTH}") \
		$$(test -n "$${HEIGHT:-}" && printf -- '--height "%s" ' "$${HEIGHT}") \
		$$(test -n "$${VAAPI_DEVICE:-}" && printf -- '--vaapi-device "%s" ' "$${VAAPI_DEVICE}") \
		--out "$${OUT}"

# Build track_continuity_eval@v1 from detector_continuity_report@v1 (#414).
# Example:
# CONTINUITY=/tmp/detector_continuity_report.v1.json OUT=/tmp/track_continuity_eval.v1.json make ml-track-continuity-eval
ml-track-continuity-eval:
	@test -n "$${CONTINUITY:-}" || (echo "Set CONTINUITY=path/to/detector_continuity_report.json" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/track_continuity_eval_report.json" >&2; exit 1)
	@python3 scripts/ml_track_continuity_eval.py \
		--continuity-report "$${CONTINUITY}" \
		$$(test -n "$${MAX_EMPTY_TRACK_RATE:-}" && printf -- '--max-empty-track-rate "%s" ' "$${MAX_EMPTY_TRACK_RATE}") \
		$$(test -n "$${MIN_TRACK_EMIT_SUCCESS_RATE:-}" && printf -- '--min-track-emit-success-rate "%s" ' "$${MIN_TRACK_EMIT_SUCCESS_RATE}") \
		--out "$${OUT}"

# Build int8_candidate_eval@v1 from baseline/candidate benchmark reports (#415).
# Example:
# BASELINE=/tmp/base.json CANDIDATE=/tmp/int8.json CONTINUITY=/tmp/detector_continuity_report.v1.json OUT=/tmp/int8_candidate_eval.v1.json make ml-int8-candidate-eval
ml-int8-candidate-eval:
	@test -n "$${BASELINE:-}" || (echo "Set BASELINE=path/to/baseline benchmark report" >&2; exit 1)
	@test -n "$${CANDIDATE:-}" || (echo "Set CANDIDATE=path/to/int8 candidate benchmark report" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/int8_candidate_eval_report.json" >&2; exit 1)
	@python3 scripts/ml_int8_candidate_eval.py \
		--baseline-report "$${BASELINE}" \
		--candidate-report "$${CANDIDATE}" \
		$$(test -n "$${CONTINUITY:-}" && printf -- '--continuity-report "%s" ' "$${CONTINUITY}") \
		$$(test -n "$${MIN_LATENCY_IMPROVEMENT_RATIO:-}" && printf -- '--min-latency-improvement-ratio "%s" ' "$${MIN_LATENCY_IMPROVEMENT_RATIO}") \
		$$(test -n "$${MAX_QUALITY_DROP_PP:-}" && printf -- '--max-quality-drop-pp "%s" ' "$${MAX_QUALITY_DROP_PP}") \
		--out "$${OUT}"

# Build shadow_rollout_report@v1 from 2+ shadow windows (#408).
# Example:
# WINDOWS='--window-report /tmp/w1.json --window-report /tmp/w2.json' OUT=/tmp/shadow_rollout.v1.json make ml-shadow-rollout-report
ml-shadow-rollout-report:
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/shadow_rollout_report.json" >&2; exit 1)
	@test -n "$${WINDOWS:-}" || (echo "Set WINDOWS='--window-report a --window-report b'" >&2; exit 1)
	@python3 scripts/ml_shadow_rollout_report.py \
		$${WINDOWS} \
		$$(test -n "$${CRITICAL_INCIDENTS:-}" && printf -- '--critical-incidents "%s" ' "$${CRITICAL_INCIDENTS}") \
		$$(test -n "$${MAX_DISAGREEMENT_RATE:-}" && printf -- '--max-disagreement-rate "%s" ' "$${MAX_DISAGREEMENT_RATE}") \
		$$(test -n "$${MIN_WINDOWS:-}" && printf -- '--min-windows "%s" ' "$${MIN_WINDOWS}") \
		--out "$${OUT}"

# Build canary_rollback_report@v1 with auto-stop + rollback drill verdict (#409).
# Example:
# BASELINE=/tmp/base_sli.json CANARY=/tmp/canary_sli.json ROLLBACK=/tmp/rollback_sli.json OUT=/tmp/canary_rollback.v1.json make ml-canary-rollback-report
ml-canary-rollback-report:
	@test -n "$${BASELINE:-}" || (echo "Set BASELINE=path/to/baseline_sli.json" >&2; exit 1)
	@test -n "$${CANARY:-}" || (echo "Set CANARY=path/to/canary_sli.json" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/canary_rollback_report.json" >&2; exit 1)
	@python3 scripts/ml_canary_rollback_report.py \
		--baseline-sli "$${BASELINE}" \
		--canary-sli "$${CANARY}" \
		$$(test -n "$${ROLLBACK:-}" && printf -- '--rollback-sli "%s" ' "$${ROLLBACK}") \
		$$(test -n "$${MAX_LATENCY_REGRESSION_RATIO:-}" && printf -- '--max-latency-regression-ratio "%s" ' "$${MAX_LATENCY_REGRESSION_RATIO}") \
		$$(test -n "$${MAX_ERROR_RATE:-}" && printf -- '--max-error-rate "%s" ' "$${MAX_ERROR_RATE}") \
		--out "$${OUT}"

# Build full_rollout_watch_report@v1 for 100% rollout and 72h watch (#410).
# Example:
# BEFORE=/tmp/before.json AFTER=/tmp/after.json WATCH='--watch-window /tmp/d1.json --watch-window /tmp/d2.json --watch-window /tmp/d3.json' OUT=/tmp/full_rollout_watch.v1.json make ml-full-rollout-watch-report
ml-full-rollout-watch-report:
	@test -n "$${BEFORE:-}" || (echo "Set BEFORE=path/to/before_report.json" >&2; exit 1)
	@test -n "$${AFTER:-}" || (echo "Set AFTER=path/to/after_report.json" >&2; exit 1)
	@test -n "$${WATCH:-}" || (echo "Set WATCH='--watch-window d1 --watch-window d2 --watch-window d3'" >&2; exit 1)
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/full_rollout_watch_report.json" >&2; exit 1)
	@python3 scripts/ml_full_rollout_watch_report.py \
		--before-report "$${BEFORE}" \
		--after-report "$${AFTER}" \
		$${WATCH} \
		$$(test -n "$${MIN_WATCH_HOURS:-}" && printf -- '--min-watch-hours "%s" ' "$${MIN_WATCH_HOURS}") \
		$$(test -n "$${MAX_ERROR_RATE:-}" && printf -- '--max-error-rate "%s" ' "$${MAX_ERROR_RATE}") \
		$$(test -n "$${MAX_P95_LATENCY_MS:-}" && printf -- '--max-p95-latency-ms "%s" ' "$${MAX_P95_LATENCY_MS}") \
		--out "$${OUT}"

# Build action_model_shortlist@v1 and MVP training recipe (#406).
# Example:
# OUT=/tmp/action_model_shortlist.v1.json make ml-action-model-shortlist
ml-action-model-shortlist:
	@test -n "$${OUT:-}" || (echo "Set OUT=path/to/action_model_shortlist_report.json" >&2; exit 1)
	@python3 scripts/ml_action_model_shortlist.py \
		$$(test -n "$${CANDIDATES_JSON:-}" && printf -- '--candidates-json "%s" ' "$${CANDIDATES_JSON}") \
		$$(test -n "$${MIN_DATASET_CLIPS:-}" && printf -- '--min-dataset-clips "%s" ' "$${MIN_DATASET_CLIPS}") \
		--out "$${OUT}"

validate-weights:
	@python3 scripts/validate-processor-weights.py \
		--binary "$${BINARY:-app/processor/models/detection/weights/best.pt}" \
		--classifier "$${CLASSIFIER:-app/processor/models/classification/weights/best.pt}" \
		--class-names "$${CLASS_NAMES:-app/processor/models/classification/weights/class_names.txt}" \
		$$(test -n "$${DATASET_INFO:-}" && printf -- '--dataset-info "%s" ' "$${DATASET_INFO}") \
		$$(test -n "$${FUSION_MODEL:-}" && printf -- '--fusion-model "%s" ' "$${FUSION_MODEL}") \
		$$(test -n "$${OUTPUT:-}" && printf -- '--output "%s" ' "$${OUTPUT}")
