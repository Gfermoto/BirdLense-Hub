# Обучение детектора (YOLO) в Google Colab

[English](./ML_DETECTOR_COLAB.md)

Пошаговый Colab для **классификатора**: [TRAINING.ru.md](./TRAINING.ru.md).  
Здесь — **детекция**: бинарный или **трёхклассовый** детектор из `dataset.yaml` по [DATASETS.ru.md](./DATASETS.ru.md).

---

## Что нужно

- Аккаунт Google, место на Drive под архивы и ран (рекомендуемо 3-4 GB)  
- Два архива датасета с Hugging Face:  
  [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)  
  (`detector_merged_balanced_20260429.zip` и `detector_merged_full_20260429.zip`)  
- Среда Colab с **GPU T4**
- Пакет весов (YOLO + OpenVINO):  
  [weights-20260429T125011Z-3-001.zip](https://huggingface.co/gfermoto/BirdLense_Detector/blob/main/weights-20260429T125011Z-3-001.zip)

---

## Краткие шаги

1. Загрузить оба архива в Google Drive (balanced + full).  
2. Stage A: распаковать `detector_merged_balanced_20260429.zip`, поправить `dataset.yaml` (`path` на `/content/...`), запустить train.  
3. Stage B: взять `best.pt` Stage A, распаковать `detector_merged_full_20260429.zip`, поправить `dataset.yaml`, запустить fine-tune.  
4. Забрать `BEST_B` с Drive; при необходимости `export(format='openvino')`.  
5. Положить веса на хаб и выставить пути в Hub — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

Если используете уже опубликованный пакет
`weights-20260429T125011Z-3-001.zip`, шаг экспорта можно пропустить:
там уже есть готовые артефакты YOLO/OpenVINO.

Полный Colab-пайплайн (готовые ячейки) — в [ML_DETECTOR_COLAB.md](./ML_DETECTOR_COLAB.md).

---

## Контракт имён

Имена классов как в Hub: **Bird**, **Rodent**, **Background**; в `detector_scope` не включать Background — [CV_ML_PREP.ru.md](./CV_ML_PREP.ru.md).
