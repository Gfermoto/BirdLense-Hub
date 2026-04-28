# Обучение детектора (YOLO) в Google Colab

[English](./ML_DETECTOR_COLAB.md)

Пошаговый Colab для **классификатора**: [TRAINING.ru.md](./TRAINING.ru.md).  
Здесь — **детекция**: бинарный или **трёхклассовый** детектор из `dataset.yaml` по [DATASETS.ru.md](./DATASETS.ru.md).

---

## Что нужно

- Аккаунт Google, место на Drive под zip и ран  
- Архив датасета с **`dataset.yaml`** внутри (например папка `binary/merged/` после `make dataset-merge-three-class`)  
- Среда Colab с **GPU T4**

---

## Краткие шаги

1. Локально упаковать папку датасета в zip и загрузить на Drive.  
2. В Colab: `pip install ultralytics`, подключить Drive, распаковать zip.  
3. Указать путь к `dataset.yaml`, запустить `YOLO(...).train(...)`.  
4. Забрать `weights/best.pt` с Drive; при необходимости `export(format='openvino')`.  
5. Положить веса на хаб, выставить `processor.inference_backend` и пути — см. [CONFIGURATION.ru.md](./CONFIGURATION.ru.md).

Полные ячейки — в английской версии [ML_DETECTOR_COLAB.md](./ML_DETECTOR_COLAB.md).

---

## Контракт имён

Имена классов как в Hub: **Bird**, **Rodent**, **Background**; в `detector_scope` не включать Background — [CV_ML_PREP.ru.md](./CV_ML_PREP.ru.md).
