#!/usr/bin/env python3
"""
Сборка YOLO-детекции на три класса: Bird / Rodent / Background (#367 Phase 1).

Ожидаемые входы (типовая цепочка после ``merge_datasets_binary.py`` и
``convert_oidv4_rodent_to_yolo.py``):

- ``binary/birds/`` — один класс bird (id 0), train/val/images + labels;
- ``binary/rodent/`` — Rodent (исторически id 1011 в OID-конвертере);
- ``binary/background/`` — кадры без объектов (пустые ``.txt``) и/или боксы
  background-кропов; любые непустые строки перенумеруются в класс 2.

Имена классов в ``dataset.yaml``: **Bird**, **Rodent**, **Background** —
совместимо с ``normalize_detector_label`` / ``detector_scope`` в Hub.

Пример::

    cd scripts/datasets
    python3 merge_datasets_three_class.py \\
      --birds-dir binary/birds \\
      --rodent-dir binary/rodent \\
      --background-dir binary/background \\
      --output-dir binary/merged

Или: ``make dataset-merge-three-class`` из корня репозитория (пути по умолчанию).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("Need PyYAML: pip install pyyaml") from e


CLASS_BIRD = 0
CLASS_RODENT = 1
CLASS_BACKGROUND = 2


def _image_extensions() -> tuple[str, ...]:
    return (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ".webp", ".WEBP")


def _find_image_for_label(label_file: Path, stem: str) -> Path | None:
    images_dir = label_file.parent.parent / "images"
    for ext in _image_extensions():
        p = images_dir / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


def _remap_lines(raw: str, class_id: int) -> str:
    out_lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        parts[0] = str(class_id)
        out_lines.append(" ".join(parts))
    return "\n".join(out_lines) + ("\n" if out_lines else "")


def _merge_split(
    birds: Path,
    rodent: Path,
    background: Path,
    out_root: Path,
    split: str,
    *,
    prefix_bird: str,
    prefix_rodent: str,
    prefix_bg: str,
) -> dict[str, int]:
    counts = {"bird": 0, "rodent": 0, "background": 0}
    dst_img = out_root / split / "images"
    dst_lbl = out_root / split / "labels"
    dst_img.mkdir(parents=True, exist_ok=True)
    dst_lbl.mkdir(parents=True, exist_ok=True)

    # Birds → class 0
    b_labels = birds / split / "labels"
    b_images = birds / split / "images"
    if b_labels.is_dir():
        for lf in sorted(b_labels.glob("*.txt")):
            stem = lf.stem
            raw = lf.read_text(encoding="utf-8", errors="replace")
            if not raw.strip():
                continue
            img = _find_image_for_label(lf, stem)
            if img is None:
                continue
            body = _remap_lines(raw, CLASS_BIRD)
            name = f"{prefix_bird}{stem}"
            shutil.copy2(img, dst_img / f"{name}{img.suffix}")
            (dst_lbl / f"{name}.txt").write_text(body, encoding="utf-8")
            counts["bird"] += 1

    # Rodent → class 1 (любой прежний class id)
    r_labels = rodent / split / "labels"
    if r_labels.is_dir():
        for lf in sorted(r_labels.glob("*.txt")):
            stem = lf.stem
            raw = lf.read_text(encoding="utf-8", errors="replace")
            if not raw.strip():
                continue
            img = _find_image_for_label(lf, stem)
            if img is None:
                continue
            body = _remap_lines(raw, CLASS_RODENT)
            name = f"{prefix_rodent}{stem}"
            shutil.copy2(img, dst_img / f"{name}{img.suffix}")
            (dst_lbl / f"{name}.txt").write_text(body, encoding="utf-8")
            counts["rodent"] += 1

    # Background: пустые label = чистые негативы; непустые → class 2
    bg_images = background / split / "images"
    bg_labels = background / split / "labels"
    allowed_img_ext = {e.lower() for e in _image_extensions()}
    if bg_images.is_dir():
        for img in sorted(bg_images.iterdir()):
            if not img.is_file() or img.suffix.lower() not in allowed_img_ext:
                continue
            stem = img.stem
            lf = bg_labels / f"{stem}.txt"
            if lf.is_file():
                raw = lf.read_text(encoding="utf-8", errors="replace")
                body = _remap_lines(raw, CLASS_BACKGROUND)
            else:
                body = ""
            name = f"{prefix_bg}{stem}"
            shutil.copy2(img, dst_img / f"{name}{img.suffix}")
            (dst_lbl / f"{name}.txt").write_text(body, encoding="utf-8")
            counts["background"] += 1

    return counts


def _write_manifest(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--birds-dir",
        type=Path,
        default=Path("binary/birds"),
        help="Выход merge_datasets_binary (binary bird)",
    )
    ap.add_argument(
        "--rodent-dir",
        type=Path,
        default=Path("binary/rodent"),
        help="Выход convert_oidv4_rodent_to_yolo",
    )
    ap.add_argument(
        "--background-dir",
        type=Path,
        default=Path("binary/background"),
        help="Каталог с train|val/images (+ опционально labels)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("binary/merged"),
        help="Куда слить три класса",
    )
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Опционально: записать manifest слияния (paths + счётчики)",
    )
    args = ap.parse_args()

    birds = args.birds_dir.resolve()
    rodent = args.rodent_dir.resolve()
    background = args.background_dir.resolve()
    out_root = args.output_dir.resolve()

    missing = [p for p in (birds, rodent, background) if not p.is_dir()]
    if missing:
        print("Missing directories:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 2

    splits = []
    for sp in ("train", "val", "test"):
        if (birds / sp / "images").is_dir() or (birds / sp / "labels").is_dir():
            splits.append(sp)

    if not splits:
        print(f"No train/val splits under {birds}", file=sys.stderr)
        return 2

    totals: dict[str, int] = {"bird": 0, "rodent": 0, "background": 0}
    per_split: dict[str, dict[str, int]] = {}

    for split in splits:
        c = _merge_split(
            birds,
            rodent,
            background,
            out_root,
            split,
            prefix_bird="b_",
            prefix_rodent="r_",
            prefix_bg="g_",
        )
        per_split[split] = c
        for k in totals:
            totals[k] += c[k]

    names = {
        CLASS_BIRD: "Bird",
        CLASS_RODENT: "Rodent",
        CLASS_BACKGROUND: "Background",
    }
    # Ultralytics без ключа path: корень = каталог с yaml (переносимый ZIP/Drive).
    yolo_yaml: dict[str, Any] = {
        "train": "train/images",
        "val": "val/images",
        "names": names,
    }
    if (out_root / "test" / "images").is_dir():
        yolo_yaml["test"] = "test/images"
    yaml_path = out_root / "dataset.yaml"
    yaml_path.write_text(
        yaml.dump(yolo_yaml, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    print("Merged 3-class YOLO dataset:")
    for split, c in per_split.items():
        print(f"  [{split}] bird={c['bird']} rodent={c['rodent']} bg={c['background']}")
    print(f"  TOTAL bird={totals['bird']} rodent={totals['rodent']} bg={totals['background']}")
    print(f"  dataset.yaml -> {yaml_path}")

    if args.manifest_out:
        manifest = {
            "schema": "merge_datasets_three_class_manifest@v1",
            "birds_dir": str(birds),
            "rodent_dir": str(rodent),
            "background_dir": str(background),
            "output_dir": str(out_root),
            "per_split": per_split,
            "totals": totals,
            "class_names": names,
        }
        _write_manifest(args.manifest_out.resolve(), manifest)
        print(f"  manifest -> {args.manifest_out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
