import json


def test_build_review_retrain_cycle_report_reads_quality_gates(app, tmp_path):
    from services.ml_quality_cycle_service import build_review_retrain_cycle_report

    dataset_info = tmp_path / "dataset_info.json"
    dataset_info.write_text(
        json.dumps(
            {
                "split_params": {
                    "ready_for_train": True,
                    "strict_quality": True,
                },
                "quality": {
                    "duplicate_track_count": 0,
                    "video_leakage": {
                        "train_val_shared": 0,
                        "train_test_shared": 0,
                        "val_test_shared": 0,
                    },
                    "group_leakage": {
                        "train_val_shared": 0,
                        "train_test_shared": 0,
                        "val_test_shared": 0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    fusion_eval = tmp_path / "fusion_eval_report.csv"
    fusion_eval.write_text("section,metric,value\nsummary,auc,0.88\n", encoding="utf-8")

    with app.app_context():
        report = build_review_retrain_cycle_report(
            days=7,
            dataset_info_path=str(dataset_info),
            fusion_eval_report_path=str(fusion_eval),
            runtime_snapshot={"latency_ms": {"frame_processor_detect_p95": 44.0}},
        )

    assert report["gates"]["dataset_ready_for_train"] is True
    assert report["gates"]["dataset_strict_quality_ok"] is True
    assert report["gates"]["fusion_eval_present"] is True
    assert report["gates"]["runtime_observability_present"] is True
    assert report["inputs"]["dataset_info_path"] == str(dataset_info)


def test_build_review_retrain_cycle_report_requires_strict_quality_flag(app, tmp_path):
    from services.ml_quality_cycle_service import build_review_retrain_cycle_report

    dataset_info = tmp_path / "dataset_info.json"
    dataset_info.write_text(
        json.dumps(
            {
                "split_params": {
                    "ready_for_train": True,
                    "strict_quality": False,
                },
                "quality": {
                    "duplicate_track_count": 0,
                    "video_leakage": {
                        "train_val_shared": 0,
                        "train_test_shared": 0,
                        "val_test_shared": 0,
                    },
                    "group_leakage": {
                        "train_val_shared": 0,
                        "train_test_shared": 0,
                        "val_test_shared": 0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with app.app_context():
        report = build_review_retrain_cycle_report(
            days=7,
            dataset_info_path=str(dataset_info),
            fusion_eval_report_path=None,
            runtime_snapshot={},
        )

    assert report["gates"]["dataset_ready_for_train"] is True
    assert report["gates"]["dataset_strict_quality_ok"] is False
