# Orin RC3/RC4/RC5/RC6 residual waves (2026-07-19)

## Done
1. **RC3** — `decision_maker_legacy.py` quarantine; hot path `get_decisions` → linear; dual test-only
2. **RC4** — `tuning_role: hub_only` + `profiles/hub_only.example.yaml`
3. **RC5** — `site_adapter.py` manifest/canary + **species_priors apply** in linear classify
4. **RC6** — `make validate-species-live-hub-only` + runtime `--run-clips` / harvest script

## Orin live pack baseline (2026-07-19)

Harvest 4×5s clips (pigeon/fieldfare/great tit/sparrow).  
`SPECIES_LIVE_DOCKER=birdlense --run-clips` → **FAIL**: tracks/persist ok, `named_species=[]` (only Bird). Confirms RC6: live DB labels ≠ offline Hub classify.

## Next loop
- Curate clips / classify-first regen so named_accept can pass
- SiteAdapter weights file load into Birder (beyond priors)
- Delete dual test harness / rewrite legacy tests to linear
- Protocol unload of Frigate modules
