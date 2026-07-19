# Orin RC3/RC4/RC5/RC6 residual waves (2026-07-19)

## Done
1. **RC3** — `decision_maker_legacy.py` quarantine; hot path `get_decisions` → linear; dual test-only
2. **RC4** — `tuning_role: hub_only` + `profiles/hub_only.example.yaml`
3. **RC5** — `site_adapter.py` manifest/canary noop + feedback_loop KPI
4. **RC6** — `make validate-species-live-hub-only` (empty skip / REQUIRE_CLIPS strict)

## Next loop
- Live labeled mp4 clips + runtime eval
- SiteAdapter weights apply (Bet A)
- Delete dual test harness / rewrite legacy tests to linear
- Protocol unload of Frigate modules
