.PHONY: install install-pull deploy build start stop logs verify verify-prod-env preflight-deploy verify-strict-quality restore-config docs docs-site diagnose refresh-telegram-proxy proxy-rotation-install proxy-rotation-status proxy-rotation-remove audit-cards validate-weights ci-local ci-local-docker test-web-contract-local security-gitleaks dataset-merge-three-class dataset-dedupe-detector-yolo dataset-report-detector-yolo dataset-dedupe-detector-binary dataset-import-cub dataset-import-roboflow-bird-feeder dataset-download-roboflow-bird-feeder dataset-validate-yolo-labels dataset-verify-quality-gates dataset-verify-hard-negatives bootstrap-detector-data bootstrap-rodents-until-verify bootstrap-bird-coco-only report-detector-bird-sources dataset-rebalance-bird-binary dataset-bootstrap-rodent-oid-fast dataset-import-roboflow-rodent dataset-fetch-lila-california-rodents-sample dataset-build-birds-rodents-quick dataset-build-detector-tz detector-etl-verify-birds-rodents detector-etl-progress detector-etl-progress-watch detector-etl-restart detector-etl-supervise detector-etl-supervise-bg active-learning-trace-to-pool active-learning-pool-from-sqlite reid-import-embeddings ml-check-decode ml-export-decision-traces ml-build-registry-entry ml-verify-registry-entry ml-verify-benchmark-slices ml-verify-reid-gates ml-run-reid-execution-report ml-verify-action-labeling ml-build-eval-dataset ml-build-behavior-dataset ml-build-behavior-train-report ml-offline-benchmark-gate ml-detector-shortlist ml-openvino-async-profile ml-decode-path-benchmark ml-track-continuity-eval ml-int8-candidate-eval ml-shadow-rollout-report ml-canary-rollback-report ml-full-rollout-watch-report ml-action-model-shortlist ml-proof ml-proof-local ml-proof-hub ml-fusion-ab-local ml-fusion-ab-hub dedupe-videos-local

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

# A1: локальная копия server app/.env (verify-prod-env) + живой хаб (DEPLOY_URL из deploy.local.sh)
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
# Канонический корень: datasets/new/detector/ — binary/{birds,rodent,background}, yolo/ (merge).
# Обратная совместимость: scripts/datasets/binary → symlink на datasets/new/detector/binary
dataset-merge-three-class:
	@python3 scripts/datasets/merge_datasets_three_class.py \
	  --birds-dir "$(CURDIR)/datasets/new/detector/binary/birds" \
	  --rodent-dir "$(CURDIR)/datasets/new/detector/binary/rodent" \
	  --background-dir "$(CURDIR)/datasets/new/detector/binary/background" \
	  --output-dir "$(CURDIR)/datasets/new/detector/yolo"

# Дедуп merged yolo/: по умолчанию только ВНУТРИ b_/r_/g_ (не трогать птицу из-за того же файла как фон).
# Опасный межклассовый режим: ARGS='--detector-merge-scope global' (осознанно).
# Восстановление yolo без повторной качки: make dataset-merge-three-class (из binary/).
dataset-dedupe-detector-yolo:
	@python3 scripts/datasets/dedupe_yolo_images.py \
	  --root "$(CURDIR)/datasets/new/detector/yolo" \
	  --detector-merge \
	  $(ARGS)

# Только отчёт по составу merged yolo/ (без изменений на диске).
dataset-report-detector-yolo:
	@python3 scripts/datasets/report_detector_yolo_dataset.py \
	  --root "$(CURDIR)/datasets/new/detector/yolo"

# Дедуп binary/…/images: только внутри одной папки класса (например rodent/train/images), без кросс-класса.
dataset-dedupe-detector-binary:
	@python3 scripts/datasets/dedupe_detector_binary_layout.py \
	  --root "$(CURDIR)/datasets/new/detector" \
	  $(ARGS)

