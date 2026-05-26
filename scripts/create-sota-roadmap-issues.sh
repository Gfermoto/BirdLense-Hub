#!/usr/bin/env bash
# One-shot: create SOTA roadmap GitHub issues (sequential backlog).
# Usage: ./scripts/create-sota-roadmap-issues.sh
# Requires: gh auth, repo Gfermoto/BirdLense-Hub

set -euo pipefail
REPO="Gfermoto/BirdLense-Hub"

create_issue() {
  local title="$1"
  local labels="$2"
  local body="$3"
  gh issue create --repo "$REPO" --title "$title" --label "$labels" --body "$body"
}

# --- Epic (created first; child numbers added manually in follow-up comment) ---
EPIC_URL=$(create_issue \
  "[Roadmap] SOTA BirdLense Hub 2026 — эпик и порядок областей" \
  "enhancement,documentation" \
  "$(cat <<'EOF'
## Цель
Пошагово довести каждую подсистему хаба до SOTA: **одна область за раз**, без «большого взрыва», без хардкодов (всё через конфиг/UI).

## Правила
1. Не начинать область N+1, пока N не закрыта (код + тесты + полевой smoke).
2. Любой PR привязывать к issue `[SOTA-XX]`.
3. Приоритет полевых болей: **детекция → боксы → треки → классификация → каталог**.

## Области (последовательность)
| # | Область | Issues |
|---|---------|--------|
| 1 | Конфигурация и адаптивность | SOTA-01 … SOTA-04 |
| 2 | Триггеры и детекция (+ боксы) | SOTA-05 … SOTA-09 |
| 3 | Трекинг и ReID | SOTA-10 … SOTA-13 |
| 4 | Классификация и каталог | SOTA-14 … SOTA-18 |
| 5 | Потоки и производительность | SOTA-19 … SOTA-21 |
| 6 | API, UI, хранение | SOTA-22 … SOTA-24 |

Дочерние issues создаются скриптом `scripts/create-sota-roadmap-issues.sh`; номера в заголовках — источник правды для порядка работ.

## Связанные открытые issues
- #376 ESPHome LD2450
- #350 NAS storage
- #243 QA весы

## Закрытый фундамент (не дублировать)
- #484–#490 Processor W1 async/backpressure
- #483 SOTA 2.0 ScoringEngine
EOF
)")
echo "Epic: $EPIC_URL"

issues=(
# Area 1
"[SOTA-01] Config Contract: Pydantic/JSON Schema для processor.* и video.*|enhancement,area:processor,area:web|$(cat <<'EOF'
## Контекст
Область **1 — Конфигурация**. Блокирует остальные области.

## Текущее
- `default_config.yaml` + merge `user_config.yaml`
- Частично UI Settings; env-переопределения (`BIRDLENSE_*`)

## Проблемы
- Нет единой схемы валидации при старте
- Legacy-ключи и дубли
- Ошибки конфига обнаруживаются в runtime на кормушке

## Задачи
- [ ] Pydantic-модели (или JSON Schema) для `processor`, `video`, `species`, `detection`
- [ ] Валидация при `create_app` / bootstrap процессора с понятными ошибками
- [ ] Документ: mapping YAML → typed config
- [ ] Тесты: invalid config → fail fast

## DoD
`make ci-local` green; невалидный `user_config` не поднимает процессор.

## Depends on
Roadmap epic
EOF
)"

"[SOTA-02] Probe-driven pipeline: FPS и разрешение с Go2RTC/камеры|enhancement,area:processor|$(cat <<'EOF'
## Контекст
Область **1**. Расширить `pipeline_config.py` / `inference_lores.py`.

## Проблемы
- Fallback `30.0` FPS в `video_file_source.py`, `track_regenerator.py`
- `704×576` зашито в дефолтах без probe substream

## Задачи
- [ ] Probe stream metadata (WxH, FPS) при старте сессии
- [ ] Автовыбор `inference_lores_wh`, `tracker_fps_profiles`, `binary_imgsz` от probe
- [ ] UI: read-only «обнаружено: 704×576 @ 7fps» + override
- [ ] Убрать magic defaults из кода → только `resolve_*()` + documented fallback

## DoD
Новая камера без правки YAML получает согласованный detect substream.

## Depends on
SOTA-01
EOF
)"

"[SOTA-03] Config migration v1: user_config upgrades и audit|enhancement,area:web,area:processor|$(cat <<'EOF'
## Контекст
Область **1**.

