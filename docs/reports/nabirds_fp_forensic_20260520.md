# NABirds OpenVINO — Forensic: массовые ложные срабатывания (2026-05-20)

## Симптом

После включения NABirds + OpenVINO GPU:

- `yolo_raw_boxes_total` 800–1100 за сессию (~5 мин)
- `yolo_accepted_boxes_total` ≈ raw (почти всё проходит фильтр)
- `post_fusion_persisted` = 1, но визиты — шум / Bird / Unknown
- Рамки на **статике кормушки**, тенях, текстуре корма (conf 0.04–0.17)

Примеры сессий (UTC): id 1443–1448, `2026-05-20T08:08–08:30`.

## Этап 1 — Forensic

### Кадр `recordings/2026/05/20/082357/video.mp4` (2688×1520)

| Backend | `conf` в track | Боксов bird @0.025 | @0.08 | @0.25 |
|---------|----------------|-------------------|-------|-------|
| PyTorch | — | 6–7 | 1 | 0 |
| OpenVINO | — | 6 | 1–2 | 0 |

**Вывод:** мусор есть **и в PT, и в OV** при низком `track(conf)` — не баг экспорта IR. При `conf≥0.25` мусор исчезает на статичном кадре.

### Class ID

Все боксы — класс **0 (bird)**. Путаницы классов нет.

### Почему в проде сотни боксов при «1 боксе на кадр» в тесте?

1. **`openvino_binary_track_ultralytics_conf: 0.025`** — Ultralytics `track(conf=0.025)` оставляет 6+ сырых детекций на кадр.
2. **`openvino_binary_bird_score_scale: 8.5`** — при сравнении с порогом Bird: `cmp_conf = conf × 8.5`.  
   Пример: conf **0.06 × 8.5 = 0.51 > 0.08** → бокс **принят** (legacy под BRG, где OV conf был ниже).
3. **`binary_track_max_det: 384`** — потолок детекций на кадр слишком высокий.
4. **`auto_small_object_relax`** + **`ultra_weak_box_salvage`** — дополнительно протаскивают слабые боксы.

## Корневая техническая причина

**Не галлюцинация OpenVINO IR**, а **неверная калибровка пост-обработки под старый BRG**:

- Parity gate (7/7) проверял **геометрию** при `conf=0.08`, не политику прод-порогов.
- После миграции остались **завышение conf (×8.5)** и **слишком низкий track conf (0.025)** → система стала «шумным датчиком».

## Hotfix (2026-05-20)

| Параметр | Было | Стало |
|----------|------|-------|
| `min_confidence_binary` / `_bird` | 0.08 | **0.28** |
| `openvino_min_confidence_binary_bird` | null | **0.28** |
| `openvino_binary_bird_score_scale` | 8.5 | **1.0** |
| `openvino_binary_track_ultralytics_conf` | 0.025 | **0.12** |
| `binary_track_max_det` | 384 | **60** |
| `auto_small_object_relax_max_candidates` | 4 | **1** |
| night `min_confidence_binary_bird` | 0.08 | **0.22** |

Принцип: **лучше пропустить птицу, чем забить БД мусором**.

## Валидация hotfix

На проблемном кадре f10: при `conf_in=0.25` → **0 боксов** (PT и OV).  
Мониторинг: `yolo_raw_boxes_total` << 200/сессию, `yolo_accepted` ≪ raw при пустой кормушке.

## Дальше (модель)

1. Fine-tune NABirds на **негативных** кадрах кормушки без птиц.
2. ROI-маска статической зоны кормушки (координаты в конфиге).
3. Temporal: требовать track ≥ N кадров перед классификацией (отдельный PR).

См. `docs/reports/migration_final_report.md`.
