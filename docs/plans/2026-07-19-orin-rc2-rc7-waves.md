# Orin RC2→RC7 wave plan (2026-07-19)

Branch: `orin` · Base: critique `hub-recognition-software-critique.md` after `f7f43117`

## Done already
- RC1 Outcome hot path, named_share_hub = hub_taxonomy_win
- RC6 JSON species golden; RC3 salvage review-only; RC9 thin namespaces

## Waves (done 2026-07-19)
1. **RC2** ✅ `classify_skip_reason` deferred/budget/timeout/no_crop/unknown_abstain; stage classify_enrich
2. **RC3** ✅ schema documents linear/legacy/dual; legacy forced linear; dual test-only
3. **RC7** ✅ Birder honest argmax; Unknown-only → unknown_abstain
4. **RC6/RC9** ✅ `benchmarks/species_live_hub_only/` scaffold; critique progress notes
5. **Verify** — pytest + species golden + commit/push/deploy

## Non-goals / next loop
- SiteAdapter / LoRA finetune (Bet A)
- Live labeled mp4 pack + gate
- Delete dual DecisionMaker body
- detection_strategy split / Orin skip-gate removal
