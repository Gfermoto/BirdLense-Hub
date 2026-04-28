# Re-ID prototypes (`#383` / `#374`)

Offline helpers — **не** в Docker-процессоре по умолчанию.

## `embed_dinov2_crop.py`

Эмбеддинг одного или нескольких **кропов** (jpeg/png) через **DINOv2** из `torch.hub` (Facebook Research). Выход: L2-нормированный вектор (JSON Lines на stdout).

**Зависимости:** `torch`, `torchvision`, `Pillow` (отдельный venv или машина с GPU/CPU для экспериментов).

```bash
python3 scripts/reid/embed_dinov2_crop.py --image path/to/crop.jpg
python3 scripts/reid/embed_dinov2_crop.py --glob 'samples/*.jpg' --output embeddings.jsonl
```

См. также [REID_ROADMAP.md](../../docs/REID_ROADMAP.md).
