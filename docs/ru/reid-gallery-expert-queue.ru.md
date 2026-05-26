# ReID Gallery и Expert Queue (SOTA-13)

## Feature flags (по умолчанию выключено)

В `default_config.yaml` / `user_config.yaml`:

```yaml
processor:
  reid_gallery_enabled: false
  reid_track_clustering_enabled: false
  reid_expert_queue_enabled: false
  reid_gallery_merge_cosine_threshold: 0.92
  reid_gallery_duplicate_threshold_low: 0.82
  reid_gallery_min_track_duration_sec: 0.6
```

Включайте **только после** зелёных бенчмарков SOTA-10..12 на VPS (`scripts/vps-validate-sota.sh`).

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/ui/reid/gallery/status` | Статус флагов |
| GET | `/api/ui/reid/gallery` | Кластеры треков по `reid_embedding` |
| GET | `/api/ui/expert/queue` | Очередь задач (`?sync=1` — подтянуть дубли) |
| POST | `/api/ui/expert/resolve` | `dismiss`, `confirm_species`, `merge_tracks`, `merge_profiles` |
| POST | `/api/ui/expert/export-verified` | Экспорт в `datasets/expert_verified/` |

Алиасы без `/ui`: `/api/expert/queue`, `/api/expert/resolve`.

## UI

Страница **`/reid-gallery`**: сетка кластеров + expert queue (merge / dismiss).

## Active learning export

После resolve задач:

```bash
curl -X POST -b "session=…" http://HOST:8085/api/ui/expert/export-verified
```

Файл: `datasets/expert_verified/expert_verified_manifest.jsonl`.

## Защита от коротких треков

Кластеризация и очередь не берут треки короче `reid_gallery_min_track_duration_sec` (по умолчанию = live `min_track_duration` 0.6 с).

## Связанные документы

- [tracking-parity.ru.md](tracking-parity.ru.md)
- [tracker-benchmark.ru.md](tracker-benchmark.ru.md)
- [benchmark-golden-clips.ru.md](benchmark-golden-clips.ru.md)