## Задачи
- [ ] Версия `user_config` + миграции (rename keys)
- [ ] `GET /api/ui/system/config-audit` — unknown/deprecated keys
- [ ] UI: предупреждение при сохранении настроек с deprecated keys

## DoD
Апгрейд с старого `user_config` не ломает детекцию (smoke на file_test).

## Depends on
SOTA-01
EOF
)"

"[SOTA-04] UI Settings: закрыть пробелы processor.* (без правки YAML)|enhancement,area:web|$(cat <<'EOF'
## Контекст
Область **1**.

## Проблемы
- Критичные ключи только в YAML (`track_regen_*`, OpenVINO, MOG2)
- UI fallback `640` в Processor*Block

## Задачи
- [ ] Инвентарь ключей «только YAML» → перенос в Settings (группы: Detect, Track, Regen)
- [ ] Убрать хардкод default 640 в UI — из OpenAPI/schema defaults
- [ ] codegen:openapi + typecheck

## DoD
Оператор на VPS меняет пороги детекции/трека без SSH.

## Depends on
SOTA-01, SOTA-02
EOF
)"

# Area 2 — detection + bboxes (user pain)
"[SOTA-05] [Поле] Детекция: YOLO «слепой» при живом Frigate — диагностика и gate|bug,area:processor|$(cat <<'EOF'
## Претензия оператора
Frigate видит объект, YOLO/Trapper на хабе — нет (`yolo_frames_with_tracks = 0`).

## Текущее
- Trapper v02 prod @ 704, torch/OpenVINO
- `user_config` может перекрывать `default_config` (openvino, пороги)

## Задачи
- [ ] Runbook: checklist (backend, imgsz, lores_wh, conf, scope, heartbeat)
- [ ] Метрика в `recording_session_summary` + алерт в System UI
- [ ] Quality gate: `yolo_frames_with_tracks` на эталонных клипах 1816/1819
- [ ] Сравнение torch vs OpenVINO на одном mp4 (`compare_detector_bboxes.py`)

## DoD
На VPS после деплоя smoke: regen эталонных роликов > 0 треков; документирован root-cause tree.

## Depends on
SOTA-02 (probe)
EOF
)"

"[SOTA-06] Боксы: letterbox/native resolution и parity overlay vs live|bug,area:processor|$(cat <<'EOF'
## Претензия
Несовпадение боксов live/regen/UI; «плывущие» или пустые оверлеи.

## Задачи
- [ ] Единый `yolo_geometry` контракт для live, regen, export crops
- [ ] Тест: bbox IoU live vs regen на file_test clip
- [ ] UI overlay path согласован с `track_regen_lores_wh`
- [ ] Док: когда `detect_use_native_resolution` vs letterbox

## DoD
`compare_detector_bboxes.py` PT vs OV < порога на golden clips; regen overlay совпадает с live в пределах IoU.

## Depends on
SOTA-05
EOF
)"

"[SOTA-07] Триггеры: модульный trigger graph + метрики FP/FN по источнику|enhancement,area:processor|$(cat <<'EOF'
## Контекст
Область **2**.

## Проблемы
- Дубли клипов (`min_seconds_between_recordings` — симптом)
- Нет attribution: какой триггер дал ложную запись

## Задачи
- [ ] Decision trace: trigger → detect window → record (уже частично есть — унифицировать)
- [ ] Prometheus gauges per trigger (start/stop/false positive proxy)
- [ ] UI System: таблица «триггеры за 24h»

## DoD
По одному ролику видно цепочку триггеров; метрики в Grafana/prometheus endpoint.

## Depends on
SOTA-05
EOF
)"

"[SOTA-08] MOG2/static-object/Frigate prior: калибровка из UI + val clips|enhancement,area:processor,area:web|$(cat <<'EOF'
## Проблемы
- FP на корме/фоне; `scoring_frigate_prior_boost` без визуальной калибровки
- Маски detection — частично UI

## Задачи
- [ ] Preset profiles: «кормушка день/ночь» (MOG2 + binary thresholds)
- [ ] Val harness: precision/recall на размеченных клипах
- [ ] Mask editor ↔ processor reload без рестарта (если возможно)

## DoD
Снижение FP на эталонном наборе без роста FN на птицах.

## Depends on
SOTA-06, SOTA-07
EOF
)"

"[SOTA-09] Benchmark harness: европейский showdown + regression в CI|enhancement,area:processor|$(cat <<'EOF'
## Задачи
- [ ] Зафиксировать golden set (1816, 1819, trapper_test_1952)
- [ ] CI job (light): bbox count, mean conf, tracks/frame без полного YOLO OOM
- [ ] Отчёт `docs/reports/` автоген из скрипта

