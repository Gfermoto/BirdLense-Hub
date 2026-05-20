# Truth Serum — FP Crisis (2026-05-20)

## Признание

Отчёты о «17× снижении FP» были **верны только для части метрик и окон времени**, но **вводили в заблуждение** как итог продукта:

| Что показывали отчёты | Что видел пользователь |
|------------------------|-------------------------|
| Сессии **после 08:35** с `accepted` 50 vs 832 | Сессии **10:00–11:25** с `accepted` ≈ **raw** (268–293/мин) |
| Офлайн-клипы 094147: 25→7 | Live UI/логи с сотнями боксов |
| «Фильтры внедрены» | **`user_config.yaml` на VPS не обновлялся** deploy'ом |

**Deploy не перезаписывает `user_config.yaml`.** На проде оставались:

- `min_confidence_to_store: 0.08`
- `yolo_weak_track_salvage_enabled: true` (0.015)
- `auto_small_object_relax_enabled: true`
- `adaptive_profiles.night`: **min_conf 0.22** (усиливало ночной шум)
- Нет `detection_ignore_masks` для пятна корма

## Forensic prod (факты)

### Худшие сессии (до жёсткого деплоя ~11:58 UTC)

| session_id | UTC | raw | accepted |
|------------|-----|-----|----------|
| 1444 | 08:23 | 1113 | **1110** |
| 1570 | 11:25 | 282 | **282** |

### После деплоя quality pipeline (~11:58+ UTC)

| Паттерн | raw | accepted |
|---------|-----|----------|
| Статичная кормушка | 1500–1800 | **0** |
| Ветер/дрожь ROI | 419 | **43** (session 1606) |

Логи: `DetectionQuality reject … global_frame_static(mean_absdiff=0.52)` — **фильтр работает на статике**.

### Почему пропускали боксы (уязвимости v1)

1. **Motion gate только при `conf < 0.42–0.50`** — мусор 0.29–0.40 при локальном шуме ветра проходил.
2. **`relaxed_small_object` обходил quality pipeline.**
3. **Night profile снижал порог до 0.22**, не повышал.
4. **Salvage/relax** восстанавливали слабые боксы.
5. **`yolo_raw` в логах** выглядит как «шум», хотя `accepted` уже 0 — путаница метрик.

## Nuclear fix (v2)

### Код

- Motion для **всех** `conf < 0.55` (не 0.42).
- **3 кадра** истории ROI motion — нет движения → ban.
- Блок **`relaxed_small_object`** в quality pipeline.
- Пороги motion: min pixel change **10**, global static **< 2.0**.

### Config (default + `patch_prod_nuclear_user_config.py`)

- `min_confidence_binary_bird: **0.38**`
- `openvino_binary_track_ultralytics_conf: **0.28**`
- `min_track_duration: **1.0** s`
- Salvage/relax: **off**
- `min_confidence_to_store: **0.35**`
- Night: **0.45**, не 0.22
- ~~Default ignore mask~~ removed — use MOG2 + scene-adaptive conf (universal)

### Прод-патч

```bash
docker exec birdlense python3 /app/scripts/patch_prod_nuclear_user_config.py
docker compose -f /app/docker-compose.yml up -d --force-recreate birdlense
```

## Критерий успеха (1 час)

- Пустая кормушка: `yolo_accepted_boxes_total` ≈ **0**, `yolo_raw` может быть высоким.
- Нет визитов в UI от FP (store ≥ 0.35).
- При появлении птицы: единичные accepted, не сотни.

## Скриншоты / артефакты

- Видео с прода: `tmp/forensic_live/082109_worst.mp4`, `094147_feed.mp4`
- До: session 1444 accepted=1110
- После nuclear: мониторить session_runtime_metrics `accepted` < 5 на пустом кадре

---

*Wave 3 заморожен до выполнения критерия тишины.*
