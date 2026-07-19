# Hub-first SOTA — radical bet (2026-07-19)

## Constraints (product)

1. **Hub standalone** — named species without Frigate/MQTT. Frigate is an optional prior, never a go-gate.
2. **Camera-agnostic** — 1+ cameras; dual wide/close is a site layout, not architecture.
3. **SOTA ≠ knobs** — thresholds/salvage/promote cannot deliver ornithological SOTA alone.

## Decision (chosen bet)

**Primary: domain-finetune + classify-first Hub path.**

| Bet | Why chosen / not |
|-----|------------------|
| **A. Site-domain classifier finetune** (primary) | Birder EU is open-world; feeder crops → Unknown/Bird. Closed-set / LoRA on Hub review crops is the direct ornithology lever. |
| **B. Visit product (named\|review\|reject)** (already started) | Keep: deferred Bird = review_only. Expand UI→training loop. Not sufficient alone. |
| **C. Replace detector stack** (defer) | Detect SLOs are OK enough; species quality is the bottleneck. Revisit if Hub-only tracks stay blind. |

## Non-goals for go

- Raising `frigate_species_authority` to inflate `named_share`
- Dual-camera-specific fusion as a release requirement
- Knob-only campaigns on `min_confidence_*`

## Immediate engineering

1. Measure `visit_quality.named_share_hub` (Frigate rows excluded).
2. Frigate rename/standalone opt-in only; default prior-only.
3. Export site-domain crop manifest from review / best_frame (camera-agnostic schema).
4. Golden gate without MQTT (`make validate-pipeline-golden`).

## Success

Hub-only `named_share_hub ≥ 0.40` on a representative window + golden without MQTT PASS → epic #666 go candidate.
