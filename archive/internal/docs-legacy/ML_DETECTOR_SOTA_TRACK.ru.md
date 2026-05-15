# Практический SOTA-трек детектора (BirdLense)

Цель: получить **реальный прирост качества на сценах кормушки (день + IR)**, а не только на paper-метриках.

## Что уже зафиксировано

- Базовый перекос прод-fusion в сторону `frigate_standalone` зафиксирован в:
  - `docs/archive/FUSION_BASELINE_2026-04-30.md`
- A/B по профилям fusion зафиксирован в:
  - `docs/archive/FUSION_AB_EVAL_2026-04-30.md`

## SOTA-подход для этого проекта

1. **Сначала YOLO-first стабильность в проде**  
   Frigate остаётся fallback, а не primary при наличии валидного визуального трека.

2. **Только затем детекторный SOTA-цикл**  
   Тренируем 2-классный детектор `Bird/Rodent` на собственном домене.

3. **Сравнение кандидатов на одинаковом протоколе**  
   Минимум две базы:
   - `yolo11n.pt`
   - `yolov8n.pt`

4. **Критерий принятия**  
   Кандидат должен улучшать recall и не увеличивать ночные ложные срабатывания.

## Матрица экспериментов

- Файл матрицы: `scripts/sota_detector_matrix.yaml`
- Запуск матрицы: `scripts/run-sota-detector-matrix.sh`

Пример:

```bash
cd /home/gfer/BirdLense
chmod +x scripts/run-sota-detector-matrix.sh
scripts/run-sota-detector-matrix.sh
```

## Обязательные данные перед обучением

- Срезы дня и IR в train/val/test
- Hard negatives из ручных удалений фона
- Коррекции species из UI (позитивы) в отдельном манифесте
- Фиксированный `seed` и одинаковые split для честного сравнения моделей

## Acceptance gates (до прод-внедрения)

- `primary_provider=yolo` не падает относительно текущего tuned профиля
- `accepted_species` не падает
- ночные FP не растут
- на ручном срезе 29.04 качество не хуже текущего tuned baseline

## Связанные источники

- [AleksandrRogachev94/BirdLense](https://github.com/AleksandrRogachev94/BirdLense)
- [Birds-YOLO (MDPI Biology)](https://www.mdpi.com/2079-7737/14/11/1515)
- [MSFN-YOLOv11 (MDPI Animals)](https://www.mdpi.com/2076-2615/15/23/3472)
