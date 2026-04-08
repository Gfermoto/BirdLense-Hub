#!/usr/bin/env python3
"""Применить полировку порогов + dataset crops к user_config.yaml (в контейнере /app/app_config)."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

TARGET = Path("/app/app_config/user_config.yaml")
BACKUP = TARGET.with_suffix(
    ".yaml.bak_tune_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)

PATCH_PROCESSOR = {
    "min_confidence_binary": 0.30,
    "min_confidence_to_process": 0.40,
    "min_confidence_to_notify": 0.46,
    "min_box_size_px": 78,
    "save_dataset_crops": True,
    "dataset_min_confidence": 0.58,
}
PATCH_DETECTION = {
    "min_confidence_to_store": 0.36,
    "absorb_generic_bird_min_classifier_confidence": 0.24,
}


def main() -> None:
    shutil.copy2(TARGET, BACKUP)
    print("backup", BACKUP, flush=True)
    raw = TARGET.read_text(encoding="utf-8")
    cfg = yaml.safe_load(raw) or {}
    proc = cfg.setdefault("processor", {})
    det = cfg.setdefault("detection", {})
    proc.update(PATCH_PROCESSOR)
    det.update(PATCH_DETECTION)
    TARGET.write_text(
        yaml.safe_dump(
            cfg,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    print("updated", TARGET, flush=True)


if __name__ == "__main__":
    main()
