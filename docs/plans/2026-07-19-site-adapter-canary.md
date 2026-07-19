# SiteAdapter species_priors — Orin canary plan (2026-07-19)

Manifest: `app/data/site_adapter/manifest.json` (not in git).  
Runtime: `adjust_confidence_with_site_adapter` in linear classify (canary bucket).

## Goal

Nudge classifier confidence for site-frequent / pack-hard species
(House Sparrow, Fieldfare, Eurasian Collared-Dove, …) without swapping ONNX.

## Dry-run (safe)

```bash
python3 scripts/seed_site_adapter_priors.py \
  --db app/data/db/birdlense.db --data-dir app/data \
  --from-video-species \
  --include-species 'Fieldfare' \
  --include-species 'Eurasian Collared-Dove,House Sparrow'
# no --apply → prints priors only
```

Or: `make seed-site-adapter-priors-dry`

## Apply canary (explicit operator OK only)

```bash
cp -a app/data/site_adapter/manifest.json \
  "app/data/site_adapter/manifest.json.bak.$(date +%Y%m%d)_priors" 2>/dev/null || true

python3 scripts/seed_site_adapter_priors.py \
  --db app/data/db/birdlense.db --data-dir app/data \
  --from-video-species \
  --include-species 'Fieldfare,Eurasian Collared-Dove,House Sparrow' \
  --apply --status canary --canary-share 0.25 --delta 0.04

# processor reads data/ on next classify; restart if unsure:
docker compose -f app/docker-compose.orin.yml up -d --force-recreate birdlense
make verify
```

Check: `/api/ui/system/feedback-loop/status` → `site_adapter.canary_ready`  
and `ml-runtime` → `site_adapter.prior_species_count`.

## Observe

| Signal | Expect |
|--------|--------|
| `session_summary` / decision meta `site_adapter.applied` | some tracks |
| Pack curate Fieldfare / Dove / Sparrow | better KEEP rate (not guaranteed) |
| False named_accept spike | abort |

## Abort

Restore `manifest.json.bak.*` or set `"status": "inactive"`, recreate container, `make verify`.

## Do not

- Set `status: active` / `canary_share: 1` without 24h canary
- Commit `app/data/site_adapter/` to git