# Скачать стартовые подмножества COCO + Open Images в три каталога (нужен pip install fiftyone).
# Переопределение лимитов: make bootstrap-detector-data ARGS='--birds-train 50 --birds-val 20'
# Большой детектор: scripts/datasets/DETECTOR_DATASET_QUALITY.md и build_detector_dataset_large.sh
bootstrap-detector-data:
	@cd scripts/datasets && python3 bootstrap_detector_yolo.py \
	  --root "$(CURDIR)/datasets/new/detector" \
	  $(ARGS)

# Плохая сеть: повторные zoo-load в bootstrap + циклический добор rodent до detector-etl-verify.
# Env: MAX_ROUNDS SLEEP_SEC CHUNK_SIZE BIRDLENSE_BOOTSTRAP_ZOO_RETRIES BIRDLENSE_BOOTSTRAP_CHUNK_MAX
bootstrap-rodents-until-verify:
	@DETECTOR_ETL_ROOT="$(CURDIR)/datasets/new/detector" \
	  BIRDLENSE_PYTHON="$(CURDIR)/.venv/bin/python" \
	  bash "$(CURDIR)/scripts/datasets/bootstrap_rodents_until_verify.sh"

# Добор только COCO bird (12-digit stem); CUB/Roboflow не удаляются. Квоты из env.
# Пример: BIRD_COCO_TRAIN=5000 BIRD_COCO_VAL=1000 make bootstrap-bird-coco-only
BIRD_COCO_TRAIN ?= 4500
BIRD_COCO_VAL ?= 1000
bootstrap-bird-coco-only:
	@"$${BIRDLENSE_PYTHON:-$(CURDIR)/.venv/bin/python}" \
	  "$(CURDIR)/scripts/datasets/bootstrap_detector_yolo.py" \
	  --root "$(CURDIR)/datasets/new/detector" \
	  --skip-rodents --skip-background --skip-birds-oid \
	  --birds-train "$(BIRD_COCO_TRAIN)" \
	  --birds-val "$(BIRD_COCO_VAL)"

report-detector-bird-sources:
	@python3 "$(CURDIR)/scripts/datasets/report_detector_bird_sources.py" \
	  --root "$(CURDIR)/datasets/new/detector"

# Урезать перекос CUB/Roboflow → целевая доля COCO+OID + ровнее train/val/test. По умолчанию dry-run; запись: ARGS='--execute'
dataset-rebalance-bird-binary:
	@python3 "$(CURDIR)/scripts/datasets/rebalance_detector_bird_binary.py" \
	  --root "$(CURDIR)/datasets/new/detector" \
	  $(ARGS)

# Быстро: волны COCO Bird + OID Bird + Rodent (OID), без фона; merge + verify. Опционально LILA — см. скрипт.
dataset-build-birds-rodents-quick:
	@bash "$(CURDIR)/scripts/datasets/build_detector_birds_rodents_quick.sh"

# Полный ТЗ-пайплайн: волны A–E → verify binary → merge → dedupe yolo → validate labels.
dataset-build-detector-tz:
	@bash "$(CURDIR)/scripts/datasets/build_detector_dataset_tz.sh"

# Подмешать CUB-200-2011 в binary/birds (нужен распакованный датасет). Пример:
#   make dataset-import-cub CUB_ROOT=~/data/CUB_200_2011
dataset-import-cub:
	@test -n "$(CUB_ROOT)" || (echo "Set CUB_ROOT=/path/to/CUB_200_2011 ( unpacked images/ + *.txt )" >&2; exit 1)
	@python3 scripts/datasets/convert_cub_to_yolo.py \
	  --root "$(CURDIR)/datasets/new/detector" \
	  --cub-root "$(CUB_ROOT)"

# ZIP экспорта Roboflow YOLOv11 (Bird-Feeder и др.) → datasets/new/detector/binary/birds.
# Скачать v3: https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11
#   make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=~/Downloads/....zip
dataset-import-roboflow-bird-feeder:
	@test -n "$(ROBOFLOW_ZIP)" || (echo "Set ROBOFLOW_ZIP=/path/to/Roboflow-YOLOv11-export.zip" >&2; exit 1)
	@python3 scripts/datasets/import_roboflow_bird_feeder_birds.py \
	  --root "$(CURDIR)/datasets/new/detector" \
	  --zip "$(ROBOFLOW_ZIP)"

