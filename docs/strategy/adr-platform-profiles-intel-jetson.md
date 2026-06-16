# ADR: Platform profiles — Intel NUC vs Jetson Nano

**Status:** Accepted  
**Date:** 2026-06-16

## Context

BirdLense Hub runs on heterogeneous edge hardware:

- **Intel NUC (x86_64)** — production path: OpenVINO IR, VA-API / `ffmpeg_vaapi`, Intel iGPU via `/dev/dri`.
- **Jetson Nano (aarch64)** — NVIDIA SoC: torch inference today, TensorRT / NVDEC-NVENC later; no OpenVINO IR requirement.

Ad-hoc Jetson files on a single device (`Dockerfile.jetson` only on host) do not scale. We need versioned **platform profiles** without changing default Intel behavior.

## Decision

1. Introduce `BIRDLENSE_PLATFORM` with values `intel_nuc` (default) and `jetson_nano`.
2. Store reference overlays under `deploy/profiles/<platform>/` (`.env.example`, `config.overlay.yaml`, README).
3. Keep existing `app/Dockerfile` + `docker-compose.yml` + `docker-compose-intel-override-gen.sh` as the **intel_nuc** path.
4. Add `app/Dockerfile.jetson` + `app/docker-compose.jetson.yml` for **jetson_nano**.
5. `scripts/public/deploy.sh` and `app/Makefile` select compose files / weight gates from platform.
6. Runtime logs platform via `app/processor/src/platform_profile.py`.

Deploy **does not** auto-merge `config.overlay.yaml` into `user_config.yaml` (same policy as today).

## Comparison

| Aspect | intel_nuc (default) | jetson_nano |
|--------|---------------------|-------------|
| **Arch** | x86_64 | aarch64 |
| **Dockerfile** | `app/Dockerfile` (`ultralytics/ultralytics:8.4.21`) | `app/Dockerfile.jetson` (`python:3.11-bookworm`) |
| **Compose** | `docker-compose.yml` + optional `docker-compose.override.yml` (Intel DRI) | `docker-compose.yml` + `docker-compose.jetson.yml` |
| **Inference** | OpenVINO IR + `intel:gpu` (optional) | torch, `cpu` / CUDA later |
| **Weights** | `.pt` + `*_openvino_model/` | `.pt` only |
| **Video encode** | VA-API (`video.encoding: intel`, `record_with_vaapi`) | CPU `libx264` (`encoding: cpu`) |
| **Video decode (live)** | `auto` / `ffmpeg_vaapi` | `opencv` (future: `ffmpeg_nvdec`) |
| **Env flags** | `BIRDLENSE_INFERENCE_BACKEND=openvino`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=1` | `torch`, `BIRDLENSE_OPENVINO_BINARY_ENABLED=0` |
| **Deploy GPU step** | `docker-compose-intel-override-gen.sh` | Skipped; remove stale override |
| **Memory / shm** | 6G / 4gb shm (default compose) | 3G / 1gb shm (jetson override) |
| **Runtime** | default | `nvidia` (when toolkit installed) |

## Deploy

```bash
# Intel — unchanged
make deploy

# Jetson — in scripts/deploy.local.sh
export BIRDLENSE_PLATFORM=jetson_nano
export DEPLOY_HOST="gfer@192.168.8.199"
export DEPLOY_URL="http://192.168.8.199:8085"
make deploy
```

## Consequences

- **Positive:** Single repo, explicit platform switch, Intel prod unchanged without new env vars.
- **Negative:** Jetson video acceleration still CPU-only until `ffmpeg_nvdec` / NVENC implemented.
- **Follow-up:** TensorRT export path, `capture_backend: ffmpeg_nvdec`, optional `requirements-jetson.txt` without OpenVINO pip on arm64.

## References

- `deploy/profiles/intel-nuc/`, `deploy/profiles/jetson-nano/`
- `scripts/platform-profile.sh`
- `docs/strategy/intel_igpu_inference_guide.md`
