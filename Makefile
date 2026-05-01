.PHONY: install install-pull deploy build start stop logs verify restore-config docs docs-site diagnose refresh-telegram-proxy proxy-rotation-install proxy-rotation-status proxy-rotation-remove audit-cards validate-weights ci-local ci-local-docker test-web-contract-local security-gitleaks dataset-merge-three-class dataset-validate-yolo-labels dataset-verify-quality-gates dataset-verify-hard-negatives bootstrap-detector-data active-learning-trace-to-pool active-learning-pool-from-sqlite reid-import-embeddings ml-check-decode ml-export-decision-traces ml-build-registry-entry ml-verify-registry-entry ml-verify-benchmark-slices ml-verify-reid-gates ml-verify-action-labeling

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

# Verify detector dataset quality gates from exported profile JSON (#394).
# Example:
#   python3 scripts/datasets/export_detector_dataset_profile.py --dataset-root scripts/datasets/binary --out /tmp/detector_profile.json
#   make dataset-verify-quality-gates PROFILE=/tmp/detector_profile.json
dataset-verify-quality-gates:
	@test -n "$${PROFILE:-}" || (echo "Set PROFILE=path/to/detector_profile.json" >&2; exit 1)
	@python3 scripts/datasets/verify_detector_dataset_quality.py \
		--profile "$${PROFILE}" \
		$$(test -n "$${MIN_TRAIN:-}" && printf -- '--min-train "%s" ' "$${MIN_TRAIN}") \
		$$(test -n "$${MIN_VAL:-}" && printf -- '--min-val "%s" ' "$${MIN_VAL}") \
		$$(test -n "$${MAX_TRAIN_IMBALANCE_RATIO:-}" && printf -- '--max-train-imbalance-ratio "%s" ' "$${MAX_TRAIN_IMBALANCE_RATIO}") \
		$$(test -n "$${MIN_SOURCE_TAGS:-}" && printf -- '--min-source-tags "%s" ' "$${MIN_SOURCE_TAGS}") \
		$$(test -n "$${MAX_UNKNOWN_TAG_SHARE:-}" && printf -- '--max-unknown-tag-share "%s" ' "$${MAX_UNKNOWN_TAG_SHARE}") \
		$$(test -n "$${MIN_BACKGROUND_SHARE_TRAIN:-}" && printf -- '--min-background-share-train "%s" ' "$${MIN_BACKGROUND_SHARE_TRAIN}") \
		$$(test -n "$${MAX_BACKGROUND_SHARE_TRAIN:-}" && printf -- '--max-background-share-train "%s" ' "$${MAX_BACKGROUND_SHARE_TRAIN}")

# Verify hard negatives manifest schema and optional file existence (#394).
# Example:
#   make dataset-verify-hard-negatives MANIFEST=scripts/datasets/example_hard_negatives_manifest.json
#   make dataset-verify-hard-negatives MANIFEST=manifest.json DATASET_ROOT=scripts/datasets REQUIRE_EXISTING_FILES=1
dataset-verify-hard-negatives:
	@test -n "$${MANIFEST:-}" || (echo "Set MANIFEST=path/to/hard_negatives_manifest.json" >&2; exit 1)
	@python3 scripts/datasets/verify_hard_negatives_manifest.py \
		--manifest "$${MANIFEST}" \
		$$(test -n "$${DATASET_ROOT:-}" && printf -- '--dataset-root "%s" ' "$${DATASET_ROOT}") \
		$$(test "$${REQUIRE_EXISTING_FILES:-0}" = "1" && printf -- '--require-existing-files')

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

validate-weights:
	@python3 scripts/validate-processor-weights.py \
		--binary "$${BINARY:-app/processor/models/detection/weights/best.pt}" \
		--classifier "$${CLASSIFIER:-app/processor/models/classification/weights/best.pt}" \
		--class-names "$${CLASS_NAMES:-app/processor/models/classification/weights/class_names.txt}" \
		$$(test -n "$${DATASET_INFO:-}" && printf -- '--dataset-info "%s" ' "$${DATASET_INFO}") \
		$$(test -n "$${FUSION_MODEL:-}" && printf -- '--fusion-model "%s" ' "$${FUSION_MODEL}") \
		$$(test -n "$${OUTPUT:-}" && printf -- '--output "%s" ' "$${OUTPUT}")