# Open Images validation-only → binary/rodent (быстро; обычно RGB днём). Переменные: RODENT_OID_TRAIN, RODENT_OID_VAL, RODENT_CHUNK, RODENT_CLASSES, DETECTOR_ETL_ROOT, BIRDLENSE_PYTHON.
dataset-bootstrap-rodent-oid-fast:
	@bash "$(CURDIR)/scripts/datasets/bootstrap_rodent_oid_fast.sh"

# Roboflow YOLOv11 → binary/rodent (IR/thermal/nocturnal — качайте экспорт на Universe и укажите ZIP).
dataset-import-roboflow-rodent:
	@test -n "$(ROBOFLOW_ZIP)" || (echo "Set ROBOFLOW_ZIP=/path/to/rodent-YOLOv11.zip" >&2; exit 1)
	@python3 scripts/datasets/import_roboflow_bird_feeder_birds.py \
	  --root "$(CURDIR)/datasets/new/detector" \
	  --zip "$(ROBOFLOW_ZIP)" \
	  --binary-subdir rodent \
	  --prefix "$(RODENT_RF_PREFIX)"

RODENT_RF_PREFIX ?= rfir_

# LILA California Small Animals (подвыборка по грызуну‑подобным категориям) → binary/rodent. Нужна сеть. ARGS: --max-images 3000 --metadata-zip ...
dataset-fetch-lila-california-rodents-sample:
	@python3 "$(CURDIR)/scripts/datasets/fetch_lila_california_rodents_sample.py" \
	  --root "$(CURDIR)/datasets/new/detector" \
	  $(ARGS)

# Скачать Bird-Feeder v3 через Roboflow API и импортировать в binary/birds (pip install roboflow).
# export ROBOFLOW_API_KEY='…'   — ключ не хранить в репозитории; при утечке отозвать в Roboflow.
dataset-download-roboflow-bird-feeder:
	@test -n "$${ROBOFLOW_API_KEY:-}" || (echo "Set ROBOFLOW_API_KEY (see scripts/datasets/download_roboflow_bird_feeder.py)" >&2; exit 1)
	@python3 scripts/datasets/download_roboflow_bird_feeder.py \
	  --root "$(CURDIR)/datasets/new/detector"

# Порог JPEG train/val птицы+грызуны (план large волн A+B+C). Exit 1 при недостаче — для CI или ручной догонки.
# Пример: DETECTOR_LOG_SCAN=1 make detector-etl-verify-birds-rodents
detector-etl-verify-birds-rodents:
	@DETECTOR_ETL_ROOT="$(CURDIR)/datasets/new/detector" bash "$(CURDIR)/scripts/datasets/verify_detector_binary_inventory.sh"

# Счётчики JPEG под binary/, кэш COCO, процессы bootstrap, хвост datasets/logs/detector_waves.log.
# Непрерывно: DETECTOR_WATCH_INTERVAL=12 make detector-etl-progress-watch
detector-etl-progress:
	@DETECTOR_ETL_ROOT="$(CURDIR)/datasets/new/detector" DETECTOR_WAVES_LOG="$(CURDIR)/datasets/logs/detector_waves.log" bash "$(CURDIR)/scripts/datasets/detector_etl_progress.sh"

detector-etl-progress-watch:
	@DETECTOR_ETL_ROOT="$(CURDIR)/datasets/new/detector" DETECTOR_WAVES_LOG="$(CURDIR)/datasets/logs/detector_waves.log" WATCH_INTERVAL="$${DETECTOR_WATCH_INTERVAL:-15}" bash "$(CURDIR)/scripts/datasets/detector_etl_progress.sh" watch

# Остановить bootstrap/waves и снова поднять волны (по умолчанию D+E, см. скрипт).
detector-etl-restart:
	@bash "$(CURDIR)/scripts/datasets/restart_detector_dataset_waves.sh"

