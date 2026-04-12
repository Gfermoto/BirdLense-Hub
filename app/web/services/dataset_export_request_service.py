"""Разбор query для GET /api/ui/dataset/export (#293)."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_dataset_export_query_args(args) -> dict:
    """Параметры для build_dataset_zip."""
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    only_manually_corrected = args.get("only_manually_corrected", "").lower() in (
        "1",
        "true",
        "yes",
    )
    ready_for_train = args.get("ready_for_train", "").lower() in ("1", "true", "yes")
    strict_quality = args.get("strict_quality", "").lower() in ("1", "true", "yes")
    try:
        val_ratio = float(args.get("val_ratio", "0.2"))
    except (TypeError, ValueError):
        val_ratio = 0.2
    try:
        test_ratio = float(args.get("test_ratio", "0"))
    except (TypeError, ValueError):
        test_ratio = 0.0
    try:
        split_seed = int(args.get("split_seed", "42"))
    except (TypeError, ValueError):
        split_seed = 42
    try:
        min_images_per_class = int(args.get("min_images_per_class", "1"))
    except (TypeError, ValueError):
        min_images_per_class = 1
    return {
        "start_date": start_date,
        "end_date": end_date,
        "only_manually_corrected": only_manually_corrected,
        "ready_for_train": ready_for_train,
        "val_ratio": val_ratio,
        "test_ratio": test_ratio,
        "split_seed": split_seed,
        "min_images_per_class": min_images_per_class,
        "strict_quality": strict_quality,
    }


def dataset_export_zip_filename() -> str:
    return f"birdlense_dataset_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}Z.zip"