# Build model registry candidate entry for release-train workflow (#393).
# Example:
#   make ml-build-registry-entry \
#     NAME=detector-20260429 STAGE=offline \
#     VALIDATION_REPORT=/tmp/processor-weight-validation.json \
#     BENCHMARK_REPORT=/tmp/benchmark-report.json \
#     DATASET_QUALITY_REPORT=/tmp/dataset_quality_report.json \
#     HARD_NEGATIVES_REPORT=/tmp/hard_negatives_report.json \
#     DETECTOR_PACKAGE_URL=https://.../weights.zip \
#     OUTPUT=/tmp/model_registry_entry.json
ml-build-registry-entry:
	@test -n "$${NAME:-}" || (echo "Set NAME=model-candidate-id" >&2; exit 1)
	@test -n "$${VALIDATION_REPORT:-}" || (echo "Set VALIDATION_REPORT=path/to/validate-report.json" >&2; exit 1)
	@test -n "$${OUTPUT:-}" || (echo "Set OUTPUT=path/to/model_registry_entry.json" >&2; exit 1)
	@python3 scripts/build_model_registry_entry.py \
		--name "$${NAME}" \
		--stage "$${STAGE:-offline}" \
		--source-issue "$${SOURCE_ISSUE:-}" \
		--validation-report "$${VALIDATION_REPORT}" \
		$$(test -n "$${BENCHMARK_REPORT:-}" && printf -- '--benchmark-report "%s" ' "$${BENCHMARK_REPORT}") \
		$$(test -n "$${DATASET_QUALITY_REPORT:-}" && printf -- '--dataset-quality-report "%s" ' "$${DATASET_QUALITY_REPORT}") \
		$$(test -n "$${HARD_NEGATIVES_REPORT:-}" && printf -- '--hard-negatives-report "%s" ' "$${HARD_NEGATIVES_REPORT}") \
		$$(test -n "$${DETECTOR_PACKAGE_URL:-}" && printf -- '--detector-package-url "%s" ' "$${DETECTOR_PACKAGE_URL}") \
		$$(test -n "$${CLASSIFIER_PACKAGE_URL:-}" && printf -- '--classifier-package-url "%s" ' "$${CLASSIFIER_PACKAGE_URL}") \
		$$(test -n "$${NOTES:-}" && printf -- '--notes "%s" ' "$${NOTES}") \
		--output "$${OUTPUT}"

# Verify model registry candidate against release gates (#393).
# Example:
#   make ml-verify-registry-entry ENTRY=/tmp/model_registry_entry.json \
#     MIN_STAGE=offline REQUIRE_BENCHMARK=1 REQUIRE_DATASET_READY=1 \
#     REQUIRE_DATASET_QUALITY=1 REQUIRE_HARD_NEGATIVES=1
ml-verify-registry-entry:
	@test -n "$${ENTRY:-}" || (echo "Set ENTRY=path/to/model_registry_entry.json" >&2; exit 1)
	@python3 scripts/verify_model_registry_entry.py \
		--entry "$${ENTRY}" \
		--min-stage "$${MIN_STAGE:-offline}" \
		$$(test "$${REQUIRE_BENCHMARK:-0}" = "1" && printf -- '--require-benchmark') \
		$$(test "$${REQUIRE_DATASET_READY:-0}" = "1" && printf -- '--require-dataset-ready') \
		$$(test "$${REQUIRE_DATASET_QUALITY:-0}" = "1" && printf -- '--require-dataset-quality') \
		$$(test "$${REQUIRE_HARD_NEGATIVES:-0}" = "1" && printf -- '--require-hard-negatives')

# Verify benchmark quality by context slices (season/camera/domain) (#391).
# Requires:
# - REPORT: benchmark-track-regen JSON
# - SLICE_MAP: JSON {"by_basename": {"clip.mp4": {"season":"...", "camera":"...", "domain":"..."}}}
ml-verify-benchmark-slices:
	@test -n "$${REPORT:-}" || (echo "Set REPORT=path/to/benchmark_report.json" >&2; exit 1)
	@test -n "$${SLICE_MAP:-}" || (echo "Set SLICE_MAP=path/to/slice_map.json" >&2; exit 1)
	@python3 scripts/verify_benchmark_slice_gates.py \
		--report "$${REPORT}" \
		--slice-map "$${SLICE_MAP}" \
		--min-gold-samples "$${MIN_GOLD_SAMPLES:-5}" \
		--min-recall "$${MIN_RECALL:-0.70}" \
		$$(test -n "$${GROUP_BY:-}" && printf -- '--group-by %s ' "$${GROUP_BY}")

