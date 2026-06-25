# BirdLense Hub (Orin) — Agent Instructions

## Critical Requirements

- **Node.js 22** only — check `app/ui/.nvmrc`. Engine in `package.json` enforces `>=22.0.0 <23`.
- **UI build BEFORE Docker**: `cd app/ui && npm run build && cd .. && docker compose build`

## Key Commands

| Command | What it does |
|---------|-------------|
| `make deploy` | Deploy to remote Orin host (rsync + build + start) |
| `make build` | Build Docker image |
| `make start` | Start Docker stack |
| `make stop` | Stop Docker stack |
| `make logs` | Tail container logs |
| `make verify` | Health check against DEPLOY_URL |

## Architecture

```
app/
├── web/           # Flask API (OpenAPI)
├── processor/     # ONNX GPU inference pipeline
├── ui/            # React 19 + MUI (Node 22)
├── data/          # recordings/, db/
└── app_config/    # user_config.yaml
```

## Production Gates

- `BIRDLENSE_ENV=production`
- `BIRDLENSE_STRICT_API_AUTH=1`
- `FLASK_SECRET_KEY`, `PROCESSOR_SECRET` — 32-char hex

## Common Pitfalls

1. Node version mismatch → check `.nvmrc` + `package.json` engines
2. Missing UI build before Docker → `npm run build` first
3. 403 from processor → bad `PROCESSOR_SECRET` in `.env`
4. GPU not visible → check NVIDIA runtime, `nvidia-smi` in container

## Model Stack

| Component | Model | Format | Backend |
|-----------|-------|--------|---------|
| Detector | Trapper AI v02 2024 | ONNX | ORT CUDA EP / TensorRT EP |
| Classifier | Birder ConvNeXt EU-707 | ONNX | ORT CUDA EP |
| ReID | Ornimetrics reid_embedder | ONNX | ORT CUDA EP |
| Welfare | Ornimetrics embedder + scorer | ONNX + NPZ | ORT CUDA EP |
| Tracker | ByteTrack unstick | YAML | CPU |