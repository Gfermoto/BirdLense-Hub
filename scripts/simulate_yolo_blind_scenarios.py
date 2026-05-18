#!/usr/bin/env python3
"""Synthetic validation for YOLO blind-gate + persistent state logic."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ROOT = os.path.join(ROOT, "app")
PROC_SRC = os.path.join(ROOT, "app", "processor", "src")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
if PROC_SRC not in sys.path:
    sys.path.insert(0, PROC_SRC)

from detection_fusion import build_fused_video_detections  # noqa: E402
from session_state_repository import SessionStateRepository  # noqa: E402


class DummyConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: str


def _base_cfg() -> DummyConfig:
    return DummyConfig(
        {
            "detection.merge_window_seconds": 5,
            "detection.dedup_window_seconds": 45,
            "detection.one_per_species": True,
            "detection.source_priority": ["yolo", "frigate"],
            "detection.cross_source_confidence_bonus": 0.0,
            "detection.min_confidence_to_store": 0.05,
            "detection.frigate_standalone_when_no_yolo": True,
            "detection.frigate_standalone_when_no_accepted_species": True,
            "detection.frigate_standalone_require_blind_yolo": True,
            "detection.frigate_standalone_min_score": 0.52,
            "detection.frigate_standalone_missing_score_fallback": 0.72,
            "detection.yolo_blind_required_consecutive_sessions": 1,
            "detection.yolo_blind_min_duration_seconds": 30,
            "detection.yolo_blind_min_frames": 180,
            "detection.yolo_blind_min_frigate_only_frames": 120,
            "processor.multi_camera_groups": [],
            "processor.birdnet_mqtt_half_life_hours": 6.0,
        }
    )


def _frigate_event(ts_iso: str) -> dict:
    return {
        "source": "frigate",
        "species": "Great Tit",
        "label": "bird",
        "camera": "BirdBox",
        "confidence": 0.8,
        "timestamp": ts_iso,
        "_session_trigger_snapshot": True,
    }


def _yolo_detection() -> dict:
    return {
        "track_id": 11,
        "species_name": "Great Tit",
        "species": "Great Tit",
        "confidence": 0.64,
        "start_time": 0.0,
        "end_time": 5.0,
        "detection_provider": "yolo",
        "source": "video",
        "detector_confidence": 0.71,
        "classifier_confidence": 0.64,
        "decision_reason": "accepted_species",
        "decision_kind": "accepted_species",
        "accepted": True,
        "visit_eligible": True,
        "notification_eligible": True,
        "frames": [{"t": 0.1, "bbox": [0.1, 0.1, 0.2, 0.2]}],
    }


def _blind_from_repo(repo: SessionStateRepository, cfg: DummyConfig) -> bool:
    return repo.is_blind_confirmed(
        camera_id="BirdBox",
        min_recent_sessions=int(cfg.get("detection.yolo_blind_required_consecutive_sessions") or 1),
        min_yolo_frames=int(cfg.get("detection.yolo_blind_min_frames") or 180),
        min_frigate_only_frames=int(cfg.get("detection.yolo_blind_min_frigate_only_frames") or 120),
        min_duration_seconds=float(cfg.get("detection.yolo_blind_min_duration_seconds") or 30.0),
    )


def run() -> list[ScenarioResult]:
    cfg = _base_cfg()
    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=35)
    frigate = [_frigate_event(end.isoformat())]
    results: list[ScenarioResult] = []

    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "state.db")
        repo = SessionStateRepository(db_path=db_path)

        # 1) Норма: YOLO + Frigate => YOLO geometry сохраняется.
        out_norm = build_fused_video_detections(
            [_yolo_detection()],
            frigate,
            start_time=start,
            end_time=end,
            app_config=cfg,
            yolo_blind_confirmed=False,
        )
        passed_norm = bool(out_norm) and any(
            str((row or {}).get("detection_provider") or "").lower() == "yolo"
            for row in out_norm
        )
        results.append(
            ScenarioResult(
                "Норма",
                passed_norm,
                f"rows={len(out_norm)} yolo_rows={sum(1 for r in out_norm if str(r.get('detection_provider','')).lower() == 'yolo')}",
            )
        )

        # 2) Короткая слепота (< порога): не подтверждаем blind.
        repo.save_session_runtime(
            {
                "triggered_camera": "BirdBox",
                "duration_s": 5.0,
                "yolo_frames_ran": 35,
                "yolo_raw_boxes_total": 0,
                "session_extended_by_frigate_only": 35,
                "video_file_ok": True,
            }
        )
        blind_short = _blind_from_repo(repo, cfg)
        out_short = build_fused_video_detections(
            [],
            frigate,
            start_time=start,
            end_time=end,
            app_config=cfg,
            yolo_blind_confirmed=blind_short,
        )
        results.append(
            ScenarioResult(
                "Слепота YOLO short",
                (not blind_short) and out_short == [],
                f"blind={blind_short} standalone_rows={len(out_short)}",
            )
        )

        # 3) Длинная слепота (> порога): подтверждаем blind + low-confidence standalone.
        repo.save_session_runtime(
            {
                "triggered_camera": "BirdBox",
                "duration_s": 34.0,
                "yolo_frames_ran": 238,
                "yolo_raw_boxes_total": 0,
                "session_extended_by_frigate_only": 170,
                "video_file_ok": True,
            }
        )
        blind_long = _blind_from_repo(repo, cfg)
        out_long = build_fused_video_detections(
            [],
            frigate,
            start_time=start,
            end_time=end,
            app_config=cfg,
            yolo_blind_confirmed=blind_long,
        )
        long_ok = (
            blind_long
            and len(out_long) == 1
            and str(out_long[0].get("detection_provider") or "").lower() == "frigate"
            and out_long[0].get("source_reason") == "blind_yolo"
            and out_long[0].get("confidence_level") == "low"
        )
        results.append(
            ScenarioResult(
                "Слепота YOLO long/critical",
                long_ok,
                f"blind={blind_long} rows={len(out_long)}",
            )
        )

        # 4) Восстановление: после blind снова появляются боксы => blind сброшен.
        repo.save_session_runtime(
            {
                "triggered_camera": "BirdBox",
                "duration_s": 40.0,
                "yolo_frames_ran": 280,
                "yolo_raw_boxes_total": 22,
                "session_extended_by_frigate_only": 3,
                "video_file_ok": True,
            }
        )
        blind_recovered = _blind_from_repo(repo, cfg)
        results.append(
            ScenarioResult(
                "Восстановление YOLO",
                not blind_recovered,
                f"blind_after_recovery={blind_recovered}",
            )
        )

        # 5) Рестарт: новый repo instance видит ранее записанное состояние.
        repo_after_restart = SessionStateRepository(db_path=db_path)
        rows_after_restart = repo_after_restart.recent_blind_sessions(camera_id="BirdBox", limit=10)
        restart_ok = len(rows_after_restart) >= 3
        results.append(
            ScenarioResult(
                "Рестарт контейнера/процесса",
                restart_ok,
                f"rows_visible_after_restart={len(rows_after_restart)}",
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit code 1 if at least one scenario fails.",
    )
    args = parser.parse_args()
    results = run()
    print("Synthetic scenarios:")
    failed = 0
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"- {item.name}: {status} ({item.details})")
        if not item.passed:
            failed += 1
    if failed:
        print(f"Summary: {failed} failed / {len(results)} total")
        return 1 if args.strict else 0
    print(f"Summary: all {len(results)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
