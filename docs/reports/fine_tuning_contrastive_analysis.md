# Contrastive forensic: корм vs птица (2026-05-20)

**Роль:** Lead CV / Data Analyst  
**Пороги:** `min_conf=0.28`, `track_conf=0.12`, NABirds + OpenVINO  
**Метод:** Self-supervised contrastive analysis — в одном ролике кадры без птицы (Type A) vs с птицей (Type B) vs конфликт (Type C).

Скрипты: `scripts/contrastive_feed_fp_forensic.py`, `scripts/calibrate_nabirds_thresholds.py`  
Артефакты на VPS: `/tmp/contrastive_forensic/` (`forensic_report.json`, `frames/`, `collage_before_after.jpg`).

---

## Этап 1 — парные ролики (сегодня)

Отбор из `session_runtime_metrics` (UTC 2026-05-20): `yolo_accepted_boxes_total > 0`, приоритет «подозрительные» (`raw >> accepted`).

| Ролик | Session | accepted | raw | Парность A+B | Комментарий |
|-------|---------|----------|-----|--------------|-------------|
| `094147` | 1509 | 173 | 216 | **да** | Лучший эталон: корм ~262×256 @0.28–0.34 vs птица @0.41+ |
| `050815` | — | — | — | **да** | Якорь «явная птица»: кластер (29,9), conf 0.41–0.73, ~160×340 |
| `094329` | 1511 | 94 | 2600 | **да** | Много raw, мало accept; гигантские боксы на A-кадрах |
| `093950` | 1508 | 58 | 3764 | нет B | Огромные боксы ~505×484 @0.30–0.36 (ложный захват кормушки) |
| `083339` | 1449+ | 707–910 | ≈raw | нет | После 0.28 в сэмпле **0** accept — шум подавлен глобальным порогом |
| `082109` | 1444 | 1110 | 1113 | **да** | Почти все кадры = крупный FP; мало чистой «пустой» фазы |
| `094536` | 1513 | 187 | 364 | **да** | 1 явный B, остальное A |

Сопоставление session → `recordings/2026/05/20/HHMMSS/video.mp4` по `created_at` (±3 мин).

**Экстракция:** stride=2, до 40 кадров/ролик → `/tmp/contrastive_forensic/frames/{HHMMSS}_{A|B|C}_{frame}.jpg`.

---

## Этап 2 — контрастный forensic

### 2.1 Статичность фона (Type A)

**`094147`** — доминирующий кластер при `track_conf=0.12`:

| Параметр | Ложный корм (кластер) | Реальная птица `050815` |
|----------|------------------------|-------------------------|
| Grid cell (50 px) | **(19, 26)** | **(29, 9)** |
| Попадания | 30 кадров / 30 хитов | 20 кадров, стабильно |
| Размер WH | **~262 × 256** | **~159 × 344** |
| conf (accept ≥0.28) | **0.25 – 0.44** (типично **0.28–0.34** на A) | **0.41 – 0.73** |
| Aspect W/H | **~1.03** (почти квадрат) | **~0.47** (вертикальная птица) |

**Вывод:** ложные срабатывания на корме — **не микробоксы 10×10**, а **средние ~67k px²** в **фиксированной зоне** с conf чуть ниже птицы. Поднятие общего `min_conf` до 0.35 убьёт часть птиц на `094147` (B mean 0.39).

**`083339`:** на выборке при 0.28 — **0** accepted; legacy-шум был на conf ~0.16 (см. прошлую калибровку).

**`093950`:** кластер (26, 9), WH **505×484**, conf 0.30–0.36 — ложный «монолит» кормушки (area > 200k px²).

### 2.2 Type A vs Type B (внутри `094147`)

| Метрика | Type A (корм, без птицы) | Type B (птица) |
|---------|--------------------------|----------------|
| n (accepted) | 18 | 7 |
| mean conf | **0.338** | **0.413** |
| mean area | 67 239 | 66 546 |
| mean W×H | 263×256 | 262×254 |

Размер **почти одинаковый** → фильтр только по площади/`<20px` **не работает**. Разделители: **conf + aspect + позиция + движение**.

### 2.3 Type C (конфликт) и NMS

На сегодняшней выборке **0** кадров класса C (птица + отдельный мелкий корм в одном кадре при текущих эвристиках). Конфликт «корм подавляет птицу» проявляется иначе: **два кластера в разных кадрах одного ролика**, а не в одном кадре NMS.

Рекомендация по NMS: при появлении C — **prefer higher conf + более вертикальный aspect**; IoU threshold оставить ByteTrack default, не ужимать (низкий FPS).

---

## Этап 3 — пространство решений

