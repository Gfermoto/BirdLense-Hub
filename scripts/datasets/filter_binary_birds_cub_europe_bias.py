#!/usr/bin/env python3
"""Опциональная нарезка CUB-200 VOC в ``binary/birds`` или откат из карантина.

**Обычный смысл:** для детектора одного класса «bird» оставить почти весь CUB;
в карантин — только явную экзотику (колибри, дальний океан, тропики) —
``--quarantine-blocklist``. Старый жёсткий EU-режим по allowlist сохранён для
совместимости (без blocklist всё работает как раньше).

Кормушка ``rfbf_*`` и грызуны не трогаются.

Вернуть из карантина::

  python3 filter_binary_birds_cub_europe_bias.py \\
    --root datasets/new/detector \\
    --restore-from binary/_quarantine/birds_cub_exotic_…

Экзотика (dry-run → execute)::

  python3 … --root datasets/new/detector --quarantine-blocklist
  python3 … --root datasets/new/detector --quarantine-blocklist --execute
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_STEM_RE = re.compile(r"^cub_(.+)_(\d{4})_(\d+)$", re.IGNORECASE)


def _allowlist_path() -> Path:
    return Path(__file__).resolve().parent / "cub200_europe_holarctic_allowlist.txt"


def _default_exotic_blocklist_path() -> Path:
    return Path(__file__).resolve().parent / "cub200_exotic_blocklist_feeder_eu.txt"


def load_species_lines_file(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.casefold())
    if not out:
        raise SystemExit(f"пустой список видов: {path}")
    return out


def species_key_from_cub_stem(stem: str) -> str | None:
    m = _STEM_RE.match(stem)
    if not m:
        return None
    return m.group(1).casefold()


@dataclass(frozen=True)
class Pair:
    split: str
    img: Path
    lbl: Path
    stem: str
    species_key: str


def collect_cub_pairs(birds_root: Path) -> list[Pair]:
    out: list[Pair] = []
    for sp in ("train", "val", "test"):
        img_dir = birds_root / sp / "images"
        lab_dir = birds_root / sp / "labels"
        if not img_dir.is_dir() or not lab_dir.is_dir():
            continue
        for img in img_dir.iterdir():
            if not img.is_file():
                continue
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            st = img.stem
            if not st.startswith("cub_"):
                continue
            sk = species_key_from_cub_stem(st)
            if sk is None:
                continue
            lbl = lab_dir / f"{st}.txt"
            if lbl.is_file():
                out.append(Pair(split=sp, img=img, lbl=lbl, stem=st, species_key=sk))
    return out


def restore_cub_from_quarantine(quarantine_root: Path, birds_root: Path) -> dict[str, int]:
    """Перенос пар image+label из дерева карантина обратно в ``birds_root``."""
    moved = skipped = missing_lbl = 0
    quarantine_root = quarantine_root.resolve()
    birds_root = birds_root.resolve()
    if not quarantine_root.is_dir():
        raise SystemExit(f"нет карантина: {quarantine_root}")
    for sp in ("train", "val", "test"):
        qi = quarantine_root / sp / "images"
        ql = quarantine_root / sp / "labels"
        if not qi.is_dir():
            continue
        for img in qi.iterdir():
            if not img.is_file():
                continue
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            dst_img = birds_root / sp / "images" / img.name
            dst_lbl = birds_root / sp / "labels" / f"{img.stem}.txt"
            src_lbl = ql / f"{img.stem}.txt"
            if dst_img.is_file() and dst_lbl.is_file():
                skipped += 1
                continue
            if dst_img.is_file() or dst_lbl.is_file():
                skipped += 1
                continue
            if not src_lbl.is_file():
                missing_lbl += 1
                continue
            dst_img.parent.mkdir(parents=True, exist_ok=True)
            dst_lbl.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(img), str(dst_img))
            shutil.move(str(src_lbl), str(dst_lbl))
            moved += 1
    return {"moved_pairs": moved, "skipped_collision": skipped, "missing_label": missing_lbl}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="…/detector (родитель binary/birds)")
    ap.add_argument(
        "--restore-from",
        type=Path,
        default=None,
        metavar="DIR",
        help="Каталог binary/_quarantine/birds_cub_NA_* — вернуть CUB в binary/birds",
    )
    ap.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="EU allowlist UTF-8 (по умолчанию cub200_europe_holarctic_allowlist.txt)",
    )
    ap.add_argument(
        "--quarantine-blocklist",
        nargs="?",
        const=_default_exotic_blocklist_path(),
        default=None,
        type=Path,
        metavar="PATH",
        help="Режим: убрать в карантин только виды из blocklist "
        "(путь по умолчанию — cub200_exotic_blocklist_feeder_eu.txt)",
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Перенести удаляемые пары в binary/_quarantine/… иначе только JSON-сводка",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    birds = root / "binary" / "birds"
    if not birds.is_dir():
        raise SystemExit(f"нет каталога {birds}")

    if args.restore_from is not None:
        stats = restore_cub_from_quarantine(args.restore_from, birds)
        print(json.dumps({"restored_from": str(args.restore_from.resolve()), **stats}, ensure_ascii=False))
        print(f"[ok] restore: {stats['moved_pairs']} пар", flush=True)
        return 0

    pairs = collect_cub_pairs(birds)
    strategy: str
    filter_path: Path

    if args.quarantine_blocklist is not None:
        strategy = "blocklist_exotic"
        filter_path = args.quarantine_blocklist.resolve()
        blocked = load_species_lines_file(filter_path)
        removed = [p for p in pairs if p.species_key in blocked]
        kept = [p for p in pairs if p.species_key not in blocked]
    else:
        strategy = "allowlist_eu"
        filter_path = (args.allowlist or _allowlist_path()).resolve()
        allowed = load_species_lines_file(filter_path)
        kept = [p for p in pairs if p.species_key in allowed]
        removed = [p for p in pairs if p.species_key not in allowed]

    by_sp_removed: dict[str, int] = {}
    by_sp_kept: dict[str, int] = {}
    for p in removed:
        by_sp_removed[p.species_key] = by_sp_removed.get(p.species_key, 0) + 1
    for p in kept:
        by_sp_kept[p.species_key] = by_sp_kept.get(p.species_key, 0) + 1

    summary = {
        "root": str(root),
        "strategy": strategy,
        "filter_list": str(filter_path),
        "cub_pairs_total": len(pairs),
        "kept": len(kept),
        "removed": len(removed),
        "species_kept": len(by_sp_kept),
        "species_removed": len(by_sp_removed),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.execute:
        print(
            "\nDry-run. Для переноса «лишнего» CUB в карантин добавьте --execute.",
            flush=True,
        )
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    qname = "birds_cub_exotic" if strategy == "blocklist_exotic" else "birds_cub_NA"
    quarantine = root / "binary" / "_quarantine" / f"{qname}_{ts}"
    for sp in ("train", "val", "test"):
        (quarantine / sp / "images").mkdir(parents=True, exist_ok=True)
        (quarantine / sp / "labels").mkdir(parents=True, exist_ok=True)

    for p in removed:
        q_img = quarantine / p.split / "images" / p.img.name
        q_lbl = quarantine / p.split / "labels" / p.lbl.name
        q_img.parent.mkdir(parents=True, exist_ok=True)
        q_lbl.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p.img), str(q_img))
        shutil.move(str(p.lbl), str(q_lbl))

    manifest = quarantine / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "summary": summary,
                "removed_top_species": dict(
                    sorted(by_sp_removed.items(), key=lambda kv: kv[1], reverse=True)[:40]
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[ok] карантин: {quarantine}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