# Держать волны до конца или перезапускать при падении (см. detector_etl_supervisor.sh).
detector-etl-supervise:
	@bash "$(CURDIR)/scripts/datasets/detector_etl_supervisor.sh"

detector-etl-supervise-bg:
	@cd "$(CURDIR)" && mkdir -p datasets/logs && \
	  POLL_SEC="$${POLL_SEC:-120}" nohup bash scripts/datasets/detector_etl_supervisor.sh >>datasets/logs/detector_etl_supervisor.log 2>&1 & \
	  echo $$! > datasets/logs/detector_etl_supervisor.pid && \
	  echo "supervisor PID $$(cat datasets/logs/detector_etl_supervisor.pid) → datasets/logs/detector_etl_supervisor.log"
# Validate YOLO labels before Colab training. Example:
# LABELS_DIR=datasets/new/detector/yolo/train/labels CLASS_COUNT=3 make dataset-validate-yolo-labels
dataset-validate-yolo-labels:
	@test -n "$${LABELS_DIR:-}" || (echo "Set LABELS_DIR=path/to/labels" >&2; exit 1)
	@python3 scripts/datasets/validate_yolo_labels.py "$${LABELS_DIR}" --class-count "$${CLASS_COUNT:-3}"

# Verify detector dataset quality gates from exported profile JSON (#394).
# Example:
#   python3 scripts/datasets/export_detector_dataset_profile.py --dataset-root datasets/new/detector --out /tmp/detector_profile.json
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

# Daily offline SSL/Re-ID cycle (extract -> embed -> recluster -> report).
# Example:
#   DB=app/data/db/birdlense.db REID_SSL_REPORT=app/data/reid_ssl_reports/latest.json make reid-ssl-daily
reid-ssl-daily:
	@test -n "$${DB:-}" || (echo "Set DB=path/to/birdlense.db" >&2; exit 1)
	@test -n "$${REID_SSL_REPORT:-}" || (echo "Set REID_SSL_REPORT=path/to/report.json" >&2; exit 1)
	@python3 scripts/reid/run_daily_ssl_cycle.py \
		--db "$${DB}" \
		--window-hours "$${REID_SSL_WINDOW_HOURS:-24}" \
		--limit "$${REID_SSL_LIMIT:-400}" \
		--cluster-threshold "$${REID_SSL_CLUSTER_THRESHOLD:-0.88}" \
		$$(test "$${REID_SSL_UPDATE_VIDEO_NICKNAMES:-0}" = "1" && printf -- '--update-video-nicknames ') \
		--report-json "$${REID_SSL_REPORT}" \
		$${ARGS:-}

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

# Train sklearn logistic baseline + export numpy weights for processor (#416 Wave 2).
# Requires: pip install scikit-learn numpy
# Example:
# MANIFEST=/tmp/behavior_dataset_manifest.v1.json EXPORT=/tmp/behavior_export.json PRED=/tmp/behavior_predictions.json make ml-train-behavior-baseline
ml-train-behavior-baseline:
	@test -n "$${MANIFEST:-}" || (echo "Set MANIFEST=path/to/behavior_dataset_manifest.v1.json" >&2; exit 1)
	@test -n "$${EXPORT:-}" || (echo "Set EXPORT=path/to/behavior_logistic_export.json" >&2; exit 1)
	@test -n "$${PRED:-}" || (echo "Set PRED=path/to/behavior_predictions.json" >&2; exit 1)
	@PY="$$(test -x app/.venv/bin/python && echo app/.venv/bin/python || command -v python3)"; \
	"$$PY" scripts/ml_behavior_train_baseline.py \
		--manifest "$${MANIFEST}" \
		--export-out "$${EXPORT}" \
		--predictions-out "$${PRED}" \
		$$(test -n "$${MAX_ITER:-}" && printf -- '--max-iter "%s" ' "$${MAX_ITER}") \
		$$(test -n "$${SEED:-}" && printf -- '--seed "%s" ' "$${SEED}") \
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
		--binary "$${BINARY:-app/processor/models/detection/weights/yolo11n.pt}" \
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

