# Changelog

All notable changes to BirdLense Hub (Orin).

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

### Developer
- Ruff auto-fix for unused imports and dead code
- x86 dev environment: Flask 3.1.3, pytest (791 tests), Node 22
- Massive cleanup: datasets/ (6.1GB), dead venvs, one-shot scripts
- Branches reduced to main, dev, orin

### Bug fixes
- `docker-compose.orin.yml`: restored missing `./data` and `./app_config` volumes
- `settings_access_service.py`: fixed dead password verification logic
- Default inference device: CPU→cuda:0
