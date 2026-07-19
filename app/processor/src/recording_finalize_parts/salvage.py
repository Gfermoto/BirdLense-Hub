from __future__ import annotations

from typing import Any


from track_first_contract import valid_track_frames


def _weak_yolo_salvage_row_from_track(
    track_id: Any,
    track: dict[str, Any],
    *,
    max_det_conf: float,
) -> dict[str, Any]:
    detector_events = list(track.get("detector_events") or [])
    detector_label = "Bird"
    if detector_events:
        detector_label = str(detector_events[-1].get("label") or detector_label).strip() or "Bird"
    species_name = detector_label if detector_label in {"Bird", "Rodent", "Animal"} else "Bird"
    return {
        "track_id": int(track_id) if str(track_id).lstrip("-").isdigit() else -9999,
        "accepted": True,
        "visit_eligible": False,
        "notification_eligible": False,
        "species_name": species_name,
        "species": species_name,
        "confidence": float(max_det_conf),
        "start_time": float(track.get("start_time") or 0.0),
        "end_time": float(track.get("end_time") or 0.0),
        "detection_provider": "yolo",
        "detector_confidence": float(max_det_conf),
        "classifier_confidence": None,
        "decision_reason": "review_only_weak_yolo_salvage",
        "decision_kind": "review_only_generic",
        "outcome_bucket": "review_only",
        "source": "video",
        "frames": list(track.get("frames") or []),
        "best_frame": track.get("best_frame"),
        "best_frame_score": float(track.get("best_frame_score") or 0.0),
        "yolo_weak_track_salvage": True,
    }


def _build_weak_yolo_salvage_row(
    tracks: dict[str, Any] | dict[int, Any],
    *,
    min_confidence: float = 0.10,
) -> dict[str, Any] | None:
    rows = _build_weak_yolo_salvage_rows(tracks, min_confidence=min_confidence, max_rows=1)
    return rows[0] if rows else None


def _build_weak_yolo_salvage_rows(
    tracks: dict[str, Any] | dict[int, Any],
    *,
    min_confidence: float = 0.10,
    max_rows: int = 5,
) -> list[dict[str, Any]]:
    scored: list[tuple[float, Any, dict[str, Any], float]] = []
    for track_id, track in (tracks or {}).items():
        frames = list(track.get("frames") or [])
        if not valid_track_frames(frames):
            continue
        detector_events = list(track.get("detector_events") or [])
        max_det_conf = max((float(ev.get("confidence") or 0.0) for ev in detector_events), default=0.0)
        if max_det_conf < float(min_confidence):
            continue
        try:
            duration = max(0.0, float(track.get("end_time") or 0.0) - float(track.get("start_time") or 0.0))
        except (TypeError, ValueError):
            duration = 0.0
        score = float(len(frames)) + duration * 5.0 + max_det_conf * 3.0
        scored.append((score, track_id, track, max_det_conf))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    limit = max(1, int(max_rows))
    return [
        _weak_yolo_salvage_row_from_track(track_id, track, max_det_conf=max_det_conf)
        for _, track_id, track, max_det_conf in scored[:limit]
    ]


