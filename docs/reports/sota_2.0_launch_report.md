# SOTA 2.0 Launch Report (2026-05-20)

**Status:** Phase 0–2 implemented · Golden Gate synthetic **PASS** · Prod deploy required for live validation

---

## 1. До vs После (архитектура)

| Аспект | Каскад (до) | ScoringEngine (после) |
|--------|-------------|------------------------|
| Решение | 8+ независимых AND-фильтров | Единый `final_score` + зоны accept/review/reject |
| Пороги | Хардкод YAML (0.55, 0.38, MOG2 0.07…) | Auto-Calibration первые 60 кадров |
| Frigate | Standalone визиты без YOLO | Prior boost +0.2, standalone **off** |
| Диагностика | Случайные log reject | JSONL Black Box per-frame |
| FP/FN цикл | Подкрутка порогов | Веса `w1..w4` (обучаемые позже) |

---

## 2. Golden Dataset v2

| Источник | Путь | Записей |
|----------|------|---------|
| Synthetic (CI) | `app/data/datasets/golden_v2/manifest.synthetic.json` | 24 клипа |
| Prod mining | `scripts/generate_golden_dataset_v2.py` → `manifest.json` | до 50 клипов |

Категории: `bird_confirmed` (is_bird=true), `noise_fp` (false), `hard_scene` (difficulty=hard).

**Генерация на VPS:**

```bash
python3 scripts/generate_golden_dataset_v2.py --db app/data/db/birdlense.db --days 7
```

---

## 3. Golden Gate (CI)

```bash
make validate-pipeline-golden
```

| Метрика | Synthetic manifest | Порог |
|---------|------------------|-------|
| F1 | ≥ 0.85 (conf-only test mode) | **> 0.7** |

Тесты: `test_scoring_engine.py`, `test_pipeline_golden_gate.py`.

---

## 4. Black Box

- Модуль: `app/processor/src/frame_decision_trace.py`
- Путь: `data/decision_traces/YYYY/MM/DD/{session}_{camera}.jsonl`
- Поля: `frame_id`, `raw_conf`, `motion_score`, `bg_score`, `shape_score`, `final_score`, `final_decision`, `reject_reason`

---

## 5. Auto-Calibration

- Первые `scoring_calibration_frames` (60) кадров без bird-кандидатов → перцентиль шума → `low_threshold` / `high_threshold`
- Safety: `low ≥ 0.25`, `high = low + review_band_width`
- Лог: `ScoringEngine auto-calibration: low=… high=…`

---

## 6. Конфиг (default)

```yaml
processor:
  scoring_engine_enabled: true
  motion_verified_detection_enabled: false
  background_subtraction_enabled: false
  static_object_suppression_enabled: false
detection:
  frigate_standalone_when_no_yolo: false
```

Патч прода: `scripts/patch_prod_sota20_user_config.py`

---

## 7. Инцидент 13:05 UTC — повтор

| | Каскад | ScoringEngine (ожидание) |
|---|--------|--------------------------|
| raw=478, accepted=0 | global_frame_static | conf≥floor → score accept |
| После recovery | 176/227 accepted | Единая кривая score |

---

## 8. Вердикт Open Source

| Критерий | Статус |
|----------|--------|
| Golden Gate CI | ✅ synthetic |
| Prod 7d metrics | ⏳ после deploy |
| Black Box | ✅ |
| Frigate standalone off | ✅ default |
| Active Learning loop | ⏳ Wave 3 #479 |

**Вердикт:** **Условно готова** — нужны 7 дней prod без ручных порогов и real-manifest F1 ≥ 0.7.

---

## 9. Wave 3 разблокировано

- [#483](https://github.com/Gfermoto/BirdLense-Hub/issues/483) Foundation — этот релиз
- [#479](https://github.com/Gfermoto/BirdLense-Hub/issues/479) AL — после prod golden
- [#480](https://github.com/Gfermoto/BirdLense-Hub/issues/480) ReID — стабильные bbox
- [#481](https://github.com/Gfermoto/BirdLense-Hub/issues/481) INT8
- [#482](https://github.com/Gfermoto/BirdLense-Hub/issues/482) Mask UI — optional

---

*Deploy: `make deploy` → `patch_prod_sota20_user_config.py` → `docker compose up -d --force-recreate birdlense`*
