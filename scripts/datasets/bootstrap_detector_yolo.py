#!/usr/bin/env python3
"""
Заполняет дерево ``binary/`` под ``merge_datasets_three_class.py``:

  binary/birds/      — COCO 2017, только класс ``bird`` → один класс в YOLO (id 0).
  binary/rodent/     — Open Images V6, несколько классов грызунов/мелкой фауны (по умолчанию
                       ``Squirrel,Mouse,Hamster,Rabbit,Porcupine``; в OID **boxable** нет отдельного ``Rat``) →
                       один класс (id 0); после merge → Rodent.
  binary/background/ — COCO train/val: кадры **без** ``bird``, пустые ``.txt``.

Зависимости::

    pip install fiftyone pyyaml

Первый запуск качает выборки через FiftyOne (десятки–сотни МБ при дефолтных лимитах).
Сгенерированные папки с изображениями в git не входят — см. корневой ``.gitignore``.
Загрузка идёт **порциями** (``--chunk-size``): файлы появляются в ``binary/`` после каждой порции,
а не только после скачивания тысяч кадров сразу.

Если тот же COCO/OID кадр попадается в другой порции, имя файла на диске уже занято —
раньше создавались ``*_1.jpg``, ``*_2.jpg`` (ложные дубликаты в датасете). Теперь такой
кадр **пропускается**, счётчик цели не увеличивается; при необходимости увеличьте лимиты
или число итераций (seed).

**Cursor / VS Code:** каталоги ``binary/birds`` и т.д. могут быть скрыты в дереве из‑за
``.gitignore`` — смотрите ``ls binary/birds/train/images`` в терминале или включите показ
исключённых файлов.

**Грызуны:** Open Images V6, список классов задаётся ``--rodent-classes``. Нужен доступ к
``storage.googleapis.com``
(метаданные и часть загрузок). Флаг ``--rodent-validation-only`` не качает огромный train CSV.
При обрывах SSL — VPN/другая сеть или скопировать готовый ``~/fiftyone/`` с машины, где OID уже скачан.
Повторы при временных ошибках zoo: ``BIRDLENSE_BOOTSTRAP_ZOO_RETRIES`` (default 15),
``BIRDLENSE_BOOTSTRAP_ZOO_RETRY_BASE_SEC`` (default 5). Меньшие порции при дропах сети:
``BIRDLENSE_BOOTSTRAP_CHUNK_MAX`` (cap размера chunk для COCO bird / OID rodent train, default 960).
Циклический добор до гейта verify: ``scripts/datasets/bootstrap_rodents_until_verify.sh``.

**Прогресс в логе:** при сборе фона переменная ``BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY`` (по умолчанию 100)
включает строки ``[background] … принято уже N/M``; ``0`` отключает. Снимок с диска::
``make detector-etl-progress`` или непрерывно ``make detector-etl-progress-watch`` (интервал ``DETECTOR_WATCH_INTERVAL``).

**Shuffle seed фона:** каждый новый процесс bootstrap для COCO-фона берёт стартовый ``seed`` из числа
уже сохранённых файлов в целевой ``background/*/images`` (иначе повторялся chunk при ``seed=0`` → ``принято 0``).
Переопределение: ``BIRDLENSE_BOOTSTRAP_BG_SEED_START=<int>``.

**Фон без птицы / hard-negative:** если есть ``instances_train2017.json`` / ``instances_val2017.json`` в кэше
FiftyOne (по умолчанию ``~/fiftyone/coco-2017/raw/``) и каталоги ``…/train/data``, ``…/validation/data``,
кадры выбираются **по JSON** (идёт без птицы в аннотациях или с триггерами person/dog/cat), а не через
``max_samples`` zoo — иначе подвыборки снова упираются в уже импортированные файлы. Отключить JSON-путь:
``BIRDLENSE_BOOTSTRAP_BG_JSON=0``. Свои пути: ``COCO_INSTANCES_TRAIN_JSON``, ``COCO_TRAIN_IMAGE_DIR``, и т.п.

Пример::

    cd scripts/datasets
    python3 -m venv .venv-detector && . .venv-detector/bin/activate
    pip install fiftyone pyyaml
    python3 bootstrap_detector_yolo.py --birds-train 300 --birds-val 100 \\
        --rodent-train 200 --rodent-val 80 \\
        --background-train 250 --background-val 150

    # Сильнее детектор: COCO bird + Open Images Bird + hard-negative фон (люди/кошки/собаки):
    python3 bootstrap_detector_yolo.py \\
        --birds-train 2500 --birds-val 700 \\
        --birds-oid-train 0 --birds-oid-val 2500 --birds-oid-validation-only \\
        --rodent-train 3500 --rodent-val 900 \\
        --background-train 4500 --background-val 1200 \\
        --background-hard-train 1800 --background-hard-val 500 \\
        --chunk-size 40 --bg-scan-chunk 800

Опционально подмешать **CUB-200-2011** в ``binary/birds`` (отдельная загрузка датасета):

``python3 convert_cub_to_yolo.py --root <как у bootstrap> --cub-root /path/to/CUB_200_2011``
или ``make dataset-import-cub CUB_ROOT=...``. Roboflow Bird-Feeder YOLOv11:
``make dataset-import-roboflow-bird-feeder ROBOFLOW_ZIP=...``.

Затем из корня репозитория::

    make dataset-merge-three-class
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Защита от бесконечного цикла, если цель по уникальным кадрам недостижима (мало уникальных имён в zoo).
_MAX_BOOTSTRAP_SEED_ITERATIONS = 10_000


def _zoo_chunk_ceiling() -> int:
    """Макс. размер одной порции zoo (env для слабой сети: меньше — меньше потерянных байт при обрыве)."""
    raw = os.environ.get("BIRDLENSE_BOOTSTRAP_CHUNK_MAX", "960").strip()
    try:
        return max(20, int(raw, 10))
    except ValueError:
        return 960


def _load_zoo_dataset_retry(foz, *args, op_tag: str = "zoo", **kwargs):
    """
    Обертка над ``foz.load_zoo_dataset`` с паузами при сетевых/IO сбоях (плохая сеть, TLS reset).

    Env:
      BIRDLENSE_BOOTSTRAP_ZOO_RETRIES — число попыток на один chunk (default 15)
      BIRDLENSE_BOOTSTRAP_ZOO_RETRY_BASE_SEC — базовая пауза, экспонента *2 каждая попытка, cap 120s (default 5)
    """
    try:
        retries = max(1, int(os.environ.get("BIRDLENSE_BOOTSTRAP_ZOO_RETRIES", "15"), 10))
    except ValueError:
        retries = 15
    try:
        base = float(os.environ.get("BIRDLENSE_BOOTSTRAP_ZOO_RETRY_BASE_SEC", "5"))
    except ValueError:
        base = 5.0

    last_exc: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return foz.load_zoo_dataset(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            last_exc = exc
            if attempt >= retries:
                print(
                    f"{op_tag} load_zoo_dataset исчерпал {retries} попыток: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                raise
            delay = min(120.0, base * (2 ** (attempt - 1)))
            print(
                f"{op_tag} load_zoo_dataset попытка {attempt}/{retries} неудачна "
                f"({type(exc).__name__}); пауза {delay:.0f}s",
                flush=True,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _bg_progress_tick(
    kind: str,
    coco_split: str,
    out_tag: str,
    accepted: int,
    target: int,
) -> None:
    """Промежуточный прогресс по числу сохранённых кадров (env см. ниже в doc модуля)."""
    try:
        every = int(os.environ.get("BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY", "100"))
    except ValueError:
        every = 100
    if every <= 0 or accepted <= 0 or accepted % every:
        return
    print(
        f"[{kind}] COCO {coco_split} → {out_tag}/: принято уже {accepted}/{target}",
        flush=True,
    )


def _binary(root: Path) -> Path:
    """Корень ``binary/`` рядом со скриптами: ``scripts/datasets/binary``."""
    return root / "binary"


def _ensure_layout(root: Path) -> None:
    base = _binary(root)
    for sub in ("birds", "rodent", "background"):
        for split in ("train", "val"):
            (base / sub / split / "images").mkdir(parents=True, exist_ok=True)
            (base / sub / split / "labels").mkdir(parents=True, exist_ok=True)


def _count_jpeg_in_dir(images_dir: Path) -> int:
    """JPEG в каталоге (без рекурсии); для сверки квот с уже скачанными файлами."""
    if not images_dir.is_dir():
        return 0
    n = 0
    for p in images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg"):
            n += 1
    return n


def _is_coco_12digit_stem(stem: str) -> bool:
    """Имена кадров COCO bird из bootstrap: ``000000397133.jpg`` → stem 12 цифр."""
    return len(stem) == 12 and stem.isdigit()


def _is_oid_hex16_stem(stem: str) -> bool:
    """Типичные имена Open Images после копирования — 16 hex символов."""
    if len(stem) != 16:
        return False
    try:
        int(stem, 16)
    except ValueError:
        return False
    return True


def _count_bird_jpegs_by_stem(images_dir: Path, stem_pred) -> int:
    if not images_dir.is_dir():
        return 0
    n = 0
    for p in images_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        if stem_pred(p.stem):
            n += 1
    return n


def _rodent_classes_oid_boxable(requested: list[str]) -> tuple[list[str], list[str]]:
    """
    Имена классов для ``foz.load_zoo_dataset(..., classes=...)`` должны совпадать с OID boxable.

    Частый промах: ``Rat`` — ``oi.get_classes()`` может включать имя, а zoo-loader
    для ``open-images-v6`` всё равно пишет ``Ignoring invalid classes``; такие имена
    отбрасываем здесь же.
    """
    import fiftyone.utils.openimages as oi

    allowed = frozenset(oi.get_classes())
    # Строже, чем get_classes(): иначе тишина в stderr от zoo и шум при каждом chunk.
    _oid_v6_zoo_rejects = frozenset({"Rat"})
    keep: list[str] = []
    drop: list[str] = []
    for c in requested:
        if c in _oid_v6_zoo_rejects:
            drop.append(c)
            continue
        if c in allowed:
            keep.append(c)
        else:
            drop.append(c)
    return keep, drop


def _detections(sample) -> list:
    """FiftyOne: COCO/OID обычно кладут боксы в ``ground_truth``."""
    gt = getattr(sample, "ground_truth", None)
    if gt is None:
        return []
    return list(gt.detections) if gt.detections else []


def _write_yolo_label(path: Path, class_id: int, detections) -> None:
    lines = []
    for det in detections:
        x, y, w, h = det.bounding_box
        xc = x + w / 2.0
        yc = y + h / 2.0
        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _copy_once(src: Path, dst_dir: Path) -> Path | None:
    """Копирует ``src`` как ``dst_dir / src.name``, если такого файла ещё нет.

    Если имя уже занято (тот же датасетный кадр из другой порции bootstrap) — возвращает
    ``None``, не создавая ``stem_1``, ``stem_2``.
    """
    dst = dst_dir / src.name
    if dst.exists():
        return None
    shutil.copy2(src, dst)
    return dst


def _unique_copy(src: Path, dst_dir: Path) -> Path:
    """Копирует в ``dst_dir``; при коллизии имени — суффикс ``_<sha256[:8]>`` (OID и hard-negative)."""
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    h = hashlib.sha256(str(src.resolve()).encode("utf-8")).hexdigest()[:8]
    alt = dst_dir / f"{src.stem}_{h}{src.suffix}"
    shutil.copy2(src, alt)
    return alt


_IMG_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})


def _fiftyone_bg_shuffle_seed(images_dir: Path) -> int:
    """Стартовый ``seed`` для ``shuffle`` в FiftyOne между отдельными процессами (волны D/E).

    Раньше каждый запуск начинался с ``seed=0`` — первый chunk COCO совпадал с предыдущим
    прогоном, все имена уже в ``binary/background/...``, ``_copy_once`` → ``None``, в логе
    ``принято 0/M`` при том что порции «просматриваются».

    Приоритет: env ``BIRDLENSE_BOOTSTRAP_BG_SEED_START`` (целое), иначе число уже сохранённых
    изображений в целевой папке (по суффиксу), по модулю большого простого.
    """
    raw = os.environ.get("BIRDLENSE_BOOTSTRAP_BG_SEED_START", "").strip()
    if raw:
        try:
            return int(raw, 10)
        except ValueError:
            pass
    if not images_dir.is_dir():
        return 0
    n = sum(
        1
        for p in images_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMG_SUFFIXES
    )
    return n % 982_451_653


def _detection_labels_lower(sample) -> set[str]:
    return {str(d.label).lower() for d in _detections(sample)}


def _coco_instances_json_default(coco_split: str) -> Path:
    if coco_split == "train":
        return (Path.home() / "fiftyone/coco-2017/raw/instances_train2017.json").resolve()
    if coco_split == "validation":
        return (Path.home() / "fiftyone/coco-2017/raw/instances_val2017.json").resolve()
    raise ValueError(f"unsupported coco_split {coco_split!r}")


def _resolve_coco_instances_json(coco_split: str) -> Path | None:
    env_map = {
        "train": "COCO_INSTANCES_TRAIN_JSON",
        "validation": "COCO_INSTANCES_VAL_JSON",
    }
    key = env_map.get(coco_split)
    if key is None:
        return None
    raw = os.environ.get(key, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    try:
        return _coco_instances_json_default(coco_split)
    except ValueError:
        return None


def _resolve_coco_image_data_dir(coco_split: str) -> Path | None:
    env_map = {
        "train": "COCO_TRAIN_IMAGE_DIR",
        "validation": "COCO_VAL_IMAGE_DIR",
    }
    rel_map = {
        "train": Path("fiftyone/coco-2017/train/data"),
        "validation": Path("fiftyone/coco-2017/validation/data"),
    }
    key = env_map.get(coco_split)
    if key is None or coco_split not in rel_map:
        return None
    raw = os.environ.get(key, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / rel_map[coco_split]).resolve()


def _reserved_coco_numeric_image_ids(root: Path, out_tag: str) -> set[int]:
    """Имена вида ``000000123456.jpg`` в ``birds`` и ``background`` — не брать повторно как фон."""
    ids: set[int] = set()
    for sub in ("background", "birds"):
        imdir = _binary(root) / sub / out_tag / "images"
        if not imdir.is_dir():
            continue
        for p in imdir.iterdir():
            if p.suffix.lower() not in _IMG_SUFFIXES:
                continue
            stem = p.stem
            if stem.isdigit():
                ids.add(int(stem))
    return ids


def _coco_load_instances(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _coco_numeric_image_ids_on_disk(image_data_dir: Path) -> set[int]:
    """Список image_id COCO, для которых в каталоге есть ``{id:012d}.jpg`` (или другой суффикс изображения)."""
    out: set[int] = set()
    if not image_data_dir.is_dir():
        return out
    for p in image_data_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in _IMG_SUFFIXES:
            continue
        stem = p.stem
        if stem.isdigit():
            out.add(int(stem))
    return out


def _coco_category_ids_by_names(coco: dict, names: set[str]) -> set[int]:
    want = {n.lower() for n in names}
    return {
        c["id"]
        for c in coco["categories"]
        if str(c.get("name", "") or "").lower() in want
    }


def _coco_image_ids_with_categories(coco: dict, category_ids: set[int]) -> set[int]:
    if not category_ids:
        return set()
    out: set[int] = set()
    for ann in coco["annotations"]:
        if ann["category_id"] in category_ids:
            out.add(ann["image_id"])
    return out


def _collect_no_bird_background_via_json(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
    instances_json: Path,
    image_data_dir: Path,
) -> int:
    """
    Импорт фона без птицы по ``instances_*2017.json`` + файлам в кэше FiftyOne.

    Нужен, потому что ``load_zoo_dataset(..., max_samples=N, shuffle=True)`` даёт
    подвыборки с огромным пересечением с уже сохранёнными кадрами → ``принято 0``.
    """
    images_dir = _binary(root) / "background" / out_tag / "images"
    labels_dir = _binary(root) / "background" / out_tag / "labels"
    print(
        f"[background-json] COCO {coco_split} → {out_tag}/ из {instances_json} "
        f"(data {image_data_dir}), цель {target}, бюджет просмотра ≤{pool}",
        flush=True,
    )
    coco = _coco_load_instances(instances_json)
    bird_cat = _coco_category_ids_by_names(coco, {"bird"})
    bird_images = _coco_image_ids_with_categories(coco, bird_cat)
    all_ids = [img["id"] for img in coco["images"]]
    reserved = _reserved_coco_numeric_image_ids(root, out_tag)
    eligible = [i for i in all_ids if i not in bird_images and i not in reserved]
    on_disk = _coco_numeric_image_ids_on_disk(image_data_dir)
    eligible_fs = [iid for iid in eligible if iid in on_disk]
    n = 0
    examined = 0
    rng = random.Random(_fiftyone_bg_shuffle_seed(images_dir))
    rng.shuffle(eligible_fs)
    for iid in eligible_fs:
        if n >= target or examined >= pool:
            break
        examined += 1
        fname = f"{iid:012d}.jpg"
        src = image_data_dir / fname
        if not src.is_file():
            continue
        dst_img = _copy_once(src, images_dir)
        if dst_img is None:
            continue
        (labels_dir / f"{dst_img.stem}.txt").write_text("", encoding="utf-8")
        n += 1
        _bg_progress_tick("background-json", coco_split, out_tag, accepted=n, target=target)

    if n < target and out_tag == "val" and pool > examined:
        inj_t = _resolve_coco_instances_json("train")
        idir_t = _resolve_coco_image_data_dir("train")
        if inj_t is not None and idir_t is not None and inj_t.is_file() and idir_t.is_dir():
            print(
                "[background-json] val: кадров из validation/data не хватает (резервация birds/val или неполный кэш) — "
                "добор без птицы из train/data → папка val/ (допустимое пересечение сплитов только для класса фон).",
                flush=True,
            )
            coco_t = _coco_load_instances(inj_t)
            bird_cat_t = _coco_category_ids_by_names(coco_t, {"bird"})
            bird_images_t = _coco_image_ids_with_categories(coco_t, bird_cat_t)
            reserved_val = _reserved_coco_numeric_image_ids(root, "val")
            reserved_train = _reserved_coco_numeric_image_ids(root, "train")
            on_disk_t = _coco_numeric_image_ids_on_disk(idir_t)
            eligible_tr = [
                img["id"]
                for img in coco_t["images"]
                if img["id"] not in bird_images_t
                and img["id"] not in reserved_val
                and img["id"] not in reserved_train
                and img["id"] in on_disk_t
            ]
            rng_t = random.Random(_fiftyone_bg_shuffle_seed(images_dir) + 97_531)
            rng_t.shuffle(eligible_tr)
            for iid in eligible_tr:
                if n >= target or examined >= pool:
                    break
                examined += 1
                fname = f"{iid:012d}.jpg"
                src = idir_t / fname
                if not src.is_file():
                    continue
                dst_img = _copy_once(src, images_dir)
                if dst_img is None:
                    continue
                (labels_dir / f"{dst_img.stem}.txt").write_text("", encoding="utf-8")
                n += 1
                _bg_progress_tick("background-json", coco_split, out_tag, accepted=n, target=target)

    print(
        f"[background-json] → {out_tag}/: {n} images, просмотрено попыток={examined}/{pool} "
        f"( eligible по JSON без bird: {len(eligible)}, из них файл на диске в этом сплите: {len(eligible_fs)} )",
        flush=True,
    )
    return n


def _collect_hard_negative_background_via_json(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
    instances_json: Path,
    image_data_dir: Path,
    trigger_labels: frozenset[str],
) -> int:
    images_dir = _binary(root) / "background" / out_tag / "images"
    labels_dir = _binary(root) / "background" / out_tag / "labels"
    trig_l = {x.lower() for x in trigger_labels}
    print(
        f"[background-hard-json] COCO {coco_split} → {out_tag}/ из {instances_json}, "
        f"триггеры {sorted(trig_l)}, цель {target}, бюджет ≤{pool}",
        flush=True,
    )
    coco = _coco_load_instances(instances_json)
    bird_cat = _coco_category_ids_by_names(coco, {"bird"})
    trig_cat = _coco_category_ids_by_names(coco, trig_l)
    bird_images = _coco_image_ids_with_categories(coco, bird_cat)
    trig_images = _coco_image_ids_with_categories(coco, trig_cat)
    candidates = list(trig_images - bird_images)
    reserved = _reserved_coco_numeric_image_ids(root, out_tag)
    eligible = [i for i in candidates if i not in reserved]
    on_disk = _coco_numeric_image_ids_on_disk(image_data_dir)
    eligible_fs = [iid for iid in eligible if iid in on_disk]
    rng = random.Random(_fiftyone_bg_shuffle_seed(images_dir) + 17)
    rng.shuffle(eligible_fs)
    n = 0
    examined = 0
    for iid in eligible_fs:
        if n >= target or examined >= pool:
            break
        examined += 1
        fname = f"{iid:012d}.jpg"
        src = image_data_dir / fname
        if not src.is_file():
            continue
        dst_img = _unique_copy(src, images_dir)
        (labels_dir / f"{dst_img.stem}.txt").write_text("", encoding="utf-8")
        n += 1
        _bg_progress_tick("background-hard-json", coco_split, out_tag, accepted=n, target=target)
    print(
        f"[background-hard-json] → {out_tag}/: {n} images, просмотрено попыток={examined}/{pool} "
        f"(триггер-кандидатов по JSON: {len(eligible)}, файл на диске: {len(eligible_fs)})",
        flush=True,
    )
    return n


def _coco_zoo_bucket(coco_split: str) -> str:
    """Каталог на images.cocodataset.org под сплиты FiftyOne."""
    if coco_split == "train":
        return "train2017"
    if coco_split == "validation":
        return "val2017"
    raise ValueError(f"unsupported coco_split {coco_split!r}")


def _coco_http_download_trainval_jpg(iid: int, image_data_dir: Path, coco_split: str) -> Path | None:
    """Скачать ``{012d}.jpg`` с официального зеркала COCO, если файла ещё нет в кэше."""
    stem = f"{iid:012d}"
    dest = image_data_dir / f"{stem}.jpg"
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    bucket = _coco_zoo_bucket(coco_split)
    url = f"http://images.cocodataset.org/{bucket}/{stem}.jpg"
    image_data_dir.mkdir(parents=True, exist_ok=True)
    try:
        timeout = float(os.environ.get("BIRDLENSE_COCO_DL_TIMEOUT_SEC", "90"))
    except ValueError:
        timeout = 90.0
    try:
        retries = int(os.environ.get("BIRDLENSE_COCO_DL_RETRIES", "4"), 10)
    except ValueError:
        retries = 4
    delay = 1.0
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BirdLense-bootstrap/1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if not data:
                return None
            dest.write_bytes(data)
            return dest
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt + 1 >= retries:
                print(f"[birds-json] HTTP {e.code} for {url}", flush=True)
                return None
        except OSError as e:
            if attempt + 1 >= retries:
                print(f"[birds-json] download fail {url}: {e}", flush=True)
                return None
        time.sleep(delay)
        delay = min(delay * 1.8, 30.0)
    return None


def _coco_image_path_for_id(image_data_dir: Path, iid: int) -> Path | None:
    stem = f"{iid:012d}"
    for ext in (".jpg", ".jpeg", ".JPG", ".JPEG"):
        p = image_data_dir / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


def _coco_bird_bboxes_per_image(coco: dict, bird_cat_ids: set[int]) -> dict[int, list[list[float]]]:
    out: dict[int, list[list[float]]] = {}
    for ann in coco["annotations"]:
        if ann["category_id"] not in bird_cat_ids:
            continue
        bbox = ann.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x, y, w, h = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        if w <= 0 or h <= 0:
            continue
        iid = ann["image_id"]
        out.setdefault(iid, []).append([x, y, w, h])
    return out


def _yolo_label_text_from_coco_boxes_px(bboxes: list[list[float]], iw: int, ih: int) -> str:
    lines: list[str] = []
    for bbox in bboxes:
        x, y, w, h = bbox
        xc = (x + w / 2.0) / iw
        yc = (y + h / 2.0) / ih
        nw = w / iw
        nh = h / ih
        xc = min(1.0, max(0.0, xc))
        yc = min(1.0, max(0.0, yc))
        nw = min(1.0, max(0.0, nw))
        nh = min(1.0, max(0.0, nh))
        lines.append(f"0 {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")
    return "".join(lines)


def _bootstrap_birds_via_json_for_split(
    root: Path,
    *,
    coco_split: str,
    out_tag: str,
    goal: int,
) -> int:
    """Добор COCO bird через instances_*.json + локальный кэш FiftyOne — без zoo-chunk застревания."""
    if goal <= 0:
        print(f"[birds-json] → {out_tag}/: добор 0 — пропуск", flush=True)
        return 0
    inj = _resolve_coco_instances_json(coco_split)
    idir = _resolve_coco_image_data_dir(coco_split)
    if inj is None or not inj.is_file():
        print(f"[birds-json] нет аннотаций COCO для {coco_split}: {inj}", flush=True)
        return 0
    if idir is None:
        print(f"[birds-json] нет каталога изображений для {coco_split}", flush=True)
        return 0
    allow_http = os.environ.get("BIRDLENSE_BOOTSTRAP_COCO_HTTP", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    idir.mkdir(parents=True, exist_ok=True)
    images_dir = _binary(root) / "birds" / out_tag / "images"
    labels_dir = _binary(root) / "birds" / out_tag / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    coco = _coco_load_instances(inj)
    bird_cat_ids = _coco_category_ids_by_names(coco, {"bird"})
    id_to_boxes = _coco_bird_bboxes_per_image(coco, bird_cat_ids)
    id_to_wh: dict[int, tuple[int, int]] = {}
    for im in coco["images"]:
        wid = im.get("width")
        het = im.get("height")
        if wid is None or het is None:
            continue
        id_to_wh[im["id"]] = (int(wid), int(het))
    eligible_full = sorted(iid for iid in id_to_boxes if iid in id_to_wh)
    on_disk_n = len(_coco_numeric_image_ids_on_disk(idir))
    rng_seed = _fiftyone_bg_shuffle_seed(images_dir)
    eligible = eligible_full[:]
    rng = random.Random(rng_seed ^ (0x9E3779B9 + len(eligible)))
    rng.shuffle(eligible)
    print(
        f"[birds-json] COCO {coco_split} → {out_tag}/: цель новых jpg до {goal}; "
        f"кадров с bird в JSON: {len(eligible_full)}; уже в кэше {on_disk_n} jpg; "
        f"HTTP-докачка: {allow_http}; rng_seed≈{rng_seed}",
        flush=True,
    )
    accepted = 0
    every = int(os.environ.get("BIRDLENSE_BOOTSTRAP_BG_PROGRESS_EVERY", "250") or "250") or 250
    examined = 0
    for iid in eligible:
        if accepted >= goal:
            break
        examined += 1
        iw, ih = id_to_wh[iid]
        if iw <= 0 or ih <= 0:
            continue
        bxs = id_to_boxes.get(iid)
        if not bxs:
            continue
        ytxt = _yolo_label_text_from_coco_boxes_px(bxs, iw, ih)
        if not ytxt.strip():
            continue
        src = _coco_image_path_for_id(idir, iid)
        if src is None and allow_http:
            src = _coco_http_download_trainval_jpg(iid, idir, coco_split)
        if src is None:
            continue
        dst_img = _copy_once(src, images_dir)
        if dst_img is None:
            continue
        (labels_dir / f"{dst_img.stem}.txt").write_text(ytxt, encoding="utf-8")
        accepted += 1
        if every > 0 and accepted % every == 0:
            print(
                f"[birds-json] {out_tag}/: уже +{accepted}/{goal}, просмотрено порядком {examined}/{len(eligible)}",
                flush=True,
            )
    print(f"[birds-json] → {out_tag}/: добавлено {accepted} (цель добора этого вызова: {goal})", flush=True)
    return accepted


def _bootstrap_birds_via_fiftyone(
    root: Path, train_max: int, val_max: int, *, chunk_size: int
) -> None:
    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        if lim <= 0:
            print(f"[birds] zoo → {tag}/: пропуск (добор COCO 0)")
            continue
        images_dir = _binary(root) / "birds" / tag / "images"
        labels_dir = _binary(root) / "birds" / tag / "labels"
        total = 0
        seed = 0
        dup_streak = 0
        while total < lim:
            if seed >= _MAX_BOOTSTRAP_SEED_ITERATIONS:
                print(
                    f"[birds] стоп: {seed} итераций seed, собрано {total}/{lim} для {split_name} — "
                    "увеличьте лимиты zoo или ослабьте фильтры",
                )
                break
            mult = 1 << min(dup_streak // 3, 3)
            take = min(max(chunk_size, chunk_size * mult), _zoo_chunk_ceiling(), lim - total)
            print(
                f"[birds] COCO 2017 {split_name} bird — chunk size={take}, seed={seed}, "
                f"have {total}/{lim}, dup_waste×{mult}"
            )
            ds = _load_zoo_dataset_retry(
                foz,
                "coco-2017",
                op_tag="[birds]",
                split=split_name,
                label_types=["detections"],
                classes=["bird"],
                max_samples=take,
                shuffle=True,
                seed=seed,
            )
            n_chunk = 0
            candidates = 0
            for sample in ds:
                birds = [d for d in _detections(sample) if d.label == "bird"]
                if not birds:
                    continue
                candidates += 1
                dst_img = _copy_once(Path(sample.filepath), images_dir)
                if dst_img is None:
                    continue
                stem = dst_img.stem
                _write_yolo_label(labels_dir / f"{stem}.txt", 0, birds)
                n_chunk += 1
                total += 1
                if total >= lim:
                    break
            fo.delete_dataset(ds.name)
            seed += 1
            if n_chunk == 0:
                if candidates == 0:
                    print(f"[birds] предупреждение: в chunk нет кадров с bird для {split_name}, прерываем сплит")
                    break
                dup_streak += 1
                print(
                    f"[birds] chunk seed={seed - 1}: кадры с bird были, но все уже в {tag}/ — "
                    f"следующий seed (собрано {total}/{lim}, dup_streak={dup_streak})",
                )
                continue
            dup_streak = 0
        print(f"[birds] zoo → {tag}/: {total} images")


def _bootstrap_birds(root: Path, train_max: int, val_max: int, *, chunk_size: int) -> None:
    """COCO bird: по умолчанию через JSON-кэш (быстро); недобор добивает FiftyOne zoo.

    Выключить JSON: ``BIRDLENSE_BOOTSTRAP_BIRD_JSON=0``.
    """
    use_json = os.environ.get("BIRDLENSE_BOOTSTRAP_BIRD_JSON", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if use_json:
        at = _bootstrap_birds_via_json_for_split(
            root, coco_split="train", out_tag="train", goal=train_max
        )
        av = _bootstrap_birds_via_json_for_split(
            root, coco_split="validation", out_tag="val", goal=val_max
        )
        train_max -= at
        val_max -= av
        if train_max <= 0 and val_max <= 0:
            return
        if at > 0 or av > 0:
            print(
                f"[birds-json] остаток после JSON: дополнительно пробуем zoo — train need {train_max}, val need {val_max}",
                flush=True,
            )
    _bootstrap_birds_via_fiftyone(root, train_max, val_max, chunk_size=chunk_size)


def _bird_oid_detections(detections) -> list:
    """Open Images: класс птицы обычно ``Bird`` (регистр может отличаться)."""
    out = []
    for d in detections:
        lab = str(getattr(d, "label", "") or "").lower()
        if lab == "bird":
            out.append(d)
    return out


def _bootstrap_birds_open_images_validation_only(
    root: Path,
    train_max: int,
    val_max: int,
    *,
    chunk_size: int,
) -> None:
    """Птицы из Open Images V6, только split validation (меньше метаданных)."""
    import fiftyone as fo
    import fiftyone.zoo as foz

    images_train = _binary(root) / "birds" / "train" / "images"
    labels_train = _binary(root) / "birds" / "train" / "labels"
    images_val = _binary(root) / "birds" / "val" / "images"
    labels_val = _binary(root) / "birds" / "val" / "labels"
    got_train = 0
    got_val = 0
    seed = 0
    total_need = train_max + val_max
    if total_need <= 0:
        print("[birds-oid] validation-only: добор 0 — пропуск")
        return
    while got_train + got_val < total_need:
        take = min(chunk_size, total_need - got_train - got_val)
        print(
            f"[birds-oid] Open Images V6 validation Bird — chunk size={take}, seed={seed}, "
            f"train {got_train}/{train_max}, val {got_val}/{val_max}"
        )
        ds = _load_zoo_dataset_retry(
            foz,
            "open-images-v6",
            op_tag="[birds-oid]",
            split="validation",
            label_types=["detections"],
            classes=["Bird"],
            max_samples=take,
            only_matching=True,
            shuffle=True,
            seed=seed,
        )
        n_chunk = 0
        for sample in ds:
            birds = _bird_oid_detections(_detections(sample))
            if not birds:
                continue
            if got_train < train_max:
                dst_img = _unique_copy(Path(sample.filepath), images_train)
                stem = dst_img.stem
                _write_yolo_label(labels_train / f"{stem}.txt", 0, birds)
                got_train += 1
            elif got_val < val_max:
                dst_img = _unique_copy(Path(sample.filepath), images_val)
                stem = dst_img.stem
                _write_yolo_label(labels_val / f"{stem}.txt", 0, birds)
                got_val += 1
            n_chunk += 1
            if got_train >= train_max and got_val >= val_max:
                break
        fo.delete_dataset(ds.name)
        seed += 1
        if n_chunk == 0:
            print("[birds-oid] предупреждение: пустой chunk (validation-only), прерываем")
            break
    print(f"[birds-oid] → train/: {got_train}, val/: {got_val} (источник: OID validation)")


def _bootstrap_birds_open_images(
    root: Path,
    train_max: int,
    val_max: int,
    *,
    chunk_size: int,
    validation_only: bool,
) -> None:
    """Дополнительные кадры «птица» из Open Images (боксы Bird → YOLO id 0)."""
    if train_max <= 0 and val_max <= 0:
        return
    if validation_only:
        _bootstrap_birds_open_images_validation_only(
            root, train_max, val_max, chunk_size=chunk_size
        )
        return

    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        if lim <= 0:
            print(f"[birds-oid] пропуск {tag}: лимит 0")
            continue
        images_dir = _binary(root) / "birds" / tag / "images"
        labels_dir = _binary(root) / "birds" / tag / "labels"
        total = 0
        seed = 0
        while total < lim:
            take = min(chunk_size, lim - total)
            print(
                f"[birds-oid] Open Images V6 {split_name} Bird — chunk size={take}, "
                f"seed={seed}, have {total}/{lim}"
            )
            ds = _load_zoo_dataset_retry(
                foz,
                "open-images-v6",
                op_tag="[birds-oid]",
                split=split_name,
                label_types=["detections"],
                classes=["Bird"],
                max_samples=take,
                only_matching=True,
                shuffle=True,
                seed=seed,
            )
            n_chunk = 0
            for sample in ds:
                birds = _bird_oid_detections(_detections(sample))
                if not birds:
                    continue
                dst_img = _unique_copy(Path(sample.filepath), images_dir)
                stem = dst_img.stem
                _write_yolo_label(labels_dir / f"{stem}.txt", 0, birds)
                n_chunk += 1
                total += 1
                if total >= lim:
                    break
            fo.delete_dataset(ds.name)
            seed += 1
            if n_chunk == 0:
                print(f"[birds-oid] предупреждение: пустой chunk для {split_name}, прерываем сплит")
                break
        print(f"[birds-oid] → {tag}/: {total} images")


def _bootstrap_rodents_validation_only(
    root: Path,
    train_max: int,
    val_max: int,
    *,
    chunk_size: int,
    rodent_classes: list[str],
) -> None:
    """Только split ``validation`` Open Images: меньше метаданных, без гигантского train CSV."""
    import fiftyone as fo
    import fiftyone.zoo as foz

    images_train = _binary(root) / "rodent" / "train" / "images"
    labels_train = _binary(root) / "rodent" / "train" / "labels"
    images_val = _binary(root) / "rodent" / "val" / "images"
    labels_val = _binary(root) / "rodent" / "val" / "labels"
    got_train = 0
    got_val = 0
    seed = 0
    total_need = train_max + val_max
    while got_train + got_val < total_need:
        if seed >= _MAX_BOOTSTRAP_SEED_ITERATIONS:
            print(
                f"[rodent] validation-only стоп: {seed} итераций seed, "
                f"train {got_train}/{train_max}, val {got_val}/{val_max}",
            )
            break
        take = min(chunk_size, total_need - got_train - got_val)
        print(
            f"[rodent] Open Images V6 validation-only {','.join(rodent_classes)} — chunk size={take}, "
            f"seed={seed}, train {got_train}/{train_max}, val {got_val}/{val_max}"
        )
        ds = _load_zoo_dataset_retry(
            foz,
            "open-images-v6",
            op_tag="[rodent]",
            split="validation",
            label_types=["detections"],
            classes=rodent_classes,
            max_samples=take,
            only_matching=True,
            shuffle=True,
            seed=seed,
        )
        n_chunk = 0
        candidates = 0
        for sample in ds:
            rods = [d for d in _detections(sample) if d.label in rodent_classes]
            if not rods:
                continue
            candidates += 1
            if got_train < train_max:
                dst_img = _copy_once(Path(sample.filepath), images_train)
                if dst_img is None:
                    continue
                stem = dst_img.stem
                _write_yolo_label(labels_train / f"{stem}.txt", 0, rods)
                got_train += 1
                n_chunk += 1
            elif got_val < val_max:
                dst_img = _copy_once(Path(sample.filepath), images_val)
                if dst_img is None:
                    continue
                stem = dst_img.stem
                _write_yolo_label(labels_val / f"{stem}.txt", 0, rods)
                got_val += 1
                n_chunk += 1
            if got_train >= train_max and got_val >= val_max:
                break
        fo.delete_dataset(ds.name)
        seed += 1
        if n_chunk == 0:
            if candidates == 0:
                print("[rodent] предупреждение: пустой chunk (validation-only), прерываем")
                break
            print(
                f"[rodent] validation-only: chunk seed={seed - 1} только дубликаты имён — следующий seed "
                f"(train {got_train}/{train_max}, val {got_val}/{val_max})",
            )
    print(f"[rodent] → train/: {got_train} images (validation split)")
    print(f"[rodent] → val/: {got_val} images (validation split)")


def _bootstrap_rodents(
    root: Path,
    train_max: int,
    val_max: int,
    *,
    chunk_size: int,
    rodent_classes: list[str],
    validation_only: bool = False,
) -> None:
    if validation_only:
        _bootstrap_rodents_validation_only(
            root,
            train_max,
            val_max,
            chunk_size=chunk_size,
            rodent_classes=rodent_classes,
        )
        return

    import fiftyone as fo
    import fiftyone.zoo as foz

    for split_name, lim, tag in (
        ("train", train_max, "train"),
        ("validation", val_max, "val"),
    ):
        if lim <= 0:
            print(f"[rodent] → {tag}/: пропуск (добор 0, уже достаточно на диске)")
            continue
        images_dir = _binary(root) / "rodent" / tag / "images"
        labels_dir = _binary(root) / "rodent" / tag / "labels"
        total = 0
        seed = 0
        dup_streak = 0
        while total < lim:
            if seed >= _MAX_BOOTSTRAP_SEED_ITERATIONS:
                print(
                    f"[rodent] стоп: {seed} итераций seed, собрано {total}/{lim} для {split_name}",
                )
                break
            mult = 1 << min(dup_streak // 3, 3)
            take = min(max(chunk_size, chunk_size * mult), _zoo_chunk_ceiling(), lim - total)
            print(
                f"[rodent] Open Images V6 {split_name} {','.join(rodent_classes)} — "
                f"chunk size={take}, seed={seed}, have {total}/{lim}, dup_waste×{mult}",
            )
            ds = _load_zoo_dataset_retry(
                foz,
                "open-images-v6",
                op_tag="[rodent]",
                split=split_name,
                label_types=["detections"],
                classes=rodent_classes,
                max_samples=take,
                only_matching=True,
                shuffle=True,
                seed=seed,
            )
            n_chunk = 0
            candidates = 0
            for sample in ds:
                rods = [d for d in _detections(sample) if d.label in rodent_classes]
                if not rods:
                    continue
                candidates += 1
                dst_img = _copy_once(Path(sample.filepath), images_dir)
                if dst_img is None:
                    continue
                stem = dst_img.stem
                _write_yolo_label(labels_dir / f"{stem}.txt", 0, rods)
                n_chunk += 1
                total += 1
                if total >= lim:
                    break
            fo.delete_dataset(ds.name)
            seed += 1
            if n_chunk == 0:
                if candidates == 0:
                    print(f"[rodent] предупреждение: пустой chunk для {split_name}, прерываем сплит")
                    break
                dup_streak += 1
                print(
                    f"[rodent] chunk seed={seed - 1}: только дубликаты имён — следующий seed "
                    f"(собрано {total}/{lim}, dup_streak={dup_streak})",
                )
                continue
            dup_streak = 0
        print(f"[rodent] → {tag}/: {total} images")


def _collect_no_bird_background(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
    scan_chunk: int,
) -> int:
    images_dir = _binary(root) / "background" / out_tag / "images"
    labels_dir = _binary(root) / "background" / out_tag / "labels"
    use_json = os.environ.get("BIRDLENSE_BOOTSTRAP_BG_JSON", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    inj = _resolve_coco_instances_json(coco_split)
    idir = _resolve_coco_image_data_dir(coco_split)
    if (
        use_json
        and inj is not None
        and idir is not None
        and inj.is_file()
        and idir.is_dir()
    ):
        return _collect_no_bird_background_via_json(
            root,
            coco_split=coco_split,
            pool=pool,
            target=target,
            out_tag=out_tag,
            instances_json=inj,
            image_data_dir=idir,
        )
    print(
        "[background] JSON-путь недоступен (нет аннотаций или каталога data) — "
        "fallback FiftyOne zoo; задайте кэш COCO или BIRDLENSE_BOOTSTRAP_BG_JSON=0 принудительно.",
        flush=True,
    )
    import fiftyone as fo
    import fiftyone.zoo as foz

    seen_fp: set[str] = set()
    n = 0
    seed = _fiftyone_bg_shuffle_seed(images_dir)
    zero_streak = 0
    print(
        f"[background] COCO {coco_split} → {out_tag}/: цель {target} кадров без bird, "
        f"бюджет уникальных путей ≤{pool}, порции по {scan_chunk}",
        flush=True,
    )
    # Считать бюджет по числу *новых* путей (первый просмотр), а не по chunk*итерациям:
    # иначе при shuffle к одним и тем же jpg в val быстро съедается pool, не обойдя весь сплит.
    while n < target and len(seen_fp) < pool:
        chunk = min(scan_chunk, max(1, pool - len(seen_fp)))
        print(
            f"[background] chunk seed={seed}, samples={chunk}, "
            f"уникальных {len(seen_fp)}/{pool}, принято {n}/{target}",
            flush=True,
        )
        ds = _load_zoo_dataset_retry(
            foz,
            "coco-2017",
            op_tag="[background]",
            split=coco_split,
            label_types=["detections"],
            max_samples=chunk,
            shuffle=True,
            seed=seed,
        )
        novel = 0
        for sample in ds:
            fp = sample.filepath
            if fp in seen_fp:
                continue
            fname = Path(fp).name
            if (images_dir / fname).exists():
                seen_fp.add(fp)
                continue
            seen_fp.add(fp)
            novel += 1
            if "bird" in _detection_labels_lower(sample):
                continue
            dst_img = _copy_once(Path(sample.filepath), images_dir)
            if dst_img is None:
                continue
            stem = dst_img.stem
            (labels_dir / f"{stem}.txt").write_text("", encoding="utf-8")
            n += 1
            _bg_progress_tick(
                "background",
                coco_split,
                out_tag,
                accepted=n,
                target=target,
            )
            if n >= target:
                break
        fo.delete_dataset(ds.name)
        seed += 1
        if novel == 0:
            zero_streak += 1
            if zero_streak >= 40:
                print(
                    f"[background] {zero_streak} батчей подряд без новых путей — дальше "
                    f"нельзя (кэш COCO неполон?). Принято {n}/{target}.",
                    flush=True,
                )
                break
        else:
            zero_streak = 0
    print(f"[background] → {out_tag}/: {n} images (empty labels)", flush=True)
    return n


def _collect_hard_negative_background(
    root: Path,
    *,
    coco_split: str,
    pool: int,
    target: int,
    out_tag: str,
    scan_chunk: int,
    trigger_labels: frozenset[str],
) -> int:
    """
    Фон с пустыми метками: кадр содержит хотя бы один из trigger_labels (person/dog/cat),
    но **нет** bird — снижает ложные срабатывания «птица» на людей и домашних животных.
    """
    images_dir = _binary(root) / "background" / out_tag / "images"
    labels_dir = _binary(root) / "background" / out_tag / "labels"
    use_json = os.environ.get("BIRDLENSE_BOOTSTRAP_BG_JSON", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    inj = _resolve_coco_instances_json(coco_split)
    idir = _resolve_coco_image_data_dir(coco_split)
    if (
        use_json
        and inj is not None
        and idir is not None
        and inj.is_file()
        and idir.is_dir()
    ):
        return _collect_hard_negative_background_via_json(
            root,
            coco_split=coco_split,
            pool=pool,
            target=target,
            out_tag=out_tag,
            instances_json=inj,
            image_data_dir=idir,
            trigger_labels=trigger_labels,
        )
    print(
        "[background-hard] JSON недоступен — fallback FiftyOne zoo.",
        flush=True,
    )
    import fiftyone as fo
    import fiftyone.zoo as foz

    seen_fp: set[str] = set()
    n = 0
    seed = _fiftyone_bg_shuffle_seed(images_dir)
    zero_streak = 0
    trig_l = {x.lower() for x in trigger_labels}
    print(
        f"[background-hard] COCO {coco_split} → {out_tag}/: цель {target}, триггеры {sorted(trig_l)}, "
        f"бюджет уникальных путей ≤{pool}",
        flush=True,
    )
    while n < target and len(seen_fp) < pool:
        chunk = min(scan_chunk, max(1, pool - len(seen_fp)))
        print(
            f"[background-hard] chunk seed={seed}, samples={chunk}, "
            f"уникальных {len(seen_fp)}/{pool}, принято {n}/{target}",
            flush=True,
        )
        ds = _load_zoo_dataset_retry(
            foz,
            "coco-2017",
            op_tag="[background-hard]",
            split=coco_split,
            label_types=["detections"],
            max_samples=chunk,
            shuffle=True,
            seed=seed,
        )
        novel = 0
        for sample in ds:
            fp = sample.filepath
            if fp in seen_fp:
                continue
            fname = Path(fp).name
            if (images_dir / fname).exists():
                seen_fp.add(fp)
                continue
            seen_fp.add(fp)
            novel += 1
            labs = _detection_labels_lower(sample)
            if "bird" in labs:
                continue
            if not labs.intersection(trig_l):
                continue
            dst_img = _unique_copy(Path(sample.filepath), images_dir)
            stem = dst_img.stem
            (labels_dir / f"{stem}.txt").write_text("", encoding="utf-8")
            n += 1
            _bg_progress_tick(
                "background-hard",
                coco_split,
                out_tag,
                accepted=n,
                target=target,
            )
            if n >= target:
                break
        fo.delete_dataset(ds.name)
        seed += 1
        if novel == 0:
            zero_streak += 1
            if zero_streak >= 40:
                print(
                    f"[background-hard] остановка после {zero_streak} пустых батчей; принято {n}/{target}.",
                    flush=True,
                )
                break
        else:
            zero_streak = 0
    print(f"[background-hard] → {out_tag}/: {n} images (empty labels)", flush=True)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Корень выхода (по умолчанию scripts/datasets)",
    )
    ap.add_argument("--birds-train", type=int, default=400, help="COCO 2017: кадры с классом bird")
    ap.add_argument("--birds-val", type=int, default=120)
    ap.add_argument(
        "--birds-oid-train",
        type=int,
        default=0,
        help="Дополнительно: Open Images V6 Bird, train (0 = отключено; тяжёлый CSV train)",
    )
    ap.add_argument(
        "--birds-oid-val",
        type=int,
        default=0,
        help="Дополнительно: Open Images V6 Bird, validation",
    )
    ap.add_argument(
        "--birds-oid-validation-only",
        action="store_true",
        help="Брать OID-птиц только из сплита validation (квоты train/val кладутся в папки как у rodent)",
    )
    ap.add_argument("--rodent-train", type=int, default=300)
    ap.add_argument("--rodent-val", type=int, default=80)
    ap.add_argument(
        "--rodent-classes",
        type=str,
        default="Squirrel,Mouse,Hamster,Rabbit,Porcupine",
        help="Open Images **boxable** классы для Rodent (через запятую); «Rat» в OID boxable нет",
    )
    ap.add_argument("--background-train", type=int, default=280)
    ap.add_argument("--background-val", type=int, default=120)
    ap.add_argument(
        "--background-hard-train",
        type=int,
        default=0,
        help="Доп. фон: COCO кадры с person/dog/cat и без bird (пустые txt), train",
    )
    ap.add_argument(
        "--background-hard-val",
        type=int,
        default=0,
        help="То же для val",
    )
    ap.add_argument(
        "--background-hard-labels",
        type=str,
        default="person,dog,cat",
        help="Метки COCO (lower case), при наличии которых кадр кандидат в hard-negative",
    )
    ap.add_argument("--background-train-pool", type=int, default=12000, help="Сколько кадров COCO train просмотреть")
    ap.add_argument("--background-val-pool", type=int, default=8000, help="Сколько кадров COCO val просмотреть")
    ap.add_argument(
        "--chunk-size",
        type=int,
        default=35,
        help="Сколько образцов подряд запрашивать у FiftyOne за один проход (меньше — раньше появятся файлы на диске)",
    )
    ap.add_argument(
        "--bg-scan-chunk",
        type=int,
        default=600,
        help="Размер порции при сканировании COCO для фона (без единого огромного prefetch)",
    )
    ap.add_argument("--skip-birds", action="store_true", help="Пропустить весь блок птиц (COCO + OID)")
    ap.add_argument(
        "--skip-birds-coco",
        action="store_true",
        help="Только COCO bird; OID-птицы остаются (если не --skip-birds)",
    )
    ap.add_argument(
        "--skip-birds-oid",
        action="store_true",
        help="Только Open Images Bird; COCO остаётся (если не --skip-birds)",
    )
    ap.add_argument("--skip-rodents", action="store_true")
    ap.add_argument("--skip-background", action="store_true", help="Весь фон: soft + hard")
    ap.add_argument(
        "--skip-background-soft",
        action="store_true",
        help="Не собирать «простой» фон (COCO без bird); hard может остаться",
    )
    ap.add_argument(
        "--skip-background-hard",
        action="store_true",
        help="Не собирать hard-negative фон (person/dog/cat)",
    )
    ap.add_argument(
        "--rodent-validation-only",
        action="store_true",
        help="Грызуны только из сплита validation Open Images (без скачивания огромного train CSV)",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    try:
        import fiftyone as fo  # noqa: F401
        import fiftyone.zoo as foz  # noqa: F401
    except ImportError:
        print("Установите: pip install fiftyone", file=sys.stderr)
        return 2

    _ensure_layout(root)

    ch = max(5, args.chunk_size)
    bg_ch = max(100, args.bg_scan_chunk)
    rodent_classes = [c.strip() for c in args.rodent_classes.split(",") if c.strip()]
    if not rodent_classes:
        print("--rodent-classes не должен быть пустым", file=sys.stderr)
        return 2

    if not args.skip_rodents:
        resolved, bad = _rodent_classes_oid_boxable(rodent_classes)
        if bad:
            print(
                "[rodent] игнорируются не‑boxable имена Open Images (в т.ч. опечатки): "
                + ", ".join(bad),
                file=sys.stderr,
            )
            print(
                "[rodent] см. доступные имена: "
                "`python -c \"import fiftyone.utils.openimages as oi; print(sorted(oi.get_classes()))\"`",
                file=sys.stderr,
            )
        rodent_classes = resolved
        if not rodent_classes:
            print(
                "--rodent-classes после проверки OID boxable пуст; задайте валидные имена.",
                file=sys.stderr,
            )
            return 2

    if not args.skip_birds:
        b_train_img = _binary(root) / "birds" / "train" / "images"
        b_val_img = _binary(root) / "birds" / "val" / "images"
        if not args.skip_birds_coco:
            have_bt = _count_bird_jpegs_by_stem(b_train_img, _is_coco_12digit_stem)
            have_bv = _count_bird_jpegs_by_stem(b_val_img, _is_coco_12digit_stem)
            need_bt = max(0, args.birds_train - have_bt)
            need_bv = max(0, args.birds_val - have_bv)
            print(
                f"[birds] COCO bird на диске (12-digit stem): train {have_bt}/{args.birds_train}, "
                f"val {have_bv}/{args.birds_val}; добор {need_bt}/{need_bv}",
                flush=True,
            )
            if need_bt > 0 or need_bv > 0:
                _bootstrap_birds(root, need_bt, need_bv, chunk_size=ch)
            else:
                print("[birds] COCO квоты уже выполнены — пропуск COCO bird", flush=True)
        if not args.skip_birds_oid:
            have_oid_t = _count_bird_jpegs_by_stem(b_train_img, _is_oid_hex16_stem)
            have_oid_v = _count_bird_jpegs_by_stem(b_val_img, _is_oid_hex16_stem)
            need_oid_t = max(0, args.birds_oid_train - have_oid_t)
            need_oid_v = max(0, args.birds_oid_val - have_oid_v)
            print(
                f"[birds-oid] OID-стиль на диске (hex16 stem): train {have_oid_t}/{args.birds_oid_train}, "
                f"val {have_oid_v}/{args.birds_oid_val}; добор {need_oid_t}/{need_oid_v}",
                flush=True,
            )
            if need_oid_t > 0 or need_oid_v > 0:
                _bootstrap_birds_open_images(
                    root,
                    need_oid_t,
                    need_oid_v,
                    chunk_size=ch,
                    validation_only=args.birds_oid_validation_only,
                )
            else:
                print("[birds-oid] квоты уже выполнены — пропуск OID Bird", flush=True)
    if not args.skip_rodents:
        r_train_img = _binary(root) / "rodent" / "train" / "images"
        r_val_img = _binary(root) / "rodent" / "val" / "images"
        have_rt = _count_jpeg_in_dir(r_train_img)
        have_rv = _count_jpeg_in_dir(r_val_img)
        need_rt = max(0, args.rodent_train - have_rt)
        need_rv = max(0, args.rodent_val - have_rv)
        print(
            f"[rodent] на диске: train JPEG {have_rt}/{args.rodent_train}, "
            f"val JPEG {have_rv}/{args.rodent_val}; добор в этом запуске: {need_rt}/{need_rv}",
            flush=True,
        )
        if need_rt == 0 and need_rv == 0:
            print("[rodent] квоты train/val уже выполнены — загрузка грызунов пропущена", flush=True)
        else:
            _bootstrap_rodents(
                root,
                need_rt,
                need_rv,
                chunk_size=ch,
                rodent_classes=rodent_classes,
                validation_only=args.rodent_validation_only,
            )
    if not args.skip_background:
        if not args.skip_background_soft:
            _collect_no_bird_background(
                root,
                coco_split="train",
                pool=args.background_train_pool,
                target=args.background_train,
                out_tag="train",
                scan_chunk=bg_ch,
            )
            _collect_no_bird_background(
                root,
                coco_split="validation",
                pool=args.background_val_pool,
                target=args.background_val,
                out_tag="val",
                scan_chunk=bg_ch,
            )
        hard_labels = frozenset(
            x.strip().lower() for x in args.background_hard_labels.split(",") if x.strip()
        )
        if (
            not args.skip_background_hard
            and args.background_hard_train > 0
            and hard_labels
        ):
            _collect_hard_negative_background(
                root,
                coco_split="train",
                pool=max(args.background_train_pool, 15000),
                target=args.background_hard_train,
                out_tag="train",
                scan_chunk=bg_ch,
                trigger_labels=hard_labels,
            )
        if (
            not args.skip_background_hard
            and args.background_hard_val > 0
            and hard_labels
        ):
            _collect_hard_negative_background(
                root,
                coco_split="validation",
                pool=max(args.background_val_pool, 8000),
                target=args.background_hard_val,
                out_tag="val",
                scan_chunk=bg_ch,
                trigger_labels=hard_labels,
            )

    print("\nГотово. Дальше из корня репозитория: make dataset-merge-three-class")
    b = _binary(root)
    print(f"Данные: {b}/birds, {b}/rodent, {b}/background")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
