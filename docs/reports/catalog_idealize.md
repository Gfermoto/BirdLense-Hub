# Идеализация каталога Species

## Целевое состояние

| Слой | Что остаётся |
|------|----------------|
| **Классификатор** | 707 Birder + **Rodent** = **708** строк `Species` (одна на класс) |
| **Иерархия UI** | Узлы-группы (`Ducks, Geese, and Swans`, …) с `parent_id` у детей — не дубли видов |
| **Служебные** | `Unknown`, `Bird`, `Birds` — не удаляются |

Legacy (YOLO EU ~821, дубли `Scientific (Common)`, пустые off-allowlist) — **удалены или слиты**.

## Скрипт

```bash
# Аудит
PYTHONPATH=/app:/app/web:/app/processor/src python3 /app/scripts/catalog_idealize.py --audit

# Применить (hub лучше остановить)
docker compose stop birdlense
docker compose run --rm --no-deps \
  -e PYTHONPATH=/app:/app/web:/app/processor/src \
  -v ./data:/app/data -v ./app_config:/app/app_config \
  -v ./web/services/species_catalog/idealize.py:/app/web/services/species_catalog/idealize.py:ro \
  -v ../scripts/catalog_idealize.py:/app/scripts/catalog_idealize.py:ro \
  birdlense python3 /app/scripts/catalog_idealize.py --apply
docker compose start birdlense
```

Флаги: `--keep-active-off-allowlist` — не сливать активные legacy-виды в Unknown.

## Шаги внутри `--apply`

1. Legacy import placeholders (disk-import)
2. `deep_reconcile` — дубликаты по имени, канонизация, plumage
3. `merge_canonical_name_collisions` — коллизии rename
4. `merge_duplicate_allowlist_species` — **одна** строка на класс allowlist
5. Удаление пустых off-allowlist; активные → **Unknown**
6. Удаление пустых узлов иерархии
7. `ensure_allowlist_species_materialized`

## Prod VPS (2026-05-28)

| | До | После |
|---|-----|--------|
| `species_total` | 1788 | **735** |
| `on_allowlist` | 808 | **708** |
| off-allowlist empty | 977 | 0 (удалены) |
| allowlist dedupe | — | 97 merge |

Оставшиеся **27** off-allowlist: **21** групп иерархии + `Birds` + `Bird` (служебные), не legacy-мусор.

Повторить 2–3 раза `--apply`, пока `purge del` ≈ 0 и `on_allowlist` = 708.
