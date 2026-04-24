"""Domain service layer for BirdLense Hub.

This package is intentionally broad, but refactoring work should keep new code
inside clear bounded contexts instead of extending the historical flat
collection of helpers forever.

Current primary domains:

- species_catalog
- timeline_visits
- settings_access_and_config
- system_diagnostics_and_jobs
- dataset_export
- notifications_and_integrations
- processor_ingest

Routes under ``app/web/routes`` should stay thin HTTP adapters and delegate
domain orchestration here.

URL → routes → services (фаза A #344): ``docs/project/WEB_SERVICES_DOMAIN_MAP.md``.
"""
