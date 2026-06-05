"""
Trigger graph model and source-specific FP/FN metrics (SOTA-07 / #498).

Nodes: Frigate, OpenCV, YOLO, BirdNET, Scale.
Edges: initiated_recording, extended_session, species_persisted, candidate_rejected, mqtt_window.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Iterable, Mapping

from runtime_contract import apply_runtime_contract_rows, choose_primary_provider, normalize_provider

TRIGGER_NODES = ("frigate", "opencv", "yolo", "birdnet", "scale")

_EDGE_INITIATED = "initiated_recording"
_EDGE_EXTENDED = "extended_session"
_EDGE_SPECIES = "species_persisted"
_EDGE_REJECTED = "candidate_rejected"
_EDGE_MQTT = "mqtt_in_window"


@dataclass
class TriggerGraphEdge:
    source: str
    target: str
    kind: str
    count: int = 1
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceMetrics:
    recordings_initiated: int = 0
    session_extensions: int = 0
    species_persisted: int = 0
    candidates_rejected: int = 0
    mqtt_events: int = 0
    fp_empty_recording: int = 0
    fp_rejected_noise: int = 0
    fn_detector_silent: int = 0
    fn_no_persisted_species: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _norm_trigger_source(raw: str | None) -> str:
    val = str(raw or "").strip().lower()
    if val in TRIGGER_NODES:
        return val
    if val in ("birdnet_mqtt", "birdnet"):
        return "birdnet"
    if val in ("scale_weight", "scale_weight_motion", "scales"):
        return "scale"
    if val in ("file", "video_file", "track_regen"):
        return "opencv"
    return val or "opencv"


def _mqtt_source_counts(mqtt_events: Iterable[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for ev in mqtt_events or []:
        if not isinstance(ev, dict):
            continue
        src = normalize_provider(str(ev.get("source") or ""))
        if src == "birdnet":
            counts["birdnet"] += 1
        elif src == "frigate":
            counts["frigate"] += 1
        elif src in ("scale", "scales"):
            counts["scale"] += 1
    return counts


def _empty_metrics() -> dict[str, SourceMetrics]:
    return {node: SourceMetrics() for node in TRIGGER_NODES}


def build_session_trigger_graph(
    *,
    session_summary: Mapping[str, Any],
    recording_context: Mapping[str, Any] | None,
    persisted_tracks: Iterable[dict],
    rejected_tracks: Iterable[dict],
    mqtt_events: Iterable[dict] | None = None,
) -> dict[str, Any]:
    """
    Build per-session trigger graph + FP/FN metrics for persistence in ``payload_json``.
    """
    ctx = dict(recording_context or {})
    rs = dict(ctx.get("runtime_signals") or {})
    init_source = _norm_trigger_source(ctx.get("triggered_by"))
    camera_id = str(ctx.get("triggered_camera") or session_summary.get("triggered_camera") or "").strip() or None

    metrics = _empty_metrics()
    edges: list[TriggerGraphEdge] = []
    by_reason: Counter[str] = Counter()

    metrics[init_source].recordings_initiated += 1
    edges.append(TriggerGraphEdge(init_source, "recording", _EDGE_INITIATED))

    frigate_only = int(
        rs.get("session_extended_by_frigate_only") or session_summary.get("session_extended_by_frigate_only") or 0
    )
    if frigate_only > 0:
        metrics["frigate"].session_extensions += frigate_only
        edges.append(TriggerGraphEdge("frigate", "recording", _EDGE_EXTENDED, count=frigate_only))

    mqtt_counts = _mqtt_source_counts(mqtt_events or [])
    for node, cnt in mqtt_counts.items():
        if node in metrics:
            metrics[node].mqtt_events += int(cnt)
            edges.append(TriggerGraphEdge(node, "recording", _EDGE_MQTT, count=int(cnt)))

    persisted = apply_runtime_contract_rows(list(persisted_tracks or []))
    rejected = apply_runtime_contract_rows(list(rejected_tracks or []))

    for row in persisted:
        provider = _norm_trigger_source(choose_primary_provider(row))
        if provider not in metrics:
            provider = "yolo"
        metrics[provider].species_persisted += 1
        reason = str(row.get("decision_reason") or "").strip()
        if reason:
            by_reason[reason] += 1
        edges.append(
            TriggerGraphEdge(
                provider,
                "species",
                _EDGE_SPECIES,
                meta={"decision_reason": reason or None},
            )
        )

    for row in rejected:
        provider = _norm_trigger_source(choose_primary_provider(row))
        if provider not in metrics:
            provider = "yolo"
        metrics[provider].candidates_rejected += 1
        reason = str(row.get("decision_reason") or row.get("reject_reason_code") or "").strip()
        if reason:
            by_reason[reason] += 1
        edges.append(
            TriggerGraphEdge(
                provider,
                "rejected",
                _EDGE_REJECTED,
                meta={"decision_reason": reason or None},
            )
        )

    post_fusion = int(session_summary.get("post_fusion_persisted") or 0)
    frames_seen = int(session_summary.get("frames_seen") or 0)
    yolo_raw = int(session_summary.get("yolo_raw_boxes_total") or 0)
    video_ok = bool(session_summary.get("video_file_ok", True))
    detect_first_ok = bool(
        rs.get("detect_first_confirmed") or session_summary.get("detect_first_confirmed")
    )
    yolo_tracks = int(session_summary.get("yolo_frames_with_tracks") or rs.get("yolo_frames_with_tracks") or 0)

    # FP: trigger fired but nothing useful persisted (operator-visible false alarm).
    # Skip when lores detect-first confirmed — persist failure is downstream, not opencv FP.
    if video_ok and frames_seen >= 30 and post_fusion == 0:
        if not detect_first_ok:
            metrics[init_source].fp_empty_recording += 1

    # FP: rejected noise candidates (weak generic / phantom / short track).
    _FP_REJECT_REASONS = {
        "rejected_weak_generic_bird",
        "rejected_weak_generic_rodent",
        "rejected_phantom_boxes",
        "rejected_static_objects",
        "rejected_texture",
        "rejected_background_subtraction",
    }
    for row in rejected:
        reason = str(row.get("decision_reason") or "").strip().lower()
        if reason in _FP_REJECT_REASONS:
            provider = _norm_trigger_source(choose_primary_provider(row))
            if provider in metrics:
                metrics[provider].fp_rejected_noise += 1

    # FN: Frigate extended session but YOLO produced no raw boxes.
    if frigate_only > 0 and yolo_raw == 0:
        metrics["yolo"].fn_detector_silent += 1
        metrics["frigate"].fn_no_persisted_species += 1

    # FN: recording with motion but YOLO never ran tracks despite frames.
    yolo_ran = int(session_summary.get("yolo_frames_ran") or 0)
    if frames_seen >= 60 and yolo_ran >= 30 and yolo_tracks == 0 and post_fusion == 0:
        metrics["yolo"].fn_no_persisted_species += 1

    if bool(session_summary.get("yolo_blind_confirmed")):
        metrics["yolo"].fn_detector_silent += 1

    nodes = [{"id": n, "label": n.upper()} for n in TRIGGER_NODES]
    return {
        "camera_id": camera_id,
        "init_source": init_source,
        "trigger_display": ctx.get("trigger_display"),
        "nodes": nodes,
        "edges": [e.to_dict() for e in edges],
        "metrics_by_source": {k: v.to_dict() for k, v in metrics.items()},
        "decision_reason_counts": dict(sorted(by_reason.items())),
        "runtime_contract": {
            "persisted_primary_provider_counts": dict(
                Counter(_norm_trigger_source(choose_primary_provider(r)) for r in persisted)
            ),
            "rejected_primary_provider_counts": dict(
                Counter(_norm_trigger_source(choose_primary_provider(r)) for r in rejected)
            ),
        },
    }


def aggregate_trigger_metrics(sessions: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate trigger_graph payloads from multiple sessions (Analytics API)."""
    totals = _empty_metrics()
    by_camera: dict[str, dict[str, SourceMetrics]] = defaultdict(_empty_metrics)
    by_reason: Counter[str] = Counter()
    init_counts: Counter[str] = Counter()
    session_count = 0

    for summary in sessions:
        if not isinstance(summary, dict):
            continue
        tg = summary.get("trigger_graph")
        if not isinstance(tg, dict):
            payload_raw = summary.get("payload_json")
            if isinstance(payload_raw, str):
                try:
                    import json

                    payload = json.loads(payload_raw)
                    tg = payload.get("trigger_graph") if isinstance(payload, dict) else None
                except Exception:
                    tg = None
            elif isinstance(payload_raw, dict):
                tg = payload_raw.get("trigger_graph")
        if not isinstance(tg, dict):
            continue
        session_count += 1
        cam = str(tg.get("camera_id") or summary.get("triggered_camera") or "").strip() or "_unknown"
        init_counts[str(tg.get("init_source") or "opencv")] += 1
        for reason, cnt in (tg.get("decision_reason_counts") or {}).items():
            try:
                by_reason[str(reason)] += int(cnt)
            except (TypeError, ValueError):
                pass
        per_src = tg.get("metrics_by_source") or {}
        for node in TRIGGER_NODES:
            block = per_src.get(node) or {}
            if not isinstance(block, dict):
                continue
            for field_name in [f.name for f in fields(SourceMetrics)]:
                try:
                    delta = int(block.get(field_name) or 0)
                except (TypeError, ValueError):
                    delta = 0
                setattr(totals[node], field_name, getattr(totals[node], field_name) + delta)
                setattr(
                    by_camera[cam][node],
                    field_name,
                    getattr(by_camera[cam][node], field_name) + delta,
                )

    return {
        "session_count": session_count,
        "recordings_initiated_by_source": dict(sorted(init_counts.items())),
        "metrics_by_source": {k: v.to_dict() for k, v in totals.items()},
        "decision_reason_counts": dict(by_reason.most_common(50)),
        "by_camera": {cam: {n: m.to_dict() for n, m in blocks.items()} for cam, blocks in sorted(by_camera.items())},
    }
