# Changelog

All notable changes to BirdLense Hub (Orin).

## [0.5.0] — 2026-07-09

### Added
- Weighted arbiter + eBird regional species hints in the multimodal scoring pipeline
- Welfare distance chip and health anomaly review on recording species cards
- Live overlay editor polish: OpenCV/YOLO toggles, shorter status line, save-polygon helper

### Fixed
- Species card layout: welfare chip and «Why this species?» on separate lines
- Live layout jitter from long OpenCV contour status text
- Telegram connectivity on Orin (API host pin / proxy defaults)
- Gateway arbiter field allowlist and Frigate camera-scoped hints
- Recording/track pipeline stability (qtmux, YOLO dims, overlapping tracklets, spatial-split finalize)

### Changed
- UI i18n: health/welfare labels translated; Live how-to synced with switch labels
- Touch video controls stay visible longer on coarse pointers
- Live camera grid capped at 4 columns for readability

## [0.4.0] — 2026-07-01

### Platform
- **Orin-only**: full migration from Intel NUC / Jetson Nano to Jetson Orin NX/NANO
- ONNX Runtime GPU (CUDA EP) for all inference — detector, classifier, ReID, welfare
- NVIDIA runtime, NVENC/NVDEC hardware encoding
- `Dockerfile.orin` + `docker-compose.orin.yml`
- `BIRDLENSE_PLATFORM=orin`

### Removed
- Intel VA-API / intel_gpu_top / OpenVINO runtime paths
- Jetson Nano (Jetson Nano aarch64 Dockerfile, compose override)
- PyTorch legacy weights (fetch-processor-weights.sh)
- All Intel GPU override scripts and examples

### Added
- `encoding_utils.py` — unified encoding/capture backend normalisation
- `BIRDLENSE_CLASSIFIER_INFERENCE_DEVICE` env var
- Host network mode for Redis on Orin
- **Welfare runtime** — `welfare_runtime.py`, Mahalanobis screening after ReID in finalize
- **`video.record_hw_encode`** — replaces `record_with_vaapi`; Settings UI toggle (NVENC vs libx264)
- ML runtime status: `reid_runtime_enabled`, `welfare_runtime_enabled`

### Developer
- Ruff auto-fix for unused imports and dead code
- x86 dev environment: Flask 3.1.3, pytest (791 tests), Node 22
- Massive cleanup: datasets/ (6.1GB), dead venvs, one-shot scripts
- Branches reduced to main, dev, orin

### Bug fixes
- `docker-compose.orin.yml`: restored missing `./data` and `./app_config` volumes
- `settings_access_service.py`: fixed dead password verification logic
- Default inference device: CPU→cuda:0
