# Issue #506 — каталог eBird/Clements, Birder 707

**Issue:** [SOTA-15] Каталог: eBird/Clements — стабильность имён и plumage variants  
**Статус:** закрыт после materialize + deep-reconcile на prod

## Критерии

- [x] Allowlist = **707** Birder `class_labels.txt` + **Rodent** (`catalog_allowlist_follow_classifier_engine`)
- [x] Нет union с legacy YOLO EU (~821) при активном `birder_eu`
- [x] API: `name` (канон), `db_name`, `scientific_name` (taxon / mapping / allowlist binomial)
- [x] `deep_reconcile` + `restore_plumage_variant_display_names` (скрипт `scripts/catalog_deep_polish.py`)
- [x] Materialize allowlist → строки `Species` (`--materialize`)
- [x] Тесты: birder allowlist, scientific_name, plumage canon (существующие)

## Prod (VPS)

```bash
# dry-run
docker compose -f /root/BirdLense/app/docker-compose.yml exec -T birdlense \
  python3 /app/scripts/catalog_deep_polish.py --dry-run --materialize

# apply
docker compose -f /root/BirdLense/app/docker-compose.yml exec -T birdlense \
  python3 /app/scripts/catalog_deep_polish.py --materialize
```

Ожидание в JSON: `allowlist_total` ≈ **708**, `listed_allowlist` ≈ **708** (meta API `scope=allowlist`).

## Код

| Модуль | Изменение |
|--------|-----------|
| `species_catalog/api.py` | `scientific_name` из `SpeciesTaxon`, mapping, allowlist |
| `species_catalog/allowlist.py` | `scientific_name_from_canonical_mapping` |
| `catalog_deep_polish.py` | флаг `--materialize` |
