"""Concrete RC4 adapters — Hub YOLO as BoxProvider, Hub as SpeciesAuthority.

Frigate/MQTT adapters stay optional install wiring; they must not become
taxonomy SoT (see ``visit_contract.frigate_species_authority``).
"""

from __future__ import annotations

from typing import Any, Mapping

from recognition_protocols import BoxProvider, SpeciesAuthority, SpeciesHint, TriggerSource


class OpenCvTriggerSource:
    """Placeholder TriggerSource matching motion_source=opencv naming."""

    name = "opencv"

    def poll(self) -> Mapping[str, Any] | None:
        return None


class HubYoloBoxProvider:
    """Expose in-memory finalize tracks as BoxProvider evidence."""

    name = "yolo"

    def __init__(self, tracks: Mapping[Any, Mapping[str, Any]] | None = None):
        self._tracks = dict(tracks or {})

    def boxes_for_window(
        self,
        *,
        start_time: Any,
        end_time: Any,
        camera_id: str | None = None,
    ) -> list[Mapping[str, Any]]:
        del start_time, end_time, camera_id  # session-scoped snapshot
        out: list[Mapping[str, Any]] = []
        for tid, track in self._tracks.items():
            if not isinstance(track, Mapping):
                continue
            bbox = track.get("best_bbox") or track.get("bbox")
            if bbox is None:
                frames = track.get("frames") or []
                if frames and isinstance(frames[0], Mapping):
                    bbox = frames[0].get("bbox")
            out.append(
                {
                    "track_id": tid,
                    "bbox": bbox,
                    "confidence": track.get("best_frame_score") or track.get("confidence"),
                    "provider": self.name,
                }
            )
        return out


class FrigateSpeciesHint:
    """Non-authoritative Frigate/MQTT species prior (never go-metric alone)."""

    name = "frigate"

    def __init__(self, hints: list[Mapping[str, Any]] | None = None):
        self._hints = list(hints or [])

    def hints_for_window(
        self,
        *,
        start_time: Any,
        end_time: Any,
        camera_id: str | None = None,
    ) -> list[Mapping[str, Any]]:
        del start_time, end_time
        if camera_id is None:
            return list(self._hints)
        cam = str(camera_id).strip().lower()
        return [
            h
            for h in self._hints
            if str(h.get("camera_id") or "").strip().lower() in {"", cam}
        ]


class HubSpeciesAuthority:
    """Default SpeciesAuthority: Hub taxonomy wins only."""

    name = "hub"

    def may_accept_named(self, row: Mapping[str, Any]) -> bool:
        from species_recognizer import is_hub_taxonomy_win

        return bool(is_hub_taxonomy_win(row))


def default_hub_stack(
    *,
    tracks: Mapping[Any, Mapping[str, Any]] | None = None,
    frigate_hints: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Bundle default protocol adapters for hub_only installs."""
    trigger: TriggerSource = OpenCvTriggerSource()
    boxes: BoxProvider = HubYoloBoxProvider(tracks)
    hints: SpeciesHint = FrigateSpeciesHint(frigate_hints)
    auth: SpeciesAuthority = HubSpeciesAuthority()
    return {
        "trigger": trigger,
        "boxes": boxes,
        "hints": hints,
        "authority": auth,
    }


def summarize_recognition_stack(
    *,
    tracks: Mapping[Any, Mapping[str, Any]] | None = None,
    mqtt_events: list[Mapping[str, Any]] | None = None,
    trigger_source: str | None = None,
    app_config: Any = None,
) -> dict[str, Any]:
    """Compact RC4 stack blob for ``session_summary.recognition_stack``."""
    frigate_hints: list[Mapping[str, Any]] = []
    for ev in mqtt_events or []:
        if not isinstance(ev, Mapping):
            continue
        src = str(ev.get("source") or ev.get("detection_provider") or "").strip().lower()
        if "frigate" not in src and src != "mqtt":
            # Keep Frigate-labelled events; skip pure YOLO rows.
            label = str(ev.get("label") or ev.get("species_name") or "").strip()
            if not label or src in {"yolo", "opencv", "hub"}:
                continue
        frigate_hints.append(
            {
                "species_name": ev.get("species_name") or ev.get("label"),
                "camera_id": ev.get("camera_id") or ev.get("camera"),
                "confidence": ev.get("confidence") or ev.get("score"),
            }
        )
    stack = default_hub_stack(tracks=tracks, frigate_hints=frigate_hints)
    boxes = stack["boxes"].boxes_for_window(start_time=None, end_time=None)
    hints = stack["hints"].hints_for_window(start_time=None, end_time=None)
    hub_auth = True
    try:
        from recognition_protocols import hub_is_species_authority

        hub_auth = hub_is_species_authority(app_config) if app_config is not None else True
    except Exception:
        hub_auth = True
    trig = str(trigger_source or stack["trigger"].name or "").strip().lower() or stack["trigger"].name
    return {
        "schema": "recognition_stack@v1",
        "trigger": trig,
        "box_provider": stack["boxes"].name,
        "box_count": len(boxes),
        "hint_provider": stack["hints"].name,
        "hint_count": len(hints),
        "species_authority": stack["authority"].name if hub_auth else "frigate_opt_in",
        "hub_is_species_authority": bool(hub_auth),
    }
