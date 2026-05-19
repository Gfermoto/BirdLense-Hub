# Validation Daylight — отчёт (мало птиц)

- **Окно (UTC):** 2026-05-19T07:29:33 → ~08:34 (7 из 12 проб, прогон ещё идёт / можно остановить)
- **Сервер:** `185.218.111.196`
- **Метрики:** `app/data/nightly_marathon/validation_daylight/validation_daylight_20260519T072933Z.json`

## Что починили (подтверждено)

| Баг | Было | Стало | Доказательство |
|-----|------|-------|----------------|
| **Monitor** | `docker logs … "2>&1"` / `capture_output`+stderr | `stdout=PIPE`, `stderr=STDOUT` | пробы 2–7: **4–13 сессий** за 10 мин (не ноль) |
| **Blind** | suspected при ранних счётчиках | `_blind_suspected_from_final_stats()` | **0** ложных FP при boxes/tracks (49 сессий) |
| **Canary** | shadow NULL (1 logit vs 2 labels) | sigmoid + DATA_DIR | backfill 1803–1805; video **1816** shadow=`flying` (до окна) |

## KPI за окно валидации (~1 ч активных проб)

| KPI | Цель | Факт | Статус |
|-----|------|------|--------|
| Monitor читает логи | sessions > 0 | max **13**/пробу, sum **49** за окно | **OK** |
| Blind false positive | 0 | **0** / 15 сессий с боксами | **OK** |
| Canary на **новых** видео | ≥1 с shadow | **0** новых видео в БД | **INCONCLUSIVE** |
| Harvest | ≥1 кроп | **0** (нет новых клипов) | **N/A** |

## YOLO (с 07:29 UTC, после деплоя)

| Метрика | Значение |
|---------|----------|
| Сессий в логах | **49** |
| Geometry (боксы или треки) | **30.6%** (15/49) |
| Blind FP (suspected + boxes) | **0** |

Проба 1: `sessions=0` — сразу после рестарта, в логе ещё не было summary (норма).

## Canary

- Новых записей с **07:29 UTC**: **0**
- `behavior canary persist` в логах за окно: **0**
- Последние видео в БД (вне окна): **1816** — meta=`feeding`, shadow=`flying` (06:57 UTC, до старта теста)

**Вывод:** днём птиц почти нет → live-проверка записи shadow **не выполнима**. Технически цепочка работает (backfill + 1816).

## Harvest

0 кропов — нет новых `video` с треками.

## Вердикт

### **Условно готов к 8h ночному марафону**

| Компонент | Готов? |
|-----------|--------|
| Monitor | **Да** |
| Blind-gate | **Да** |
| Canary persist (код) | **Да** (не проверен на новых клипах днём) |
| Сбор flying днём | **Нет** (ожидаемо) |

**Рекомендация:** запускать **8h марафон ночью**, не днём. Критерий успеха ночи: ≥1 новое видео с `behavior_shadow_label`, harvest > 0, monitor JSON с sessions > 0.

```bash
# на VPS после переключения на ночь
bash /root/BirdLense/scripts/nightly_marathon_start.sh
```

Опционально: остановить текущий daylight-монитор (`kill $(cat app/data/nightly_marathon/validation_daylight/validation_daylight.pid)`).
