"""Trigger graph and source FP/FN metrics (SOTA-07)."""

from __future__ import annotations

import unittest

from trigger_graph import (
    TRIGGER_NODES,
    aggregate_trigger_metrics,
    build_session_trigger_graph,
)


class TestTriggerGraph(unittest.TestCase):
    def _base_summary(self, **overrides):
        base = {
            "frames_seen": 200,
            "yolo_frames_ran": 150,
            "yolo_frames_with_tracks": 0,
            "yolo_raw_boxes_total": 0,
            "post_fusion_persisted": 0,
            "session_extended_by_frigate_only": 80,
            "video_file_ok": True,
            "yolo_blind_confirmed": True,
        }
        base.update(overrides)
        return base

    def test_frigate_init_yolo_fn(self):
        summary = self._base_summary()
        ctx = {"triggered_by": "frigate", "triggered_camera": "BirdBox", "runtime_signals": summary}
        tg = build_session_trigger_graph(
            session_summary=summary,
            recording_context=ctx,
            persisted_tracks=[],
            rejected_tracks=[],
            mqtt_events=[{"source": "frigate"}, {"source": "birdnet"}],
        )
        self.assertEqual(tg["init_source"], "frigate")
        self.assertEqual(tg["metrics_by_source"]["frigate"]["recordings_initiated"], 1)
        self.assertGreater(tg["metrics_by_source"]["yolo"]["fn_detector_silent"], 0)
        self.assertEqual(tg["metrics_by_source"]["birdnet"]["mqtt_events"], 1)

    def test_yolo_persisted_with_reason(self):
        summary = self._base_summary(
            yolo_raw_boxes_total=12,
            post_fusion_persisted=1,
            yolo_frames_with_tracks=5,
            session_extended_by_frigate_only=0,
            yolo_blind_confirmed=False,
        )
        persisted = [
            {
                "detection_provider": "yolo",
                "decision_reason": "accepted_species",
                "track_id": 1,
            }
        ]
        tg = build_session_trigger_graph(
            session_summary=summary,
            recording_context={"triggered_by": "opencv"},
            persisted_tracks=persisted,
            rejected_tracks=[],
        )
        self.assertEqual(tg["metrics_by_source"]["yolo"]["species_persisted"], 1)
        self.assertIn("accepted_species", tg["decision_reason_counts"])

    def test_aggregate_sessions(self):
        s1 = {
            "trigger_graph": build_session_trigger_graph(
                session_summary=self._base_summary(),
                recording_context={"triggered_by": "frigate", "triggered_camera": "A"},
                persisted_tracks=[],
                rejected_tracks=[],
            )
        }
        agg = aggregate_trigger_metrics([s1])
        self.assertEqual(agg["session_count"], 1)
        self.assertEqual(agg["recordings_initiated_by_source"].get("frigate"), 1)
        self.assertIn("frigate", agg["metrics_by_source"])

    def test_all_nodes_present(self):
        tg = build_session_trigger_graph(
            session_summary=self._base_summary(),
            recording_context={"triggered_by": "scale"},
            persisted_tracks=[],
            rejected_tracks=[],
        )
        for node in TRIGGER_NODES:
            self.assertIn(node, tg["metrics_by_source"])


if __name__ == "__main__":
    unittest.main()
