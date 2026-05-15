# Датасеты и модели BirdLense

[English](./DATASETS.md)

---

Справочник: форматы, скрипты, источники, оборудование. **Обучение:** [TRAINING](./TRAINING.ru.md).

---

## Актуальные пути (репозиторий сейчас)

Длинные списки команд не дублировать — см. **`scripts/datasets/README.md`**.

| Что | Путь / команда |
|-----|----------------|
| Входы детектора (YOLO-каталоги), **`make dataset-merge-three-class`** | `datasets/new/detector/binary/birds/`, `binary/rodent/`, `binary/background/` |
| **Выход слияния по умолчанию** (Makefile) | `datasets/new/detector/yolo/` — `make dataset-merge-three-class` |
| Тот же merge вручную из `scripts/datasets/` | `python3 scripts/datasets/merge_datasets_three_class.py --birds-dir … --output-dir …` (любые каталоги) |
| Входы / merged «классический» каталог под `scripts/datasets/` | `scripts/datasets/binary/{birds,rodent,background}/`, при необходимости `binary/merged/` — если используете локальную копию без `datasets/new/` |
| Опциональная папка **под ZIP / Colab** | `scripts/datasets/brg/` — тот же формат, что и `merged/`; заполнить **копией из `binary/merged/`** после обогащения/dedupe **или** запуск `merge_datasets_three_class.py` с **`--output-dir brg`** (Makefile всегда пишет в `binary/merged/`) |
| Упаковка YOLO в архив | `python3 scripts/datasets/pack_brg_for_gdrive.py` → **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`** (источник по умолчанию: **`datasets/new/detector/yolo`**) |
| Раскладка на диске | `scripts/datasets/DETECTOR_DATA_LAYOUT.md`, `scripts/datasets/binary/README.md` |
| ZIP на Hugging Face | Другие имена файлов (`detector_merged_*` и т.д.) — [BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main); это **не** то же имя, что локальный `BirdLense_detector_brg_*.zip` |
| Классификатор (merged локально) | Часто `datasets/merged_cls/` в корне — в `.gitignore`; см. [TRAINING](./TRAINING.ru.md) |

---

## Каталог `datasets/new/` — источники данных

Корень **`datasets/new/`** — основной локальный ETL для CV: детектор, классификатор, утилиты манифестов. Ниже перечислены **источники по подпапкам** (лицензии и фильтры — на стороне первичных наборов).

### Именованные публичные датасеты (COCO, CUB, Open Images, …)

Сводка **какой канонический набор** даёт какой класс детектора или слой классификатора (конкретные флаги — в скриптах и в **`scripts/datasets/DETECTOR_DATASET_QUALITY.md`**).

**Детектор** (входы в `binary/*`, затем **`make dataset-merge-three-class`** → `yolo/`):

| Именованный набор | Роль в Hub (после merge) | Как подключается |
|-------------------|--------------------------|------------------|
| **MS COCO 2017** | **Bird** (боксы класса `bird`), **Background** (кадры без птицы + пустые `.txt`) | **`bootstrap_detector_yolo.py`** (FiftyOne zoo `coco-2017`) |
| **Google Open Images V6** | **Bird** (опционально, детекции класса **Bird**), **Rodent** (боксы выбранных видов / `--rodent-classes`) | **`bootstrap_detector_yolo.py`** (`--birds-oid-*`, `--rodent-*`, validation-only и т.д.) |
| **Caltech-UCSD Birds-200-2011** (**CUB-200-2011**) | **Bird** | **`convert_cub_to_yolo.py`** / **`make dataset-import-cub`** (`--root datasets/new/detector`, локальный распакованный tarball) |
| **Roboflow Universe — Bird-Feeder** (экспорт **YOLOv11**, напр. **dataset v3**) | **Bird** | **`import_roboflow_bird_feeder_birds.py`**; исходный ZIP часто в **`detector/raw/`** |
| **Open Images** (выгрузка **OIDv4 Toolkit**, папки train/validation по классу) | **Rodent** | **`convert_oidv4_rodent_to_yolo.py`** → `binary/rodent/` |
| **Кадры оператора / съёмка хаба** | **Background** | **`import_hub_background_folder.py`** |
| Доп. **hard-negative** майны (часто **OID**: человек / собака / кошка и т.п.) | чаще **Background** | Политика и флаги — **`DETECTOR_DATASET_QUALITY.md`** и **`bootstrap_detector_yolo.py`** |
| **NABirds** | отдельная линия под иерархию видов | **`convert_nabirds_to_yolo*.py`** — **не** обязательный вход для стандартного трёхклассового merge |

**Классификатор** (виды птиц, папки под `datasets/new/classifier/`):

| Именованный набор / корпус | Заметки |
|----------------------------|---------|
| **`gfermoto/birds-eu-merged`** (Hugging Face) | Базовый EU-слой — **`download_birds_eu_merged.py`** |
| **iNaturalist** (research-grade, привязка к региону) | **`download_inaturalist.py`**, добор — **`backfill_classifier_open.py`** |
| **birds-525** и зеркала на HF | **`download_hf_birds.py`** (`--format scientific_common`) |
| Экспорт разметки из **BirdLense Hub** | **`export_birdlense_to_yolo.py`** |
| **CUB-200-2011**, BirdCLEF / LifeCLEF, Macaulay Library, NABirds, GBIF и др. | Обычно вне автоматического merge или по отдельным скриптам — см. **`EU_CLASSIFIER.md`** |

### Детектор — `datasets/new/detector/`

| Путь | Роль | Откуда берутся данные |
|------|------|------------------------|
| **`binary/birds/`** | Вход merge, класс Bird | **COCO 2017** (класс `bird`) через **`bootstrap_detector_yolo.py`** (FiftyOne); **Roboflow Universe — Bird-Feeder [YOLOv11, dataset v3](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11)** через **`import_roboflow_bird_feeder_birds.py`** (`--root datasets/new/detector`, все виды → один класс); архив импорта может храниться в **`raw/`** (напр. `Bird-Feeder.v3i.yolov11.zip`); опционально **CUB-200-2011** (`make dataset-import-cub`), другие Roboflow ZIP при совместимой лицензии |
| **`binary/rodent/`** | Вход merge, класс Rodent | **Open Images V6** (боксы классов из **`--rodent-classes`**, только **boxable**; отдельного `Rat` в boxable нет) через **`bootstrap_detector_yolo.py`**; опционально **OIDv4 Toolkit** → **`convert_oidv4_rodent_to_yolo.py`**; опционально **COCO instances** (LILA и др.) → **`import_coco_rodents_to_binary.py`** |
| **`binary/background/`** | Вход merge, класс Background | Кадры **COCO** без птицы и **пустые** YOLO-лейблы (bootstrap); кадры с камеры / папки оператора → **`import_hub_background_folder.py`** |
| **`yolo/`** | Выход **`make dataset-merge-three-class`** | Слитый YOLO detect **Bird / Rodent / Background**: `train|val|test/{images,labels}` + **`dataset.yaml`** |
| **`raw/`** | Архивы «как скачано» | ZIP экспортов (Roboflow и т.п.) до импорта в `binary/` |
| **`manifests/`**, **`qa/`** | Учёт сборки / QA | JSON манифесты и артефакты проверок (генерация: **`datasets/new/tools/build_manifests.py`**) |

Доп. скрипты и команды: **`scripts/datasets/README.md`**, качество: **`scripts/datasets/DETECTOR_DATASET_QUALITY.md`**, раскладка **`binary/`**: **`datasets/new/detector/README_binary_layout.md`**.

### Образцовый детектор Bird / Rodent для YOLOv11 (политика качества)

Цель — **обучение YOLOv11 detection** (классы **Bird** и **Rodent** в merge, плюс Background при полном трёхклассовом датасете), с опорой на обычную практику мультидоменного обучения и снижение смещения домена.

**Обязательное правило.** В `binary/birds/` и `binary/rodent/` попадают **только** кадры с **проверяемой разметкой боксов** из исходного набора: каждому изображению соответствует non-empty YOLO `labels/*.txt`, боксы воспроизводимы из первичных аннотаций (COCO, Open Images, CUB `bounding_boxes.txt`, экспорт Roboflow YOLO, COCO instances для camera traps / LILA и т.п.).

**Недопустимо для «образцового» пайплайна:** каталоги «голых» JPEG/PNG **без** исходной детекционной разметки; искусственная одна коробка на весь кадр **без** первичных боксов; смешение несогласованных таксонов без явной политики (например землеройки в классе Rodent) без отдельной спецификации.

**Научно обоснованная сборка (птицы):**

1. **Широкий домен** — **MS COCO 2017**, класс `bird` (`bootstrap_detector_yolo.py`): стабильная база масштаба и сцены.  
2. **Доп. визуальный домен** — **Open Images Bird**: боксы в более «зашумлённых» сценах (`--birds-oid-*`).  
3. **Приближение к продакшену** — **Roboflow YOLOv11** (напр. Bird-Feeder): уже YOLO-боксы под кормушечные сцены (`import_roboflow_bird_feeder_birds.py`).  
4. **Fine-grained / позы** — **CUB-200-2011** с официальными прямоугольниками (`convert_cub_to_yolo.py`); держать долю осознанно относительно COCO/OID, чтобы не доминировал сдвиг домена fine-grained → полевые камеры.

**Грызуны:** **Open Images V6** с классами только из списка **boxable** (`--rodent-classes`, в boxable **нет** отдельного `Rat`); при необходимости масштаба — **конвертация COCO instances** (camera traps, LILA): `import_coco_rodents_to_binary.py`; исторически — **OIDv4 Toolkit** → `convert_oidv4_rodent_to_yolo.py`.

**После merge** (`make dataset-merge-three-class` → `datasets/new/detector/yolo/`): **`make dataset-dedupe-detector-yolo`** (дефолт — внутри префиксов `b_`/`r_`/`g_`), **`make dataset-validate-yolo-labels`**, при необходимости профиль и **`make dataset-verify-quality-gates`** (см. #394 в `DATASETS*.md`).

### Классификатор — `datasets/new/classifier/`

| Путь / артефакт | Источник данных |
|-----------------|-----------------|
| **`yolo_cls_eu_hf/`** | Hugging Face **[`gfermoto/birds-eu-merged`](https://huggingface.co/datasets/gfermoto/birds-eu-merged)** — **`download_birds_eu_merged.py`** |
| **`raw/inat_europe_bulk/`** | **iNaturalist**: Europe (`place_id` по умолчанию), **Aves**, research-grade — **`download_inaturalist.py`** |
| **`raw/source_birds525/`** | Слой **birds-525** (HF и зеркала) — **`download_hf_birds.py`** и связанные скрипты |
| **`raw/source_inaturalist/`** | Выборки iNaturalist под отдельные задачи импорта |
| **`yolo_cls/`** | Рабочая YOLO-classification раскладка после merge / правок |
| **`yolo_cls_eu_merged/`** | Результат **`merge_classification_datasets.py`** из нескольких `--inputs` |
| **`yolo_cls_caps_legacy/`** | Исторический слой с именами в CAPS (наследие пайплайна) |
| **`manifests/`**, **`qa/`**, **`reports/`** | Манифесты сборки, QA и отчёты по классам |

Полный EU-пайплайн, добор редких классов и внешние источники (BirdCLEF, CUB, …): **`scripts/datasets/EU_CLASSIFIER.md`**.

### Утилиты — `datasets/new/tools/`

**`build_manifests.py`** — генерация манифестов для детектора и классификатора; см. **`datasets/new/tools/README.md`**.

---

## Ворота подготовки CV / ML (#377)

Перед стартом эпика CV / ML держите контракт detector/classifier из
[CV_ML_PREP](./CV_ML_PREP.ru.md) согласованным с этой страницей. Коротко: боксы
первого детектора попадают в классификатор видов только если их нормализованная
метка входит в `processor.detector_scope` (по умолчанию `["Bird", "Rodent"]`).
Background / hard-negative классы детектора — только detector evidence и должны
оставаться вне этого scope.

---

## Трёхклассовый детектор — эпик [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367), фаза 1

Сборка YOLO-детекции **Bird / Rodent / Background** (согласовано с `detector_labels.normalize_detector_label`). **`make dataset-merge-three-class`** по умолчанию читает **`datasets/new/detector/binary/{birds,rodent,background}/`** и пишет в **`datasets/new/detector/yolo/`**. Альтернатива — три каталога под **`scripts/datasets/binary/`** при ручном вызове merge (см. **`scripts/datasets/README.md`**).

- Точка входа: **`make dataset-merge-three-class`** или `python3 scripts/datasets/merge_datasets_three_class.py --help`.
- Выход по умолчанию (Makefile): **`datasets/new/detector/yolo/dataset.yaml`** и сплиты. Папка **`scripts/datasets/brg/`** — только для упаковки под Drive (см. блок **Актуальные пути** выше).
- Опубликованные архивы: [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main)  
  (`detector_merged_balanced_20260429.zip`, `detector_merged_full_20260429.zip`).
- Манифест hard negatives (учёт курируемых негативов): схема `scripts/datasets/schemas/hard_negatives_manifest_v1.schema.json`, пример `example_hard_negatives_manifest.json`; при слиянии можно передать `--manifest-out`.
- Quality gates (#394): перед обучением делайте экспорт профиля и проверку:
  `python3 scripts/datasets/export_detector_dataset_profile.py --dataset-root datasets/new/detector --out /tmp/detector_profile.json`,
  затем `make dataset-verify-quality-gates PROFILE=/tmp/detector_profile.json`.
- Проверка целостности hard-negatives манифеста (#394):
  `make dataset-verify-hard-negatives MANIFEST=/path/to/hard_negatives_manifest.json`
  (строгий режим: `DATASET_ROOT=scripts/datasets REQUIRE_EXISTING_FILES=1`).

Рекомендованный путь обучения детектора:
- **Stage A (устойчивость):** train на `merged_balanced`
- **Stage B (разнообразие):** fine-tune с весов Stage A на `merged` (full)

Дальнейшие шаги эпика — в [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) / [#368](https://github.com/Gfermoto/BirdLense-Hub/issues/368).

### Датасет `brg` и ZIP для Colab / Drive — происхождение и обогащение

**Стартовые веса для дообучения в Colab:** положите на Drive **`bl_best.pt`** — актуальный чекпоинт **YOLO11n detection** с хаба (или копию из `app/processor/models/detection/weights/`). От него идёт fine-tune по инструкции [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md) (два этапа с `freeze`, затем экспорт OpenVINO). Альтернатива «с нуля» на том же архитектуре: **`YOLO("yolo11n.pt")`** из Ultralytics (автоскачивание), без отдельного файла на Drive.

**Откуда взяты птицы и «мыши» (грызуны) в `brg`:**

- **Bird:** две линии данных: (1) **COCO 2017**, один класс птицы (`bird`), выгрузка через **`bootstrap_detector_yolo.py`** (FiftyOne); (2) обогащение bbox птиц из **Roboflow Universe** — экспорт в формате **YOLOv11**, импорт **`import_roboflow_bird_feeder_birds.py`** (все исходные классы в разметке сводятся в один класс bird). Типичное обогащение кормушкой: **[Bird-Feeder, экспорт YOLOv11](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11)** (версия датасета **v3**; раньше использовали v6 — в метаданных экспорта часто **CC BY 4.0**). Тот же скрипт подходит для любого аналогичного Roboflow ZIP после проверки лицензии на странице проекта; пример другого публичного набора про птиц: **[birds-yolo](https://universe.roboflow.com/birds-detection-2fyqw/birds-yolo)**.

- **Rodent:** в этом пайплайне **не** из Roboflow. Боксы — из **Open Images V6** (классы **OID boxable**, **`--rodent-classes`** в `bootstrap_detector_yolo.py`; отдельного **`Rat`** в boxable нет — см. help скрипта). Доп. масштаб — **COCO instances** (напр. LILA): **`import_coco_rodents_to_binary.py`**; или **OIDv4 Toolkit** → **`convert_oidv4_rodent_to_yolo.py`**. Для качественного детектора **не брать** снимки **без** исходной разметки боксов.

- **Background:** кадры COCO без птицы и пустые лейблы (bootstrap) плюс кадры из папки оператора (**`import_hub_background_folder.py`**, см. этап 4 в таблице).

**Этапы сборки слитого `brg` (Bird / Rodent / Background):**

| Этап | Источник / действие |
|------|---------------------|
| 1 | Локальное дерево **`datasets/new/detector/binary/`** (или **`scripts/datasets/binary/`**): птицы — **COCO 2017** (`bird`), грызуны — **Open Images V6** (boxable **`--rodent-classes`**), фон — COCO без птицы + пустые `.txt`. Наполнение: **`bootstrap_detector_yolo.py`** (`--root datasets/new/detector`). |
| 2 | Слияние в три класса Hub: **`merge_datasets_three_class.py`**. При **`make dataset-merge-three-class`** результат в **`datasets/new/detector/yolo/`**. Дерево **`scripts/datasets/brg/`** для ZIP — копия после следующих шагов или **`--output-dir brg`** при ручном вызове скрипта. |
| 3 | **Обогащение птицами «у кормушки»:** ZIP экспорта Roboflow **YOLOv11** (Bird-Feeder **v3** и др.; лицензия на карточке проекта). Импорт: **`make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=…`** или **`import_roboflow_bird_feeder_birds.py --root datasets/new/detector --zip …`** — все виды → один класс bird (id 0); исходный ZIP удобно хранить в **`datasets/new/detector/raw/`**. Ссылка на выгрузку: [Bird-Feeder YOLOv11](https://universe.roboflow.com/meproject-pcsly/bird-feeder-hhjks/dataset/3/download/yolov11). |
| 4 | **Обогащение фоном реального домена:** кадры из папки оператора (например **`scripts/datasets/detector/Background`**) → **`import_hub_background_folder.py`** в `binary/background` (пустые `.txt`). |
| 5 | **Дедупликация** одинаковых изображений по SHA256 внутри сплита: **`dedupe_yolo_images.py`**. |
| 6 | **Упаковка для Google Drive:** **`pack_brg_for_gdrive.py`** → **`datasets/new/detector/BirdLense_detector_brg_<UTC>.zip`**. |

Colab под этот ZIP и **`bl_best.pt`**: [ML_DETECTOR_COLAB.ru.md](./ML_DETECTOR_COLAB.ru.md). Скрипты и команды: **`scripts/datasets/README.md`**.

---

## Операционный flow в Library (Hub)

Критичный happy-path для ежедневной работы оператора в `Library`:

1. **Импорт с диска** (`Сканировать и импортировать`).
2. **Регенерация** за период (`Спектрограммы` → `Треки`).
3. **Экспорт ZIP датасета** (опционально: `только вручную подтверждённые`).
4. **Обслуживание**: `retro-export` для доэкспорта и `clean dataset` для очистки.

### Период «за всё время»

В `Library` теперь есть пресет **«За всё время»**. Он не угадывает диапазон по календарю, а берёт его из реально найденных записей на диске (`storage/stats`), поэтому безопасно выбирает весь архив без ручного поиска первой даты.

Практический совет:
- начните с **последних 7 или 30 дней**, если хотите оценить скорость операции;
- используйте **«За всё время»**, когда устройство не занято активной съёмкой;
- для очень большого архива самой тяжёлой операцией обычно будет **перегенерация треков**, затем **спектрограммы**; экспорт ZIP датасета обычно легче, если crops уже подготовлены.

Формула метрики «Уникальные посетители» в `System`: количество сессий `SpeciesVisit` за выбранный период (не уникальные особи, а уникальные визит-сессии).

### Экспорт «готово к train»

В `Library -> Экспорт датасета` включите опцию **«Готово к train (авто split train/val, без пост-скрипта)»**.  
Опционально: **«Добавить test split (~10%)»** — в ZIP попадёт и `test/<class>/...` (hold-out).

Для официального цикла дообучения BirdLense используйте:

- `ready_for_train=1`
- `strict_quality=1`
- `only_manually_corrected=1`, когда нужен самый чистый corrective set
- `dataset_info.json` + `classes.txt` как обязательные rollout evidence artifacts

ZIP будет содержать:
- `train/<class>/...`, `val/<class>/...`, при необходимости `test/<class>/...`
- `classes.txt`
- `dataset_info.json` — паспорт выгрузки (`manifest.schema=birdlense_dataset_export_v2`, фильтры, `split_seed`, `fingerprint_sha256_16`) и блок **`quality`**: дубликаты `(video_id, track_id)`, «утечка» одного `video_id` между сплитами.

API: `GET /api/ui/dataset/export` — параметры `test_ratio`, `strict_quality=1` (отменить выгрузку при дубликатах треков, утечке `video_id` между сплитами или если при **ready_for_train** есть классы ниже `min_images_per_class`).

Перед rollout новых весов проверяйте выгрузку и артефакты вместе:

```bash
make validate-weights DATASET_INFO=/path/to/dataset_info.json CLASS_NAMES=/path/to/classes.txt
```

Это убирает обязательный промежуточный запуск `scripts/datasets/export_birdlense_to_yolo.py` для базового сценария дообучения.

---

## 1. Модели

| Компонент | Версия | Дообучено на |
|-----------|--------|--------------|
| **Детектор** | YOLO11n | У шипнутых весов часто указывают линейку NABirds + COCO birds + OID rodent/squirrel; в хабе грызуноподобные боксы → **Rodent**. **Новые сборки** — три класса **Bird / Rodent / Background** (эпик [#367](https://github.com/Gfermoto/BirdLense-Hub/issues/367) выше), не только эта строка таблицы. |
| **Классификатор EU** | YOLO11n-cls | birds-525 + iNaturalist (~491 вид) — активна в `best.pt` |
| **Классификатор US** | YOLO11n-cls | NABirds (~400 видов) — резерв в `best_US.pt` |

Вернуть US: `cp best_US.pt best.pt`.

---

## 2. Формат имён: Scientific (Common)

Единый формат для merge, Frigate, BirdNET, YOLO:

| Источник | Исходный формат | После приведения |
|----------|-----------------|------------------|
| **Frigate** | `Cardinalis cardinalis (Northern Cardinal)` | уже в формате |
| **iNaturalist** | `Columba palumbus` | `Columba palumbus (Common Wood Pigeon)` |
| **birds-525** | `GOLDEN_EAGLE` | `Aquila chrysaetos (Golden Eagle)` |

**YOLO classification:** `train/Parus major (Great Tit)/img.jpg`, `val/` — те же классы.

---

## 3. Скрипты (`scripts/datasets/`)

Полный перечень и детекторный пайплайн — **`scripts/datasets/README.md`**. Ниже — краткий индекс.

### EU-классификатор (birds-525 + iNaturalist)

| Скрипт | Назначение |
|--------|------------|
| `export_birdlense_to_yolo.py` | Локальные кропы BirdLense (`app/data/dataset/train`) → YOLO cls `train/val` |
| `download_hf_birds.py` | Hugging Face → YOLO cls (`--format scientific_common`) |
| `download_inaturalist.py` | iNaturalist Europe → YOLO cls |
| `merge_classification_datasets.py` | Объединить датасеты |
| `download_and_merge_all.sh` | Полный пайплайн → merged_cls |

### Детектор — старые / вспомогательные скрипты

Для части источников всё ещё полезно; **основной трёхклассовый путь** — `bootstrap_detector_yolo.py` + импорты + **`merge_datasets_three_class.py`** (см. README).

| Скрипт | Назначение |
|--------|------------|
| `convert_nabirds_to_yolo.py` | NABirds → YOLO |
| `download_coco_birds.py` | COCO birds — для binary |
| `merge_datasets_binary.py` | NABirds + COCO → один класс «птица» (вход в старые сценарии) |

### Модели (`app/processor/models/`)

| Путь | Роль |
|------|------|
| `classification/weights/best.pt` | EU-классификатор с [HF birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) (YOLO11n-cls, активен) |
| `classification/weights/best_US.pt` | Резерв US (опционально) |
| `classification/weights/class_names.txt` | Allowlist классов для привязки каталога |
| `detection/weights/best.pt` | Бинарный детектор (YOLO11n); zip — форк [AleksandrRogachev94/BirdLense → `app/processor`](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor) |

Всё остальное в `app/processor/models/` — это экспорт/тренировка, а не runtime input.

---

## 4. Источники датасетов

### Для EU (приоритет)

| Датасет | Видов | Ссылка |
|---------|-------|--------|
| **[34data/birds-525-species](https://huggingface.co/datasets/34data/birds-525-species)** | 525 | Hugging Face |
| **iNaturalist Europe** | Тысячи | [API](https://api.inaturalist.org/v1/docs/), `place_id=96372` |

Шипнутый детектор часто описывают как обученный на **NABirds + COCO birds + OIDv4 squirrel** (имена классов Open Images); хаб нормализует «грызуноподобное» в **Rodent**. Эта формулировка может быть старше рецепта **Bird / Rodent / Background** (§ эпик #367 выше). Шипнутый EU-классификатор — на **birds-525 + iNaturalist Europe (~490/491 видов)**.

### Северная Америка (не дают улучшения по EU)

| Датасет | Видов |
|---------|-------|
| NABirds | ~400 |
| [sasha/birdsnap](https://huggingface.co/datasets/sasha/birdsnap) | 500 |
| [randall-lab/cub200](https://huggingface.co/datasets/randall-lab/cub200) | 200 |

---

## 5. Оборудование

| Платформа | GPU | Цена |
|-----------|-----|------|
| **Google Colab** | T4 (15 GB) | Бесплатно |
| **RunPod** | RTX 4090, A100 | ~$0.40–0.80/ч |
| **Локально** | Своя видеокарта | — |

**Рекомендация:** Colab Free (T4) — [TRAINING](./TRAINING.ru.md).

---

## 6. Пайплайн: сбор → обучение

```
BirdLense (записи) → export_birdlense_to_yolo.py → YOLO dataset
                                                      ↓
birds-525 + iNaturalist → merge_classification_datasets.py → merged_cls
                                                                    ↓
                                              TRAINING.md (Colab) → best.pt
```

---

## 7. Платформы для публикации

| Платформа | Назначение |
|-----------|------------|
| **Hugging Face** | [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged), [birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu) — см. [TRAINING](./TRAINING.ru.md) |
| **Hugging Face (детектор)** | [gfermoto/BirdLense_Detector](https://huggingface.co/datasets/gfermoto/BirdLense_Detector/tree/main) — ZIP для 3-классового детектора (balanced + full) |
| **Zenodo** | DOI для статей, снапшоты |

---

См. также: [TRAINING](./TRAINING.ru.md).
