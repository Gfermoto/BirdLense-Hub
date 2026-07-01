<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Hub Logo">
</p>

# BirdLense Hub

Bird monitoring for feeders on **Jetson Orin**: five neural networks in sequence — detection, species classification, individual re-identification, health assessment, and trajectory tracking. Self-hosted, no vendor cloud.

## Model Stack — ONNX GPU

Every model runs on **ONNX Runtime CUDA EP** (`cuda:0`) on Jetson Orin GPU.

| # | Component | Model | Purpose | Backend |
|---|-----------|-------|---------|---------|
| ① | **Detector** | Trapper AI v02 2024 (YOLO) | Finds bird or Rodent in frame, bounding box | ORT CUDA EP |
| ② | **Classifier** | Birder ConvNeXt EU-707 (birder_eu) | Identifies species: 707 European birds | ORT CUDA EP |
| ③ | **Tracker** | ByteTrack unstick | Links boxes into tracks → movement trajectory | CPU |
| ④ | **ReID** | Ornimetrics DINOv2 | Recognizes individual: same sparrow or different? | ORT CUDA EP |
| ⑤ | **Welfare** | Ornimetrics embedder + scorer | Health assessment: plumage, body condition, activity | ORT CUDA EP |

**Docs:** [`docs/index.md`](docs/index.md) · [Architecture overview](docs/OVERVIEW.md) · [Quick start](docs/QUICKSTART.md)

## How it works

```
IP camera → Detector (bird?) → Classifier (which species?)
                              → Tracker (trajectory)
                              → ReID (which individual?)
                              → Welfare (healthy?)
                              → Recording + UI
```

Scoring Engine filters false positives (confidence + motion + shape + background). First 60 seconds — auto-calibration to the scene. Result: Accept / Review / Reject.

## Quick start

```bash
cd app
cp .env.example .env          # edit tokens
make build && make start
```

See [Installation](docs/user/install.md) · [Quick start](docs/user/quickstart.md)

## Architecture

```
app/
├── web/          # Flask API (OpenAPI), MQTT, Go2RTC
├── processor/    # ONNX GPU: detection, classification, ReID, Welfare
├── ui/           # React 19 + MUI (Node 22)
├── data/         # MP4 recordings, DB, crops
└── app_config/   # user_config.yaml
```

Makefile: `deploy`, `build`, `start`, `stop`, `logs`, `verify`.

## Features

- **Timeline** — date + time of day (morning/day/evening/night)
- **CSV / JSON / eBird** — visit export for analysis
- **PDF report** — monthly summary: species, top-5, charts
- **Unknown birds** — Review zone + best-guess classifier
- **Integrations** — iNaturalist, Xeno-canto, BirdNET (audio), Telegram

---

**Platform:** Jetson Orin NX 16GB / Orin NANO 8GB · Docker · NVIDIA runtime · ONNX Runtime CUDA EP · GStreamer NVDEC/NVENC
