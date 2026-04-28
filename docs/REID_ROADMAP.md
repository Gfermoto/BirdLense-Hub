# Bird re-identification — roadmap (#374)

**Status:** research / design — not shipped as product defaults.

## Goals

- Same individual across visits: **metric learning** or **embedding** head on detector crops; temporal smoothing with ByteTrack IDs.

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
