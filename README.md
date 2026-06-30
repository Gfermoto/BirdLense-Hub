<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

Bird monitoring for feeders on **Jetson Orin**: computer vision (ONNX GPU) for detection, classification, re-identification, and visit analysis. Self-hosted, no vendor cloud.

**Full ONNX GPU stack:**

| Component | Model | Backend |
|-----------|-------|---------|
| Detector | Trapper AI v02 2024 (YOLO) | ONNX Runtime CUDA EP / TensorRT EP |
| Classifier | Birder ConvNeXt EU-707 (birder_eu) | ONNX Runtime CUDA EP |
| ReID | Ornimetrics reid_embedder | ONNX Runtime CUDA EP |
| Welfare | Ornimetrics embedder + scorer | ONNX Runtime CUDA EP |
| Tracker | ByteTrack unstick | CPU (boxes) |

**Docs:** [`docs/index.md`](docs/index.md) · [`docs/user/overview.md`](docs/user/overview.md) · [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

## Quick start

```bash
cd app
cp .env.example .env          # edit tokens
make build && make start
```

See [`docs/INSTALL.md`](docs/INSTALL.md) · [`docs/QUICKSTART.md`](docs/QUICKSTART.md)

## Architecture

```
app/
├── web/          # Flask API (OpenAPI)
├── processor/    # ONNX GPU — detection, classification, ReID
├── ui/           # React 19 + MUI (Node 22)
├── data/         # recordings, DB
└── app_config/   # configuration
```

Makefile: `deploy`, `build`, `start`, `stop`, `logs`, `verify`.

## Features

- Timeline (date + time of day)
- CSV / JSON / eBird export
- PDF report
- Unknown birds
- iNaturalist, Xeno-canto

---

**Platform:** Jetson Orin NX 16GB / Orin NANO 8GB · Docker · NVIDIA runtime · ONNX Runtime · NVDEC/NVENC · GStreamer