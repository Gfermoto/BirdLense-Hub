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

**Docs:** [Project overview](./docs/user/overview.md) · [Full documentation index](./docs/index.md) · [Documentation site (Pages)](https://gfermoto.github.io/BirdLense-Hub/)

**Community:** [Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions) · [Issues](https://github.com/Gfermoto/BirdLense-Hub/issues)

See [Installation](docs/user/install.md) · [Quick start](docs/user/quickstart.md)

Two components: **detector** (bird or rodent in frame) and **classifier** (bird species).

```
app/
├── web/          # Flask API (OpenAPI), MQTT, Go2RTC
├── processor/    # ONNX GPU: detection, classification, ReID, Welfare
├── ui/           # React 19 + MUI (Node 22)
├── data/         # MP4 recordings, DB, crops
└── app_config/   # user_config.yaml
```

**Current model:** EU (birds-525 + iNaturalist Europe, ~491 species). US (NABirds) — backup in `best_US.pt`.

**EU model:** classifier trained on merged_cls → [gfermoto/birds-eu-merged](https://huggingface.co/datasets/gfermoto/birds-eu-merged). Weights: [gfermoto/birdlense-birds-eu](https://huggingface.co/gfermoto/birdlense-birds-eu). Training: [docs/TRAINING.md](./archive/internal/docs-legacy/TRAINING.md). Detector unchanged.

**Runtime weights:** two-stage `app/processor/models/detection/weights/best.pt` (binary from zip in fork [AleksandrRogachev94/BirdLense `app/processor`](https://github.com/AleksandrRogachev94/BirdLense/tree/main/app/processor)) and `app/processor/models/classification/weights/best.pt` ([`gfermoto/birdlense-birds-eu`](https://huggingface.co/gfermoto/birdlense-birds-eu) on Hugging Face). `scripts/fetch-processor-weights.sh` fetches both. Keep `class_names.txt` aligned with the classifier. `app/yolo11n.pt` is legacy-only (`--legacy-single-stage`).

**Catalog hygiene:** align the Hub species list with your classifier using `species.catalog_allowlist_file` + optional `catalog_strict_ingest`, `scripts/datasets/dump_classifier_allowlist.py`, and `POST /api/ui/system/species-catalog/reconcile` — see [docs/CONFIGURATION.md](./docs/user/configuration.md).

**Optional behavior baseline (logistic JSON, #416):** a **demo** `behavior_logistic_export@v1.json` ships under `app/processor/models/behavior/` with default path `models/behavior/behavior_logistic_export@v1.json` (relative to `app/processor/`). There is **no in-Hub UI to label a training dataset or run training** — only Settings toggles/path/thresholds and per-clip manual label edit on the video page. Full training: CSV → `make ml-build-behavior-dataset` → `make ml-train-behavior-baseline` (see [README.ru.md](./README.ru.md) Russian section *Обучение baseline «поведения»*).

<details>
<summary>📷 Screenshots</summary>
<br>
<p align="center">
  <img src="screenshots/dashboard1.jpg" width="800" alt="Dashboard">
</p>
<p align="center">
  <img src="screenshots/dashboard2.jpg" width="800" alt="Activity">
</p>
<p align="center">
  <img src="screenshots/video-details.jpg" width="800" alt="Video Details">
</p>
</details>

## Features

- **Timeline** — date + time of day (morning/day/evening/night)
- **CSV / JSON / eBird** — visit export for analysis
- **PDF report** — monthly summary: species, top-5, charts
- **Unknown birds** — Review zone + best-guess classifier
- **Integrations** — iNaturalist, Xeno-canto, BirdNET (audio), Telegram

### Analytics & Export
- **CSV/JSON export** — download visits for analysis in Excel/Python
- **eBird export** — checklist format for import into eBird.org
- **Region comparison** — compare your species with eBird region top (Overview card)
- **PDF report** — monthly summary: species count, top-5, charts
- **Prometheus metrics** — `/metrics` for Grafana dashboards

**Platform:** Jetson Orin NX 16GB / Orin NANO 8GB · Docker · NVIDIA runtime · ONNX Runtime CUDA EP · GStreamer NVDEC/NVENC