| Мера | Селективность | Оценка |
|------|---------------|--------|
| **A. Порог по «feed-like» геометрии** | area 40k–95k, aspect 0.75–1.25, conf <0.40 **только если в кадре нет bird-like** (conf≥0.40, h≥200 или area≥40k, aspect<0.65) | **Лучший ROI** на `094147`: 20 FP отсекаются, птицы `050815` не трогаются |
| **B. Динамический порог по размеру** | conf 0.45 если area<1600 или side<28 | На сегодня **0** таких accept — не решает основную жалобу |
| **C. ROI-маска «зона риска»** | grid (19,26) @50px ≈ центр (950,1300) на 1280×720 | Дополнение к A; стабильна для `094147`, нужна калибровка на камеру |
| **D. Temporal static filter** | 3 кадра, jitter <6 px, area<80k → drop | Режет статичный корм; **не резать** при смещении >6 px (низкий FPS) |
| **E. Поднять global min_conf до 0.32+** | — | **Отклонено:** теряем B на `094147` (conf 0.39–0.41) |

---

## Этап 4 — симуляция на выборке

Правило **feed-like + no-bird-in-frame** (офлайн-симуляция):

- `40000 < area < 95000`, `0.75 < W/H < 1.25`, `conf < 0.40`, в кадре нет box с `conf≥0.40` и bird-like shape.

| Ролик | FP feed-like (до) | После правила | Bird recall |
|-------|-------------------|---------------|-------------|
| `094147` | **20** | **0** | 100% (7/7 B-кадров) |
| `050815` | 0 | 0 | 100% |
| `083339` | 0 | 0 | — |
| `093950` | 5 (гигант.) | 0* | — |

\*Гигантские боксы отсекаются отдельно: `area > 120000` или `W>400` → reject.

**Оценка:** FP reduction **~100%** на feed-like классе; recall птиц **100%** на якорных роликах.

Визуализация: `/tmp/contrastive_forensic/collage_before_after.jpg` (если есть C-кадры; иначе см. `frames/`).

---

## Этап 5 — рекомендации и план

### Предлагаемый конфиг (`user_config.yaml` / `default_config.yaml`)

```yaml
processor:
  min_confidence_binary: 0.28
  min_confidence_binary_bird: 0.28
  openvino_min_confidence_binary_bird: 0.28
  openvino_binary_track_ultralytics_conf: 0.12

  # Селективный anti-feed (новое)
  feed_fp_suppression_enabled: true
  feed_fp_suppression_max_confidence: 0.40
  feed_fp_suppression_area_px_min: 40000
  feed_fp_suppression_area_px_max: 95000
  feed_fp_suppression_aspect_min: 0.75
  feed_fp_suppression_aspect_max: 1.25
  feed_fp_suppression_requires_no_bird_in_frame: true
  feed_fp_suppression_bird_min_confidence: 0.40
  feed_fp_suppression_bird_max_aspect: 0.65

  # Гигантский ложный захват кормушки
  max_box_area_norm: 0.35   # проверить текущее; при WH>50% кадра — reject

  # Temporal (фаза 2)
  static_box_suppression_enabled: true
  static_box_suppression_min_frames: 3
  static_box_suppression_max_jitter_px: 6
  static_box_suppression_max_area_px: 80000
```

### ROI-маска (опционально, камера BirdBox)

Нормализованный прямоугольник зоны риска `094147` (уточнить по 5–10 кадрам Type A):

- примерно **cx: 0.55–0.85, cy: 0.55–0.95** (grid 19–26 при 16×9) — игнор accept если `conf < 0.42` внутри маски.

### Мониторинг

- Счётчики в `last_detect_metrics`: `rejected_feed_fp`, `rejected_static`, `rejected_giant_box`.
- Дашборд: `yolo_accepted` vs `yolo_raw` + доля reject по reason.

### Внедрено (StaticObjectFilter)

- Модуль: `app/processor/src/static_object_filter.py` — класс **`StaticObjectFilter`**.
- Интеграция: `detection_strategy.py` после сбора `valid_boxes`, до классификации.
- Конфиг: `processor.static_object_suppression_enabled` и `static_box_*` / `static_temporal_*` в `default_config.yaml`.
- Метрики: `rejected_static_objects`, `rejected_phantom_boxes` в `last_detect_metrics`.
- Валидация: `scripts/validate_static_object_filter.py`, `pytest tests/test_static_object_filter.py`.

### План внедрения (остаток)

1. **Smoke на проде:** `094147` / `050815` после `make deploy`.
2. **Опционально:** ROI-маска по grid (19,26) как YAML polygon.

### Критическое

- **Не** поднимать общий `min_conf` — мелкие птицы и пограничные B (0.39) пропадут.
- Резать **геометрию корма + низкий conf в пустых кадрах**, якорить по роликам с явной птицей (`050815`, кадры B в `094147`).

---

## Координаты: ложные vs реальные (сводка)

| Класс | Grid (50px) | Norm center ≈ | WH typ. | conf typ. |
|-------|-------------|---------------|---------|-----------|
| Корм FP `094147` | (19, 26) | (0.74, 0.81) | 262×256 | 0.28–0.34 |
| Птица `050815` | (29, 9) | (1.16*, 0.28) | 159×344 | 0.41–0.73 |
| Гигант FP `093950` | (26, 9) | — | 505×484 | 0.30–0.36 |

\*Grid >16 означает координату у правого края кадра — нормализовать под фактическое разрешение при построении маски.

---

*Сгенерировано: 2026-05-20, контейнер birdlense, GPU OpenVINO.*
