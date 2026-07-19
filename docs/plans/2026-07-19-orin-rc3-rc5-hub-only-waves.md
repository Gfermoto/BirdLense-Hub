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

## Done (loop 4 — finish pass)
13. **RC2 scaffold** — `async_classify_patch.py` + `processor.async_classify_patch_enabled` (default off); enqueue after persist
14. **RC4 protocols** — `recognition_protocols.py` (`TriggerSource` / `BoxProvider` / `SpeciesHint` / `SpeciesAuthority`)
15. **RC6 harvest** — wider candidate pool for curate (`limit*20`, conf≥0.45)

## Done (loop 5 — dig)
16. **RC2 enrich** — create_video returns `detections[{id,track_id,species_id}]`;
    `PATCH /api/processor/videos/<id>/detections/<det>`;
    `apply_processor_species_enrich` (no `manually_corrected`);
    async worker patches named leftovers via track map

## Done (loop 6 — dig reclassify)
17. **RC2 reclassify** — async worker second-budget Birder on leftover tracks
    (`track_ids` / runtime overrides in `enrich_tracks_classifier_at_finalize`);
    fills `patch_species_name` → enrich PATCH. Flag still default off.

## Done (loop 6b — adapters)
18. **RC4 adapters** — `recognition_adapters.py` (OpenCV trigger, Hub YOLO boxes,
    Frigate hint, Hub authority)

## Remaining (ops / deeper dig)
- Broader multi-species pack on Orin (model/data ceiling ~2 named offline)
- Enable async patch on Orin canary + measure GPU contention
- Wire adapters into bootstrap / session_summary
- Full PresenceRecorder/SpeciesRecognizer service classes (beyond facades)
