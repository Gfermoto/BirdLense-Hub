# Issue #516 — чеклист приёмки

**Статус:** в работе (не закрывать до зелёного прогона на проде).

## Wave A — PoC + артефакты

- [x] `scripts/download_birder_classifier.py`
- [x] Smoke / export OpenVINO
- [x] Бенчмарк latency (convnext256px выбран для prod)
- [x] `docs/reports/birder_eu_classifier_poc.md`

## Wave B — Интеграция под ключ

- [x] `processor.classifier_engine: birder_eu` (default)
- [x] Runtime `birder_eu_classifier.py` (torch + OpenVINO)
- [x] **Именование как у детектора:** `convnext_v2_tiny_eu-common256px.pt` + `convnext_v2_tiny_eu-common256px_openvino_model/` (без подпапки variant, без legacy/)
- [x] `scripts/migrate_classifier_weights_layout.sh` + миграция `user_config`
- [ ] Прод: migrate + `patch_user_config_birder_on_server.sh` + health/smoke после деплоя
- [ ] A/B на избранном через **треки** (не разреженные кропы) — отдельный скрипт

## Wave C — Каталог

- [ ] Отдельная задача: reconcile Collins 707 → каталог Hub (#506 scope)

## Wave D — Валидация

- [x] A/B favorites (грубый sampling) — `favorites_ab_benchmark.md`
- [ ] `make ci-local` / processor-light с новыми путями
- [ ] Deploy + verify-stack на VPS

## Критерии приёмки (#516)

1. [x] Eurasian Jay — класс в модели (id 232), не mapping-костыль
2. [x] Prod default: convnext256px OpenVINO (~120 ms/crop VPS)
3. [ ] Каталог scope 707 — **отложено** (Wave C)
4. [x] Squirrel/Rodent — детектор, не bird classifier