## DoD
PR с изменением детектора не мержится без regression gate.

## Depends on
SOTA-06
EOF
)"

# Area 3 — tracks
"[SOTA-10] Треки: стабильность ID на низком FPS (ByteTrack tuning)|bug,area:processor|$(cat <<'EOF'
## Претензия
Рваные `track_id`, короткие визиты → `rejected_short_track`, пустой timeline.

## Задачи
- [ ] Аудит `tracker_fps_profiles`, `bytetrack_birdlense_lowfps.yaml`
- [ ] Метрики: track length distribution, ID switches per session
- [ ] Док: `min_track_duration` vs `track_regen_min_track_duration`
- [ ] Полевой A/B на 5–7 FPS substream

## DoD
На эталонных роликах median track duration ↑, rejected_short ↓ без взрыва FP.

## Depends on
SOTA-06
EOF
)"

"[SOTA-11] Live vs regen: единая политика детекции и порогов|enhancement,area:processor|$(cat <<'EOF'
## Проблемы
- `track_regen_*` дублирует live keys с другими значениями
- Regen `frame_step` даёт пустые треки на слабом бинарнике

## Задачи
- [ ] Single `PipelinePolicy` resolver для live + regen (override flags explicit)
- [ ] UI: «regen = live policy» toggle
- [ ] Тест: same video live slice vs regen IoU/tracks

## DoD
Оператор понимает одну матрицу порогов; regen не «ломает» то, что видел live.

## Depends on
SOTA-10
EOF
)"

"[SOTA-12] Tracker abstraction: оценка BoT-SORT / OC-SORT на wildlife clips|enhancement,area:processor|$(cat <<'EOF'
## SOTA research
- ByteTrack (текущий)
- BoT-SORT / OC-SORT для low-FPS wildlife

## Задачи
- [ ] Plugin interface `TrackerBackend`
- [ ] Offline benchmark MOTA/IDF1 на 3–5 роликах
- [ ] Рекомендация + YAML preset

## DoD
Отчёт с цифрами; если выигрыш <5% — остаёмся на ByteTrack с улучшенным YAML.

## Depends on
SOTA-10
EOF
)"

"[SOTA-13] ReID: gallery policies + expert queue hardening|enhancement,area:processor,area:web|$(cat <<'EOF'
## Задачи
- [ ] DINOv2 embed quality metrics (intra/inter species)
- [ ] Auto-link thresholds в конфиг + UI
- [ ] Expert queue: batch approve, conflict resolution

## DoD
ReID не создаёт ложных global profiles на коротких треках.

## Depends on
SOTA-10
EOF
)"

# Area 4 — classification + catalog (user pain)
"[SOTA-14] Каталог: 526/526 карточки (фото+описание) — остаток 38 без фото|bug,area:web|$(cat <<'EOF'
## Претензия
Каталог неполный: на prod `complete_cards=488`, `missing_image_lines=38`.

## Текущее
- `catalog_deep_polish.py`, repair API, quality-gate (CAPS=0 ✅)

## Задачи
- [ ] Список 38 видов + root cause (iNat, allowlist science name, rate limit)
- [ ] Batch repair до 526/526
- [ ] Gate `REQUIRE_COMPLETE_CARDS=1` в release checklist

## DoD
`make quality-gate` с полным cards gate PASS на prod.

## Depends on
SOTA-01 (config)
EOF
)"

"[SOTA-15] Каталог: eBird/Clements — стабильность имён и plumage variants|bug,area:web|$(cat <<'EOF'
## Претензия
ALL CAPS, group labels («Starlings and Allies»), сломанные plumage (`Breeding male` без вида).

## Текущее
- `canon.py`, `restore_plumage_variant_display_names`, deep reconcile

## Задачи
- [ ] Регрессионные тесты на 20+ plumage строк из `hierarchy_names.txt`
- [ ] Reconcile dry-run обязателен перед apply на prod
- [ ] UI: каталог `/species` vs quality `/species-directory` (не путать)

## DoD
`all_caps_matched_species=0`, нет species-card для taxon nodes; plumage restore в deep reconcile.

## Depends on
SOTA-14
EOF
)"

"[SOTA-16] Классификация: калибровка confidence (мышь→синица, rodent vs bird)|bug,area:processor|$(cat <<'EOF'
## Претензия
Неверный вид при уверенном детекторе; `min_confidence_binary_bird` vs rodent.

