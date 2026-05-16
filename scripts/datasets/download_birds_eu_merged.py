#!/usr/bin/env python3
# flake8: noqa
"""
Скачать готовый EU-merge классификатор птиц с Hugging Face (BirdLense).

Репозиторий: gfermoto/birds-eu-merged — ~490 видов, формат Scientific (Common),
источники birds-525 + iNaturalist Europe. Лицензия см. карточку датасета.

После распаковки опционально приводит имена папок к безопасному виду (to_folder_name),
сливая коллизии.

  pip install huggingface_hub
  python3 scripts/datasets/download_birds_eu_merged.py \\
    --output datasets/new/classifier/yolo_cls_eu_hf
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts" / "datasets") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "datasets"))

from species_format import to_folder_name  # noqa: E402

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    raise SystemExit("pip install huggingface_hub")


def _move_split_contents(src_split: Path, dst_split: Path) -> None:
    if not src_split.is_dir():
        return
    dst_split.mkdir(parents=True, exist_ok=True)
    for item in src_split.iterdir():
        dest = dst_split / item.name
        if dest.exists() and item.is_dir():
            for f in item.iterdir():
                shutil.move(str(f), str(dest / f.name))
            try:
                item.rmdir()
            except OSError:
                pass
        else:
            shutil.move(str(item), str(dest))


def _sanitize_split(split_dir: Path) -> None:
    """Переименовать подпапки классов в to_folder_name; слить дубликаты цели."""
    if not split_dir.is_dir():
        return
    buckets: dict[str, list[Path]] = {}
    for d in sorted(split_dir.iterdir(), key=lambda p: p.name):
        if not d.is_dir():
            continue
        tgt = to_folder_name(d.name)
        buckets.setdefault(tgt, []).append(d)

    for tgt_name, dirs in buckets.items():
        final_dir = split_dir / tgt_name
        final_dir.mkdir(parents=True, exist_ok=True)
        if len(dirs) == 1 and dirs[0].name == tgt_name:
            continue
        for d in dirs:
            if d.resolve() == final_dir.resolve():
                continue
            for p in list(d.iterdir()):
                if not p.is_file():
                    continue
                dest = final_dir / p.name
                if dest.exists():
                    dest = final_dir / f"{p.stem}_{hash(p) & 0xFFFFFFFF:x}{p.suffix}"
                shutil.move(str(p), str(dest))
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass


def download_and_extract(
    output: Path,
    repo_id: str,
    zip_name: str,
    sanitize: bool,
) -> dict[str, object]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    zip_path = Path(
        hf_hub_download(repo_id=repo_id, filename=zip_name, repo_type="dataset")
    )

    with tempfile.TemporaryDirectory(prefix="birds_eu_zip_") as td:
        staging = Path(td)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(staging)

        inner = staging / "datasets" / "merged_cls"
        if not inner.is_dir():
            raise SystemExit(f"Unexpected zip layout: missing {inner}")

        for split in ("train", "val", "test"):
            src_sp = inner / split
            dst_sp = output / split
            if src_sp.is_dir():
                _move_split_contents(src_sp, dst_sp)

    if sanitize:
        for split in ("train", "val", "test"):
            _sanitize_split(output / split)

    # счётчики
    stats: dict[str, object] = {"output": str(output), "repo_id": repo_id}
    for split in ("train", "val", "test"):
        sp = output / split
        if not sp.is_dir():
            stats[f"{split}_classes"] = 0
            stats[f"{split}_images"] = 0
            continue
        classes = [p for p in sp.iterdir() if p.is_dir()]
        n_img = sum(
            1
            for c in classes
            for f in c.iterdir()
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        stats[f"{split}_classes"] = len(classes)
        stats[f"{split}_images"] = n_img
    all_cls = set()
    for split in ("train", "val", "test"):
        sp = output / split
        if sp.is_dir():
            all_cls.update(p.name for p in sp.iterdir() if p.is_dir())
    stats["classes_union"] = len(all_cls)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True, help="Корень YOLO cls (train/val)")
    ap.add_argument("--repo-id", default="gfermoto/birds-eu-merged")
    ap.add_argument("--zip-name", default="merged_cls.zip")
    ap.add_argument("--no-sanitize", action="store_true", help="Не переименовывать папки")
    args = ap.parse_args()

    stats = download_and_extract(
        args.output,
        args.repo_id,
        args.zip_name,
        sanitize=not args.no_sanitize,
    )
    import json

    print(json.dumps({"ok": True, **stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
