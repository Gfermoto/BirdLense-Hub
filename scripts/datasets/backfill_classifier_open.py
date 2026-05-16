#!/usr/bin/env python3
"""
Добор размеченных кадров для «тонких» классов через iNaturalist (research-grade), без урезания других классов.

Идея: поднять счётчик изображений до --target за счёт открытых наблюдений, затем слить staging вторым входом в merge_classification_datasets.py и снова refine.

  python3 scripts/datasets/backfill_classifier_open.py \\
    --root datasets/new/classifier/yolo_cls_eu_merged \\
    --staging datasets/new/classifier/raw/inat_backfill \\
    --target 120 --dry-run

  # затем:
  python3 scripts/datasets/merge_classification_datasets.py \\
    --inputs datasets/new/classifier/yolo_cls_eu_merged \\
             datasets/new/classifier/raw/inat_backfill \\
    --output datasets/new/classifier/yolo_cls_eu_merged_plus \\
    --symlink --val-ratio 0.2

Имя вида для поиска taxon_id берётся из имени папки класса (формат Scientific_(Common) после refine).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_SCRIPTS = REPO_ROOT / "scripts" / "datasets"
if str(DATASETS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DATASETS_SCRIPTS))

from download_inaturalist import (  # noqa: E402
    EUROPE_PLACE_ID,
    RATE_LIMIT,
    download_inaturalist_cls_layer,
)
from report_classifier_class_counts import collect_counts  # noqa: E402

TAXA_API = "https://api.inaturalist.org/v1/taxa"


def folder_to_scientific(folder: str) -> str:
    m = re.match(r"^(.+)_\((.+)\)$", folder)
    if m:
        return m.group(1).replace("_", " ").strip()
    return folder.replace("_", " ").strip()


def resolve_taxon_id(scientific_name: str, rate_limit: float = RATE_LIMIT) -> int | None:
    time.sleep(rate_limit)
    r = requests.get(
        TAXA_API,
        params={"q": scientific_name, "rank": "species", "per_page": 20},
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    want = scientific_name.lower().strip()
    for t in results:
        if (t.get("name") or "").lower() == want:
            return int(t["id"])
    if results:
        return int(results[0]["id"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True, help="Текущий yolo_cls с train/val[/test]")
    ap.add_argument("--staging", type=Path, required=True, help="Куда писать только добор (новый слой)")
    ap.add_argument("--target", type=int, default=100, help="Цель суммарных изображений на класс")
    ap.add_argument(
        "--max-obs-per-class",
        type=int,
        default=500,
        help="Максимум наблюдений API на один вид за проход (есть несколько фото на obs)",
    )
    ap.add_argument(
        "--place-mode",
        choices=("europe", "global"),
        default="global",
        help="europe=place_id EU; global=весь мир (обычно больше кадров для редких видов)",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-json", type=Path, default=None)
    args = ap.parse_args()

    root = args.root.resolve()
    staging = args.staging.resolve()
    place_id = EUROPE_PLACE_ID if args.place_mode == "europe" else None

    counts_map = collect_counts(root)
    totals = {k: v["total"] for k, v in counts_map.items()}
    rare = [(name, n) for name, n in sorted(totals.items(), key=lambda x: (x[1], x[0])) if n < args.target]

    report: dict = {
        "root": str(root),
        "staging": str(staging),
        "target": args.target,
        "place_mode": args.place_mode,
        "rare_classes": len(rare),
        "runs": [],
    }

    if not rare:
        print(json.dumps({"ok": True, "msg": "all classes >= target", **report}, ensure_ascii=False, indent=2))
        return 0

    staging.mkdir(parents=True, exist_ok=True)
    (staging / "train").mkdir(parents=True, exist_ok=True)
    (staging / "val").mkdir(parents=True, exist_ok=True)

    for folder_name, total in rare:
        need = args.target - total
        sci = folder_to_scientific(folder_name)
        tid = resolve_taxon_id(sci)
        if tid is None:
            report["runs"].append(
                {"folder": folder_name, "scientific": sci, "error": "taxon_not_found", "had": total}
            )
            print(f"[skip] no taxon: {folder_name!r} ({sci})")
            continue

        # наблюдений берём с запасом: у части obs нет фото или битые URL
        max_obs = min(args.max_obs_per_class, max(40, need * 6))

        run_rec = {
            "folder": folder_name,
            "scientific": sci,
            "taxon_id": tid,
            "had": total,
            "need": need,
            "max_observations": max_obs,
        }

        if args.dry_run:
            print(f"[dry-run] {folder_name}: taxon={tid} max_obs={max_obs} ({sci})")
            report["runs"].append({**run_rec, "dry_run": True})
            continue

        stats = download_inaturalist_cls_layer(
            staging,
            query_taxon_id=tid,
            place_id=place_id,
            max_observations=max_obs,
            val_ratio=0.2,
            photo_size="medium",
            seed=args.seed,
        )
        run_rec.update(stats)
        report["runs"].append(run_rec)
        print(f"[ok] {folder_name}: taxon={tid} obs={stats['observations']} imgs={stats['images_written']}")

    report["ok"] = True
    out_json = json.dumps(report, ensure_ascii=False, indent=2)
    print(out_json)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(out_json, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
