# Orin RC3/RC4/RC5/RC6 residual waves (2026-07-19)

## Done
1. **RC3** — `decision_maker_legacy.py` quarantine; hot path `get_decisions` → linear; dual test-only
2. **RC4** — `tuning_role: hub_only` + `profiles/hub_only.example.yaml`
3. **RC5** — `site_adapter.py` manifest/canary + **species_priors apply** in linear classify
4. **RC6** — `make validate-species-live-hub-only` + runtime `--run-clips` / harvest script

## Orin live pack baseline (2026-07-19)

Harvest 4×5s clips (pigeon/fieldfare/great tit/sparrow).  
`SPECIES_LIVE_DOCKER=birdlense --run-clips` → **FAIL**: tracks/persist ok, `named_species=[]` (only Bird). Confirms RC6: live DB labels ≠ offline Hub classify.

## Done (loop 2)
5. **RC3 delete** — `decision_maker_legacy.py` removed; dual→linear coerce; tests rewritten
6. **RC4 unload** — bootstrap skips Frigate MQTT when trigger+scales off; hub_only profile + assist off
7. **RC5 weights** — `resolve_site_adapter_weights_path` → Birder ONNX when active
8. **RC6 classify-first regen** — `track_regenerator` calls `enrich_tracks_classifier_at_finalize`
9. **RC9** — `session_summary.reliability.*` namespace

## Orin live pack (verified)

Full-clip Common Wood Pigeon → `PASS species-live-hub-only (clips=1 mode=runtime)`  
with classify-first regen. Short cuts → Unknown; use `--copy-full`.

## Done (loop 3)
10. **RC1 facades** — `presence_recorder.py` / `species_recognizer.py` wire into session_summary
11. **RC8** — `profiles/feeder_install.example.yaml`; feeder roles marked install-physics in defaults
12. **RC6 curate** — `scripts/curate_species_live_pack.py` (offline named_accept keep)

## Remaining
- Broader multi-species pack (run curate on Orin)
- Full PresenceRecorder/SpeciesRecognizer service split (async classify)
