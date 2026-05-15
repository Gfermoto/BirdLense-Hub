# Bird re-identification — roadmap (#374)

**Status:** research / design — not shipped as product defaults.

## Goals

- Same individual across visits: **metric learning** or **embedding** head on detector crops; temporal smoothing with ByteTrack IDs.

## Backbone — DINO / DINOv2 (planned candidate)

**Role:** a frozen or lightly tuned **ViT** backbone on detector crops produces a fixed-size **embedding** for cosine similarity / metric learning — tracked under [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374).

**What it gives you**

- **Fine-grained appearance features** with relatively little per-individual labeling: DINO-style self-supervised pretraining transfers well when “same bird again” labels are sparse compared to species classification.
- **Embeddings that cluster by look**, not by taxonomy alone — aligned with **individual** Re-ID (same feeder, different visits), unlike the main EU/US species classifier head.
- A standard training stack (**PyTorch**, timm/torch.hub) so prototypes stay reproducible; deployment path (latency, optional ONNX) must be validated on your hub hardware like any new model.

**What it does *not* replace**

- The existing **binary detector** and **species classifier** pipeline stays the default product path unless you redesign scope. Re-ID is an **add-on**: extra compute per crop or per visit.

**Trade-offs**

- **Latency and VRAM** vs classifier-only; embedding dimension and input resolution drive cost.
- Strong embeddings still need **policy** (thresholds, gallery aging, “new individual”) — see Acceptance below.

## Species classification — same backbone (optional)

DINO/DINOv2 is **not** only for individual Re-ID. The same backbone can support **species** quality and tooling:

- **Fine-tuning**: add a species classification head on detector crops — SSL backbones often data-efficient vs training a small net from scratch on your labels.
- **Labeling & active learning**: embedding similarity helps find duplicates, confusion pairs, and priority batches ([#369](https://github.com/Gfermoto/BirdLense-Hub/issues/369)), aligned with the classifier roadmap ([#370](https://github.com/Gfermoto/BirdLense-Hub/issues/370)).

**One backbone on the hub (design target):** one forward pass per crop can feed **both** a species head **and** an L2 embedding for Re-ID if integrated — typically **one** ViT load in VRAM instead of two unrelated models. Cost remains **one ViT forward + thin heads** whenever both paths are enabled; toggles can turn Re-ID off or run embeddings offline/batched to cap load.

The [#383](https://github.com/Gfermoto/BirdLense-Hub/issues/383) prototype focuses on the Re-ID gallery first; species experiments stay documented here until folded into [TRAINING](./TRAINING.md) / processor wiring.

### Offline prototype script (repository)

- **`scripts/reid/embed_dinov2_crop.py`** — load DINOv2 via `torch.hub`, L2-normalized embedding per image path; JSON Lines output. See **`scripts/reid/README.md`**. Requires PyTorch + torchvision + Pillow in your training/offline environment (not bundled as a processor runtime dependency).
- **`scripts/reid/embed_cosine_report.py`** — pairwise cosine stats, optional **top-K neighbors** per row, optional `--pairs` file for labeled same-individual pairs vs random negatives (Markdown report). Requires **numpy** only.
- **`scripts/reid/export_crops_from_sqlite.py`** — export detector crops from **`video_species`** rows (bbox + ffmpeg frame grab), matching Hub crop semantics; feed output JPEGs into `embed_dinov2_crop.py`. Requires **ffmpeg**, OpenCV, read-only SQLite access.

## Phase 1 (design)

- Literature + feasibility: labeled individuals are rare → default **self-supervised** or **supervised contrastive** when users supply IDs.
- Storage: **embedding per visit** in an extension / sidecar table — **no breaking change** to core visit schema until agreed.

## Phase 2 (product-shaped)

- UI: “likely same bird as visit #…” via cosine similarity + time decay.
- Export embeddings for researchers (CSV/Parquet).

## Privacy

Local-only processing by default; any cloud/opt-in must be explicit in deployment docs.

## Acceptance

Tracked in [#374](https://github.com/Gfermoto/BirdLense-Hub/issues/374) (Rank-1 thresholds, gallery “new individual” path).
