# Legacy Intel / OpenVINO dev scripts (archived)

Orin-only Hub uses **ONNX Runtime CUDA EP** — these scripts targeted OpenVINO IR export,
PT vs OV geometry audits, and Intel NUC-era detector training.

**Not used in production deploy.** Kept for historical reference or one-off lab work on old hardware.

| Script | Was used for |
|--------|----------------|
| `train_detector_brg.py` | Ultralytics YOLO train + OpenVINO export |
| `audit_detector_geometry.py` | PT vs OpenVINO bbox audit on MP4 |
| `run_trapper_performance_test.py` | Trapper OpenVINO @704 benchmark |
| `snapshot_detector_weights.py` | Backup `best.pt` + `best_openvino_model/` |
| `detector_synthetic_smoke.py` | Synthetic frames → OV/PT detector smoke |
| `validate_static_object_filter.py` | Static-object filter eval (OV default path) |
| `ml_int8_candidate_eval.py` | INT8 detector candidate gate vs baseline benchmark |

Active Orin diagnostics: `scripts/diag_video_detect.py`, `scripts/diagnose_detection_funnel.py`.