def _pick_frigate_evidence_for_salvage(
    mqtt_events: list[dict[str, Any]],
    *,
    frigate_trigger_event: dict[str, Any] | None,
    session_camera_id: str | None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    if isinstance(frigate_trigger_event, dict) and frigate_trigger_event:
        candidates.append(frigate_trigger_event)
    cam_key = str(session_camera_id or "").strip().lower()
    for ev in mqtt_events or []:
        if str((ev or {}).get("source") or "").strip().lower() != "frigate":
            continue
        if cam_key:
            ev_cam = str((ev or {}).get("camera") or "").strip().lower()
            if ev_cam and ev_cam != cam_key:
                continue
        candidates.append(ev)
    if not candidates:
        return None

    def _score(ev: dict[str, Any]) -> tuple[float, float]:
        snapshot = 1.0 if bool(ev.get("_session_trigger_snapshot")) else 0.0
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return snapshot, conf

    return max(candidates, key=_score)


def _build_frigate_trigger_review_salvage_row(
    ev: dict[str, Any],
    *,
    duration_s: float,
    app_config,
    camera_id: str | None = None,
) -> dict[str, Any]:
    from detection_fusion import _species_mapping
    from species_normalizer import normalize
    from visit_contract import frigate_species_authority, is_named_product_species

    species_mapping = _species_mapping(app_config)
    raw = ev.get("species") or ev.get("sub_label") or ev.get("label") or ""
    species = normalize(str(raw), species_mapping) if str(raw).strip() else ""
    if not species or species.lower() == "unknown":
        species = str(raw).strip() or "Unidentified"
    try:
        conf = float(ev.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf <= 0.0:
        try:
            conf = float(app_config.get("detection.frigate_standalone_missing_score_fallback") or 0.72)
        except (TypeError, ValueError):
            conf = 0.72
    birder_unknown = str(app_config.get("processor.birder_eu_unknown_label") or "Unknown Bird")
    named = is_named_product_species(species, birder_unknown_label=birder_unknown)
    row = {
        "track_id": -9001,
        "accepted": True,
        "visit_eligible": False,
        "notification_eligible": False,
        "species_name": species,
        "species": species,
        "confidence": max(0.0, min(1.0, conf)),
        "start_time": 0.0,
        "end_time": max(0.0, float(duration_s)),
        "detection_provider": "frigate",
        "detector_confidence": max(0.0, min(1.0, conf)),
        "classifier_confidence": None,
        "decision_reason": "review_only_frigate_trigger_salvage",
        "decision_kind": "review_only_generic",
        "outcome_bucket": "review_only",
        "source": "video",
        "frigate_trigger_salvage": True,
    }
    # Salvage is evidence/review only. Never promote to named_accept here — even when
    # frigate_species_authority is on (authority applies via fusion/hints with Hub track).
    if named and frigate_species_authority(app_config, camera_id=camera_id):
        row["frigate_prior_label"] = species
        row["frigate_species_authority_eligible"] = True
        # Keep invent-conf out of notify: salvage stays review_only.
        row["decision_reason"] = "review_only_frigate_trigger_salvage"
        row["decision_kind"] = "review_only_generic"
        row["outcome_bucket"] = "review_only"
        row["visit_eligible"] = False
        row["notification_eligible"] = False
    bbox = ev.get("frigate_bbox_norm")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            row["frames"] = [
                {
                    "t": round(max(0.0, float(duration_s) * 0.5), 3),
                    "bbox": [float(x) for x in bbox[:4]],
                }
            ]
        except (TypeError, ValueError):
            pass
    return row


def _yolo_anchor_row_score(row: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(row.get("confidence") or 0.0),
        float(row.get("best_frame_score") or 0.0),
        len(row.get("frames") or []),
    )


def _best_yolo_anchor_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    anchors = _best_yolo_anchor_rows(rows, max_rows=1)
    return anchors[0] if anchors else None


def _best_yolo_anchor_rows(rows: list[dict[str, Any]], *, max_rows: int = 3) -> list[dict[str, Any]]:
    yolo_rows = [
        row for row in (rows or []) if str((row or {}).get("detection_provider") or "").strip().lower() == "yolo"
    ]
    if not yolo_rows:
        return []
    seen_track_ids: set[int] = set()
    ordered = sorted(yolo_rows, key=_yolo_anchor_row_score, reverse=True)
    out: list[dict[str, Any]] = []
    for row in ordered:
        tid = row.get("track_id")
        try:
            tid_int = int(tid) if tid is not None else None
        except (TypeError, ValueError):
            tid_int = None
        if tid_int is not None:
            if tid_int in seen_track_ids:
                continue
            seen_track_ids.add(tid_int)
        out.append(row)
        if len(out) >= max(1, int(max_rows)):
            break
    return out