# Run execution-level Re-ID report for #389 (nearline shadow + failover + rollback checks).
# Example:
#   make ml-run-reid-execution-report REID_EXEC_REPORT=/tmp/reid_exec_report.json REID_WINDOW_HOURS=168 REID_VIDEO_LIMIT=300
ml-run-reid-execution-report:
	@test -n "$${REID_EXEC_REPORT:-}" || (echo "Set REID_EXEC_REPORT=path/to/reid_execution_report.json" >&2; exit 1)
	@python3 scripts/reid/run_reid_execution_report.py \
		--output-json "$${REID_EXEC_REPORT}" \
		--window-hours "$${REID_WINDOW_HOURS:-168}" \
		--video-limit "$${REID_VIDEO_LIMIT:-300}" \
		--min-embeddings "$${MIN_EMBEDDINGS:-1}" \
		--max-missing-contract-rows "$${MAX_MISSING_CONTRACT_ROWS:-0}" \
		--max-stale-hours "$${MAX_STALE_HOURS:-8760}" \
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

# Build E4 guarded rollout go/no-go report from E2+E3 artifacts.
# Example:
#   make ml-run-action-e4 ACTION_E2_REPORT=/tmp/action_e2_report.json ACTION_E3_SWEEP_REPORT=/tmp/action_e3_sweep.json ACTION_E4_REPORT=/tmp/action_e4_report.json
ml-run-action-e4:
	@test -n "$${ACTION_E2_REPORT:-}" || (echo "Set ACTION_E2_REPORT=path/to/action_e2_report.json" >&2; exit 1)
	@test -n "$${ACTION_E3_SWEEP_REPORT:-}" || (echo "Set ACTION_E3_SWEEP_REPORT=path/to/action_e3_sweep.json" >&2; exit 1)
	@test -n "$${ACTION_E4_REPORT:-}" || (echo "Set ACTION_E4_REPORT=path/to/action_e4_report.json" >&2; exit 1)
	@python3 scripts/action/run_action_e4_guarded_rollout_report.py \
		--e2-report "$${ACTION_E2_REPORT}" \
		--e3-sweep-report "$${ACTION_E3_SWEEP_REPORT}" \
		--required-windows "$${ACTION_E4_REQUIRED_WINDOWS:-120,168}" \
		--output-json "$${ACTION_E4_REPORT}"

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

# Sweep E3 shadow report over multiple time windows and select best evidence window.
# Example:
#   make ml-run-action-e3-sweep ACTION_E3_DIR=/tmp/action_e3_sweep ACTION_E3_SWEEP_REPORT=/tmp/action_e3_sweep.json ACTION_E3_WINDOWS=24,48,72,120,168,336
ml-run-action-e3-sweep:
	@test -n "$${ACTION_E3_DIR:-}" || (echo "Set ACTION_E3_DIR=path/to/sweep_output_dir" >&2; exit 1)
	@test -n "$${ACTION_E3_SWEEP_REPORT:-}" || (echo "Set ACTION_E3_SWEEP_REPORT=path/to/final_report.json" >&2; exit 1)
	@python3 scripts/action/run_action_e3_shadow_sweep.py \
		--runner-path scripts/action/run_action_e3_shadow_report.py \
		--output-dir "$${ACTION_E3_DIR}" \
		--windows "$${ACTION_E3_WINDOWS:-24,48,72,120,168,336}" \
		--video-limit "$${ACTION_VIDEO_LIMIT:-1200}" \
		--min-action-available-ratio "$${ACTION_MIN_ACTION_AVAILABLE_RATIO:-0.95}" \
		--min-reid-available-ratio "$${ACTION_MIN_REID_AVAILABLE_RATIO:-0.90}" \
		--max-reid-reject-proxy-ratio "$${ACTION_MAX_REID_REJECT_PROXY_RATIO:-0.50}" \
		$$(test "$${ACTION_REQUIRE_SUGGESTIONS:-0}" = "1" && printf -- '--require-suggestions ') \
		--output-json "$${ACTION_E3_SWEEP_REPORT}"

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
