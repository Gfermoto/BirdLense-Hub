# Issue #516 — чеклист приёмки

**Статус:** закрыто (2026-05-28). Prod: VPS `185.218.111.196:8085`, UI `birdlense.eyera.info`.

## Wave A — PoC + артефакты

- [x] `scripts/download_birder_classifier.py`
- [x] Smoke / export OpenVINO (`scripts/export_birder_classifier_to_openvino.py`)
- [x] Бенчмарк latency — **prod:** `convnext_v2_tiny_eu-common256px` OpenVINO (~120 ms/crop VPS)
- [x] `docs/reports/birder_eu_classifier_poc.md`

## Wave B — Интеграция под ключ

- [x] `processor.classifier_engine: birder_eu` (default)
- [x] Runtime `birder_eu_classifier.py` (torch + OpenVINO, GPU `intel:gpu`)
- [x] Плоский layout весов: `convnext_v2_tiny_eu-common256px.pt` + `*_openvino_model/`
- [x] `classifier_model_layout.py`, `migrate_classifier_weights_layout.sh`
- [x] Legacy EfficientNet/YOLO classifier paths убраны из prod default
- [x] Прод: deploy, `classifier_engine=birder_eu`, 707 labels в логах
- [x] Валидация на роликах [#2140](https://birdlense.eyera.info/videos/2140) / [#2152](https://birdlense.eyera.info/videos/2152) — Eurasian Magpie, overlay следует за птицей (`478af8720`)

## Wave C — Каталог

- [ ] Reconcile Collins 707 → каталог Hub — **отдельно** ([#506](https://github.com/Gfermoto/BirdLense-Hub/issues/506) scope), не блокер #516  
- [x] Allowlist 707 + `Rodent` в `default_config.yaml`, `catalog_allowlist_follow_classifier_engine: true`

## Wave D — Валидация

- [x] A/B favorites — `docs/reports/favorites_ab_benchmark.md`
- [x] `processor/tests/test_classifier_paths.py`, `test_species_allowlist_resolver.py`, overlay tests
- [x] Deploy + health OK; smoke classifier на VPS (Trapper + Birder OpenVINO)
- [x] Overlay: `AnnotationViewer` — интерполяция bbox, скрытие вне трека

## Критерии приёмки (#516)

| # | Критерий | Статус |
|---|----------|--------|
| 1 | Eurasian Jay / EU виды из класса модели (707), не mapping-костыль | ✅ Birder `class_labels.txt`, id в metadata |
| 2 | Latency на VPS в бюджете | ✅ convnext256px OpenVINO, fallback от rope_vit |
| 3 | Каталог scope 707 без раздувания | ✅ allowlist 707 + Rodent; полный reconcile — Wave C / #506 |
| 4 | Squirrel/Rodent через детектор | ✅ `detector_scope` Trapper, не bird classifier |

## Коммиты

- `57b91be2e` — Birder EU default engine
- `478af8720` — overlay + ByteTrack clamp + VPS regen scripts