## Задачи
- [ ] Temperature scaling / threshold sweep на val set
- [ ] `bird_skip_classifier_max_area_frac` — UI + док с рекомендациями
- [ ] Отчёт confusion top-10 на corrections из БД

## DoD
Top FP pairs снижены на val; пороги в default_config обоснованы цифрами.

## Depends on
SOTA-05, SOTA-11
EOF
)"

"[SOTA-17] Fusion/scoring: прозрачность источников в UI (YOLO/Frigate/BirdNET)|enhancement,area:processor,area:web|$(cat <<'EOF'
## Задачи
- [ ] Video details: breakdown ScoringEngine (уже debug routes — в UX)
- [ ] Contributor: «почему этот вид» tooltip
- [ ] Тесты scoring paths

## DoD
Оператор видит, кто дал label и с каким весом.

## Depends on
SOTA-16
EOF
)"

"[SOTA-18] Аудио каталога: KPI Xeno-canto + resolver для group labels|enhancement,area:web|$(cat <<'EOF'
## Задачи
- [ ] `cards_with_audio_source` KPI (sample probe opt-in)
- [ ] `audio_search_term_for_species_name` coverage test
- [ ] UI filter «без аудио»

## DoD
Доля видов с валидным audio URL ≥ целевого порога или documented exceptions.

## Depends on
SOTA-15
EOF
)"

# Area 5
"[SOTA-19] Backpressure: harden W1 queues (detector/classifier/finalize)|enhancement,area:processor|$(cat <<'EOF'
## Контекст
#487–#490 закрыты — нужен field hardening.

## Задачи
- [ ] Stress test: 10 parallel regen + live recording
- [ ] Metrics: queue depth, drop count, finalize fallback sync
- [ ] OOM 137 playbook

## DoD
Нет exit 137 на VPS при нормальной нагрузке 24h.

## Depends on
SOTA-11
EOF
)"

"[SOTA-20] Zero-copy ROI: завершить FrameContext path|enhancement,area:processor|$(cat <<'EOF'
## Контекст
#486 W1.2 — довести до classifier/ReID crops.

## Задачи
- [ ] Audit memcpy hotspots in hot loop
- [ ] `classifier_use_source_frame` без лишних copy

## DoD
Профиль: −X% CPU на 7fps detect stream (замер документирован).

## Depends on
SOTA-19
EOF
)"

"[SOTA-21] Track regen: admission control и SLA|enhancement,area:processor,area:web|$(cat <<'EOF'
## Задачи
- [ ] Global regen semaphore (interprocess lock уже есть — метрики)
- [ ] UI: regen queue position, cancel
- [ ] p95 regen duration SLO

## DoD
Ручной regen не валит live processor.

## Depends on
SOTA-19
EOF
)"

# Area 6
"[SOTA-22] Async jobs API: catalog repair, regen, export|enhancement,area:web|$(cat <<'EOF'
## Проблемы
- Долгие ops в threads без единого job id/status

## Задачи
- [ ] `POST /jobs` + `GET /jobs/{id}` pattern
- [ ] Migrate catalog repair, track regen, dataset export

## DoD
UI polls job status; CSRF-safe; OpenAPI documented.

## Depends on
SOTA-14
EOF
)"

"[SOTA-23] Timeline read models: производительность SQLite/Postgres|enhancement,area:web|$(cat <<'EOF'
## Задачи
- [ ] Explain analyze top queries
- [ ] Индексы (#014 частично) — gap analysis
- [ ] Pagination contract

## DoD
Timeline p95 < 500ms на 10k visits (цель документировать).

## Depends on
SOTA-22
EOF
)"

"[SOTA-24] UX ops: каталог, quality, observability единая навигация|enhancement,area:web|$(cat <<'EOF'
## Претензия
Путаница каталог vs карточки качества (исправлено частично в d6ef5bd).

## Задачи
- [ ] PageHelp для `/species` и `/species-directory`
- [ ] System dashboard: catalog + detection health one screen
- [ ] i18n audit

## DoD
Новый оператор без README понимает, где оглавление, где полировка.

## Depends on
SOTA-15, SOTA-17
EOF
)"
)

for spec in "${issues[@]}"; do
  IFS='|' read -r title labels body <<< "$spec"
  url=$(create_issue "$title" "$labels" "$body")
  echo "$url"
  sleep 1
done

echo "Done. Epic: $EPIC_URL"
