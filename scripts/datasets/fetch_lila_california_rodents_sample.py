#!/usr/bin/env python3
"""
Выборочная подтяжка **California Small Animals** (LILA, CC-BY 4.0) → ``binary/rodent``.

1) Качает метадату ``california_small_animals_with_sequences.zip`` с Azure  
   (можно указать уже скачанный файл --metadata-zip).
2) Находит COCO‑подобный JSON, отбирает кадры, где есть боксы по категориям «грызуно‑подобным»
   (подстрочное совпадение по имени категории).
3) Скачивает только выбранные изображения по HTTPS с blob Azure.
4) Пишет урезанный COCO JSON и вызывает ``import_coco_rodents_to_binary``.

Датасет: https://lila.science/datasets/california-small-animals/
Камеры Reconyx, много мелких млекопитающих; не все кадры ночные, но это типичный **camera trap**.

Запуск из корня репозитория (нужна сеть и ~несколько ГБ места под выборку)::

    python3 scripts/datasets/fetch_lila_california_rodents_sample.py \\
      --root datasets/new/detector --max-images 2000

Переменные: см. argparse (--keywords, лимиты).

После успеха: ``make dataset-merge-three-class``.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_META_URL = (
    "https://lilawildlife.blob.core.windows.net/"
    "lila-wildlife/california-small-animals/california_small_animals_with_sequences.zip"
)
IMAGE_BASE = (
    "https://lilawildlife.blob.core.windows.net/lila-wildlife/california-small-animals/"
)
DEFAULT_KW = (
    "mouse,mice,rat,rats,rodent,arvicolinae,vole,voles,squirrel,chipmunk,"
    "marmot,pika,gopher,hamster,porcupine,rabbit,hare,bunny,lagomorph,shrew"
)


def _find_coco_like_json(search_root: Path) -> Path | None:
    candidates: list[Path] = []
    for p in search_root.rglob("*.json"):
        if p.stat().st_size < 500:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        if '"categories"' in head and '"images"' in head:
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
    return candidates[0]


def _filter_rodent_subset(
    data: dict,
    keywords: list[str],
    max_images: int,
    rng: random.Random,
) -> dict:
    cats = data.get("categories", [])
    by_id = {int(c["id"]): str(c.get("name", "") or "") for c in cats}
    kws = [k.lower() for k in keywords]
    rod_ids = {
        cid
        for cid, nm in by_id.items()
        if nm and any(kw in nm.lower() for kw in kws)
    }
    if not rod_ids:
        raise ValueError(f"никакая категория не попала под keywords (пример имён): {list(by_id.values())[:25]}")

    anns_keep: list[dict] = []
    img_hit: dict[int, list[dict]] = {}
    for ann in data.get("annotations", []):
        if ann.get("iscrowd", 0):
            continue
        if int(ann.get("category_id", -1)) not in rod_ids:
            continue
        bbox = ann.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        iid = int(ann["image_id"])
        anns_keep.append(ann)
        img_hit.setdefault(iid, []).append(ann)

    ids_order = list(img_hit.keys())
    rng.shuffle(ids_order)
    picked: set[int] = set(ids_order[: max_images if max_images > 0 else len(ids_order)])
    anns_f = [a for a in anns_keep if int(a["image_id"]) in picked]
    images_f = [im for im in data.get("images", []) if int(im["id"]) in picked]

    subset = {
        "info": data.get("info", {}),
        "licenses": data.get("licenses", []),
        "categories": [c for c in cats if int(c["id"]) in rod_ids],
        "images": images_f,
        "annotations": anns_f,
    }
    return subset


def _http_download(url: str, dest: Path, *, retries: int = 4, timeout: float = 120.0) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    delay = 1.5
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BirdLense-lila-fetch/1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                return False
            dest.write_bytes(data)
            return True
        except (urllib.error.URLError, OSError):
            if attempt + 1 >= retries:
                return False
            time.sleep(delay)
            delay = min(delay * 1.7, 45.0)
    return False


def _blob_url(rel_path: str) -> str:
    rel_posix = Path(rel_path).as_posix()
    q = urllib.parse.quote(rel_posix, safe="/")
    return IMAGE_BASE + q


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="…/datasets/new/detector")
    ap.add_argument("--max-images", type=int, default=2000)
    ap.add_argument(
        "--metadata-zip",
        type=Path,
        default=None,
        help="Локальный zip метадаты (не качать)",
    )
    ap.add_argument(
        "--metadata-url",
        type=str,
        default=DEFAULT_META_URL,
        help="URL zip метадаты",
    )
    ap.add_argument("--keywords", type=str, default=DEFAULT_KW)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--skip-download-images",
        action="store_true",
        help="Только распаковать/проанализировать/записать subset JSON без картинок",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    work = root / "raw" / "lila" / "california_small_animals"
    work.mkdir(parents=True, exist_ok=True)
    zpath = args.metadata_zip
    if zpath is None:
        zpath = work / "california_small_animals_with_sequences.zip"
        if not zpath.is_file() and not args.dry_run:
            print(f"[lila-ca] загрузка метадаты → {zpath} …", flush=True)
            if not _http_download(args.metadata_url, zpath, retries=8, timeout=180.0):
                print(
                    "[lila-ca] не удалось скачать метадату (сеть?). "
                    "Скачайте zip вручную и передайте --metadata-zip",
                    file=sys.stderr,
                )
                return 2
        elif args.dry_run and not zpath.is_file():
            print("[lila-ca] dry-run без локального zip — нечего делать")
            return 2
    elif not Path(zpath).is_file():
        print(f"[lila-ca] нет файла {zpath}", file=sys.stderr)
        return 2
    zpath = zpath.resolve()

    extract_dir = work / "_meta_unpacked"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    print(f"[lila-ca] распаковка {zpath.name} …", flush=True)
    with zipfile.ZipFile(zpath, "r") as zf:
        zf.extractall(extract_dir)

    coco_json = _find_coco_like_json(extract_dir)
    if coco_json is None:
        print("[lila-ca] не найден COCO‑JSON в архиве метадаты", file=sys.stderr)
        return 3
    print(f"[lila-ca] JSON: {coco_json}", flush=True)

    raw = json.loads(coco_json.read_text(encoding="utf-8"))
    kws = [x.strip() for x in args.keywords.split(",") if x.strip()]
    rng = random.Random(args.seed)
    subset = _filter_rodent_subset(raw, kws, args.max_images, rng)
    n_im = len(subset["images"])
    n_ann = len(subset["annotations"])
    snames = sorted({str(c["name"]) for c in subset["categories"]})
    print(
        f"[lila-ca] подмножество: images={n_im} annotations={n_ann} классы({len(snames)}): "
        f"{snames[:20]}{'…' if len(snames)>20 else ''}",
        flush=True,
    )

    sub_path = work / "coco_rodent_subset.json"
    sub_path.write_text(json.dumps(subset, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        print(f"[lila-ca] dry-run OK; запись {sub_path}", flush=True)
        return 0

    imgs_root = work / "images"
    if imgs_root.exists():
        shutil.rmtree(imgs_root)
    imgs_root.mkdir(parents=True)

    if args.skip_download_images:
        print(
            f"[lila-ca] subset JSON: {sub_path}\n"
            "Изображения — AzCopy/gcs/aws см. https://lila.science/image-access ,\n"
            "потом импорт: python3 scripts/datasets/import_coco_rodents_to_binary.py "
            f"--root {root} --coco-json {sub_path} --images-dir {imgs_root} "
            "--split train --max-images 0 --prefix licamsa_",
            flush=True,
        )
        return 0

    ok = fail = 0
    for i, im in enumerate(subset["images"], 1):
        fn = str(im.get("file_name", "") or "").strip()
        if not fn:
            fail += 1
            continue
        dst = imgs_root / fn
        url = _blob_url(fn)
        if dst.is_file():
            ok += 1
            continue
        if _http_download(url, dst):
            ok += 1
        else:
            fail += 1
        if i % 100 == 0:
            print(f"[lila-ca] загрузка {i}/{n_im} ok={ok} fail={fail}", flush=True)

    print(f"[lila-ca] изображения готово: ok={ok} fail={fail} → {imgs_root}", flush=True)

    imp = Path(__file__).resolve().parent / "import_coco_rodents_to_binary.py"
    cmd = [
        sys.executable,
        str(imp),
        "--root",
        str(root),
        "--coco-json",
        str(sub_path),
        "--images-dir",
        str(imgs_root),
        "--split",
        "train",
        "--max-images",
        "0",
        "--seed",
        str(args.seed),
        "--prefix",
        "licamsa_",
    ]
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc
    print("[lila-ca] готово. Дальше: make dataset-merge-three-class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
