"""Переобучение behavior baseline из ручных меток в БД (UI, без CLI, #416)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import joinedload

from models import Video, VideoSpecies, db

_log = logging.getLogger(__name__)


def processor_root() -> Path:
    """Каталог ``/app/processor`` в образе или ``<repo>/app/processor`` локально."""
    explicit = (os.environ.get("BIRDLENSE_PROCESSOR_ROOT") or "").strip()
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            return p.resolve()
    for cand in (Path("/app/processor"), Path(__file__).resolve().parents[2] / "processor"):
        if cand.is_dir():
            return cand.resolve()
    raise RuntimeError("processor_root_not_found")


def resolve_behavior_export_write_path() -> Path:
    """Путь записи JSON весов (совпадает с default_config ``models/behavior/...``)."""
    return processor_root() / "models" / "behavior" / "behavior_logistic_export@v1.json"


def _video_duration_s(video: Video) -> float:
    try:
        return max(0.0, (video.end_time - video.start_time).total_seconds())
    except (TypeError, AttributeError):
        return 0.0


def _video_species_to_runtime_detections(video: Video) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for vs in getattr(video, "video_species", []) or []:
        frames_payload: Any = []
        raw = getattr(vs, "frames", None)
        if raw:
            try:
                frames_payload = json.loads(raw)
            except (TypeError, ValueError):
                frames_payload = []
        if not isinstance(frames_payload, list):
            frames_payload = []
        name = ""
        sp = getattr(vs, "species", None)
        if sp is not None:
            name = str(getattr(sp, "name", "") or "").strip()
        out.append({"species_name": name, "frames": frames_payload})
    return out


def collect_labeled_hub_rows(*, max_videos: int = 2000) -> tuple[list[list[float]], list[str]]:
    """Вернуть (features, labels) для роликов с непустым ``behavior_label`` (не удалённые)."""
    from behavior_baseline_runtime import runtime_meta_features

    q = (
        db.session.query(Video)
        .options(joinedload(Video.video_species).joinedload(VideoSpecies.species))
        .filter(Video.deleted_at.is_(None))
        .filter(Video.behavior_label.isnot(None))
        .order_by(Video.id.desc())
        .limit(int(max_videos))
    )

    X_list: list[list[float]] = []
    y_list: list[str] = []
    for v in q:
        lab = str(v.behavior_label or "").strip().lower()
        if not lab:
            continue
        dets = _video_species_to_runtime_detections(v)
        dur = _video_duration_s(v)
        xf = runtime_meta_features(dets, duration_s=dur)
        X_list.append(xf)
        y_list.append(lab)
    return X_list, y_list


def run_behavior_baseline_retrain_from_hub(
    *,
    max_iter: int = 500,
    seed: int = 42,
    max_videos: int = 2000,
) -> dict[str, Any]:
    """Собрать данные, обучить, записать JSON. При ошибке — ValueError / RuntimeError."""
    from shared.behavior_logistic_train import EXPORT_SCHEMA, fit_behavior_logistic_export

    X_list, y_list = collect_labeled_hub_rows(max_videos=max_videos)
    if len(X_list) < 4:
        raise ValueError(
            f"need at least 4 videos with non-empty behavior_label, got {len(X_list)}",
        )
    if len(set(y_list)) < 2:
        raise ValueError("need at least 2 distinct behavior_label values among labeled videos")

    extra = {
        "training_source": "ui_hub_retrain",
        "n_training_videos": len(X_list),
        "distinct_labels": sorted(set(y_list)),
    }
    export, _clf = fit_behavior_logistic_export(
        X_list,
        y_list,
        max_iter=max_iter,
        seed=seed,
        feature_mode="runtime_meta_v1",
        extra=extra,
    )
    if str(export.get("schema") or "") != EXPORT_SCHEMA:
        raise RuntimeError("internal_export_schema_mismatch")

    out_path = resolve_behavior_export_write_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info("behavior baseline retrain wrote %s (%s rows)", out_path, len(X_list))

    return {
        "ok": True,
        "export_path": str(out_path),
        "n_training_videos": len(X_list),
        "labels": list(export.get("labels") or []),
        "generated_at": export.get("generated_at") or datetime.now(timezone.utc).isoformat(),
    }