# Verify Re-ID production gates (#389/#390) using API payload snapshots.
# Example:
#   make ml-verify-reid-gates REID_SUMMARY=/tmp/reid_summary.json REID_MATCH=/tmp/reid_match.json REQUIRE_CONTRACT_OK=1 MIN_SUGGESTION_COUNT=1
ml-verify-reid-gates:
	@test -n "$${REID_SUMMARY:-}" || (echo "Set REID_SUMMARY=path/to/reid_summary.json" >&2; exit 1)
	@python3 scripts/verify_reid_production_gates.py \
		--reid-summary "$${REID_SUMMARY}" \
		$$(test -n "$${REID_MATCH:-}" && printf -- '--reid-match %s ' "$${REID_MATCH}") \
		--min-embeddings "$${MIN_EMBEDDINGS:-1}" \
		--max-missing-contract-rows "$${MAX_MISSING_CONTRACT_ROWS:-0}" \
		$$(test "$${REQUIRE_CONTRACT_OK:-0}" = "1" && printf -- '--require-contract-ok') \
		$$(test -n "$${MAX_STALE_HOURS:-}" && printf -- '--max-stale-hours %s ' "$${MAX_STALE_HOURS}") \
		--min-suggestion-count "$${MIN_SUGGESTION_COUNT:-0}"

# Verify action-labeling protocol gates (#392) for API payload and/or dataset JSONL.
# Example:
#   make ml-verify-action-labeling ACTION_EVENTS=/tmp/action_events.json ACTION_DATASET=/tmp/action_dataset.jsonl
ml-verify-action-labeling:
	@{ test -n "$${ACTION_EVENTS:-}" || test -n "$${ACTION_DATASET:-}"; } || (echo "Set ACTION_EVENTS=... and/or ACTION_DATASET=..." >&2; exit 1)
	@python3 scripts/verify_action_labeling_gates.py \
		$$(test -n "$${ACTION_EVENTS:-}" && printf -- '--action-events %s ' "$${ACTION_EVENTS}") \
		$$(test -n "$${ACTION_DATASET:-}" && printf -- '--dataset-jsonl %s ' "$${ACTION_DATASET}") \
		--min-events "$${MIN_EVENTS:-1}" \
		--min-dataset-rows "$${MIN_DATASET_ROWS:-1}" \
		--min-segment-ms "$${MIN_SEGMENT_MS:-300}" \
		$$(test "$${ALLOW_EXTENDED_LABELS:-0}" = "1" && printf -- '--allow-extended-labels')

# Run positive and negative fixture checks for action-labeling gates (#392).
# Positive fixture must pass, negative fixture must fail.
ml-verify-action-labeling-fixtures:
	@python3 scripts/verify_action_labeling_gates.py \
		--action-events scripts/fixtures/action_labeling/action_events.valid.json \
		--dataset-jsonl scripts/fixtures/action_labeling/action_dataset.valid.jsonl \
		--min-events 1 \
		--min-dataset-rows 1 \
		--min-segment-ms 300
	@python3 scripts/verify_action_labeling_gates.py \
		--action-events scripts/fixtures/action_labeling/action_events.invalid.json \
		--dataset-jsonl scripts/fixtures/action_labeling/action_dataset.invalid.jsonl \
		--min-events 1 \
		--min-dataset-rows 1 \
		--min-segment-ms 300 >/dev/null 2>&1 && \
		(echo "Expected invalid fixtures to fail, but command succeeded" >&2; exit 1) || true

# Export weak-labeled action seed dataset rows for #392 E1.
# Example:
#   make ml-export-action-seed ACTION_DB=app/data/db/birdlense.db ACTION_SEED_JSONL=/tmp/action_seed.jsonl ACTION_SEED_MANIFEST=/tmp/action_seed_manifest.json
ml-export-action-seed:
	@test -n "$${ACTION_DB:-}" || (echo "Set ACTION_DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${ACTION_SEED_JSONL:-}" || (echo "Set ACTION_SEED_JSONL=path/to/action_seed.jsonl" >&2; exit 1)
	@python3 scripts/action/export_action_seed_dataset.py \
		--db-path "$${ACTION_DB}" \
		--output-jsonl "$${ACTION_SEED_JSONL}" \
		$$(test -n "$${ACTION_SEED_MANIFEST:-}" && printf -- '--manifest-json %s ' "$${ACTION_SEED_MANIFEST}") \
		--limit-videos "$${ACTION_LIMIT_VIDEOS:-400}" \
		--boundary-ms "$${ACTION_BOUNDARY_MS:-300}" \
		--min-track-duration-ms "$${ACTION_MIN_TRACK_DURATION_MS:-300}" \
		--min-tracks "$${ACTION_MIN_TRACKS:-1}" \
		--min-weight-delta-kg "$${ACTION_MIN_WEIGHT_DELTA_KG:-0.001}" \
		$$(test "$${ACTION_REQUIRE_WEIGHT_DELTA:-0}" = "1" && printf -- '--require-weight-delta') \
		--annotator-id "$${ACTION_ANNOTATOR_ID:-bootstrap_weak_label}" \
		$$(test -n "$${ACTION_VIDEO_IDS:-}" && printf -- '--video-ids %s ' "$${ACTION_VIDEO_IDS}")

# Compute Cohen's kappa for two annotator JSONL files.
# Example:
#   make ml-verify-action-agreement ACTION_ANN_A=/tmp/a.jsonl ACTION_ANN_B=/tmp/b.jsonl ACTION_MIN_KAPPA=0.75 ACTION_AGREEMENT_REPORT=/tmp/kappa.json
ml-verify-action-agreement:
	@test -n "$${ACTION_ANN_A:-}" || (echo "Set ACTION_ANN_A=path/to/annotator_a.jsonl" >&2; exit 1)
	@test -n "$${ACTION_ANN_B:-}" || (echo "Set ACTION_ANN_B=path/to/annotator_b.jsonl" >&2; exit 1)
	@python3 scripts/action/compute_action_agreement.py \
		--annotator-a-jsonl "$${ACTION_ANN_A}" \
		--annotator-b-jsonl "$${ACTION_ANN_B}" \
		$$(test -n "$${ACTION_MIN_KAPPA:-}" && printf -- '--min-kappa %s ' "$${ACTION_MIN_KAPPA}") \
		$$(test -n "$${ACTION_AGREEMENT_REPORT:-}" && printf -- '--output-json %s ' "$${ACTION_AGREEMENT_REPORT}")

# Build calibration subset and annotator templates from seed JSONL.
# Example:
#   make ml-prepare-action-calibration ACTION_SEED_JSONL=/tmp/action_seed.jsonl ACTION_CALIB_DIR=/tmp/action_calibration
ml-prepare-action-calibration:
	@test -n "$${ACTION_SEED_JSONL:-}" || (echo "Set ACTION_SEED_JSONL=path/to/action_seed.jsonl" >&2; exit 1)
	@test -n "$${ACTION_CALIB_DIR:-}" || (echo "Set ACTION_CALIB_DIR=path/to/output_dir" >&2; exit 1)
	@python3 scripts/action/prepare_action_calibration_pack.py \
		--seed-jsonl "$${ACTION_SEED_JSONL}" \
		--output-dir "$${ACTION_CALIB_DIR}" \
		--max-videos "$${ACTION_CALIB_MAX_VIDEOS:-60}" \
		--max-segments-per-video "$${ACTION_CALIB_SEGMENTS_PER_VIDEO:-2}" \
		--annotator-a "$${ACTION_CALIB_ANNOTATOR_A:-annotator_a}" \
		--annotator-b "$${ACTION_CALIB_ANNOTATOR_B:-annotator_b}"

# Run full E1 artifact pipeline (seed + calibration + agreement report).
# Example:
#   make ml-run-action-e1 ACTION_DB=app/data/db/birdlense.db ACTION_E1_DIR=/tmp/action_e1
ml-run-action-e1:
	@test -n "$${ACTION_DB:-}" || (echo "Set ACTION_DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${ACTION_E1_DIR:-}" || (echo "Set ACTION_E1_DIR=path/to/output_dir" >&2; exit 1)
	@python3 scripts/action/run_action_e1_pipeline.py \
		--db-path "$${ACTION_DB}" \
		--output-dir "$${ACTION_E1_DIR}" \
		--limit-videos "$${ACTION_LIMIT_VIDEOS:-400}" \
		--boundary-ms "$${ACTION_BOUNDARY_MS:-300}" \
		--min-track-duration-ms "$${ACTION_MIN_TRACK_DURATION_MS:-300}" \
		--min-tracks "$${ACTION_MIN_TRACKS:-1}" \
		--min-weight-delta-kg "$${ACTION_MIN_WEIGHT_DELTA_KG:-0.001}" \
		$$(test "$${ACTION_REQUIRE_WEIGHT_DELTA:-0}" = "1" && printf -- '--require-weight-delta') \
		--annotator-id "$${ACTION_ANNOTATOR_ID:-bootstrap_weak_label}" \
		--calib-max-videos "$${ACTION_CALIB_MAX_VIDEOS:-60}" \
		--calib-segments-per-video "$${ACTION_CALIB_SEGMENTS_PER_VIDEO:-2}" \
		--calib-annotator-a "$${ACTION_CALIB_ANNOTATOR_A:-annotator_a}" \
		--calib-annotator-b "$${ACTION_CALIB_ANNOTATOR_B:-annotator_b}" \
		$$(test -n "$${ACTION_ANN_A:-}" && printf -- '--agreement-ann-a %s ' "$${ACTION_ANN_A}") \
		$$(test -n "$${ACTION_ANN_B:-}" && printf -- '--agreement-ann-b %s ' "$${ACTION_ANN_B}") \
		--min-kappa "$${ACTION_MIN_KAPPA:-0.75}"

# Run consolidated E2 benchmark/recommendation report.
# Example:
#   make ml-run-action-e2 ACTION_GT=/tmp/action_gt.jsonl ACTION_PRED=/tmp/action_pred.jsonl ACTION_E2_REPORT=/tmp/action_e2_report.json
ml-run-action-e2:
	@test -n "$${ACTION_GT:-}" || (echo "Set ACTION_GT=path/to/ground_truth.jsonl" >&2; exit 1)
	@test -n "$${ACTION_PRED:-}" || (echo "Set ACTION_PRED=path/to/predictions.jsonl" >&2; exit 1)
	@test -n "$${ACTION_E2_REPORT:-}" || (echo "Set ACTION_E2_REPORT=path/to/output_report.json" >&2; exit 1)
	@python3 scripts/action/run_action_e2_pipeline.py \
		--ground-truth-jsonl "$${ACTION_GT}" \
		--predictions-jsonl "$${ACTION_PRED}" \
		--output-json "$${ACTION_E2_REPORT}" \
		--tolerance-sec "$${ACTION_TOLERANCE_SEC:-1.5}" \
		--quality-min-f1 "$${ACTION_QUALITY_MIN_F1:-0.70}" \
		--quality-max-delay-p95-sec "$${ACTION_QUALITY_MAX_DELAY_P95_SEC:-1.5}"

# Run E3 shadow report for action/Re-ID runtime + proxy outcomes.
# Example:
#   make ml-run-action-e3-shadow ACTION_E3_REPORT=/tmp/action_e3_shadow.json ACTION_WINDOW_HOURS=24 ACTION_VIDEO_LIMIT=300
ml-run-action-e3-shadow:
	@test -n "$${ACTION_E3_REPORT:-}" || (echo "Set ACTION_E3_REPORT=path/to/output_report.json" >&2; exit 1)
	@python3 scripts/action/run_action_e3_shadow_report.py \
		--output-json "$${ACTION_E3_REPORT}" \
		--window-hours "$${ACTION_WINDOW_HOURS:-24}" \
		--video-limit "$${ACTION_VIDEO_LIMIT:-300}" \
		--min-action-available-ratio "$${ACTION_MIN_ACTION_AVAILABLE_RATIO:-0.95}" \
		--min-reid-available-ratio "$${ACTION_MIN_REID_AVAILABLE_RATIO:-0.90}" \
		--max-reid-reject-proxy-ratio "$${ACTION_MAX_REID_REJECT_PROXY_RATIO:-0.50}"

# Benchmark action-model candidates on shared ground-truth JSONL.
# Example:
#   make ml-benchmark-action-candidates ACTION_GT=/tmp/gt.jsonl ACTION_PRED=/tmp/pred.jsonl ACTION_BENCHMARK_REPORT=/tmp/report.json
ml-benchmark-action-candidates:
	@test -n "$${ACTION_GT:-}" || (echo "Set ACTION_GT=path/to/ground_truth.jsonl" >&2; exit 1)
	@test -n "$${ACTION_PRED:-}" || (echo "Set ACTION_PRED=path/to/predictions.jsonl" >&2; exit 1)
	@python3 scripts/action/benchmark_action_candidates.py \
		--ground-truth-jsonl "$${ACTION_GT}" \
		--predictions-jsonl "$${ACTION_PRED}" \
		--tolerance-sec "$${ACTION_TOLERANCE_SEC:-1.5}" \
		$$(test -n "$${ACTION_BENCHMARK_REPORT:-}" && printf -- '--output-json %s ' "$${ACTION_BENCHMARK_REPORT}")
