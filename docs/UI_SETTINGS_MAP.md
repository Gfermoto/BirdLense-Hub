# UI map (Recordings → Station → Service)

[Русский](./UI_SETTINGS_MAP.ru.md)

Single-page map of **where** user, contributor, and admin tasks live in the Hub UI. Deep links use hash fragments where supported.

| Area | Route / entry | What it is for |
|------|-----------------|----------------|
| **Recordings** | `/timeline` | Main day-by-day workflow: open clips, inspect detections, export reports. |
| **Review** | `/timeline?review=1` | Contributor/admin queue for uncertain detections and manual corrections. |
| **Species** | `/species` | Species directory for browsing birds seen by the station. |
| **Species seasonality** | `/migration-calendar` | Secondary seasonal view for species exploration. |
| **Station** (admin) | `/settings` | Outcome-based station setup: cameras, notifications, recognition, integrations. |
| **Service** (admin) | `/system` | Health, recognition improvement, diagnostics, and service-mode tooling. |
| **Data** (admin) | `/library` | Archive verification, dataset export, storage, replay, and archive maintenance. |
| **Live** | `/live` | Runtime streams and overlays, not persistent configuration. |

## Cross-links

- Release smoke checklist: [Definition of Done](./DEFINITION_OF_DONE.md).
- Canonical role and journey map: [UX canonical map](./UX_CANONICAL_MAP.md).
- Operator playbooks (slow frames, Frigate, logs): [RUNBOOKS](./RUNBOOKS.md).
- Full config keys: [CONFIGURATION](./CONFIGURATION.md).
- Triggers / merge / Frigate overlap (inventory): [CONFIGURATION_TRIGGERS_INVENTORY](./CONFIGURATION_TRIGGERS_INVENTORY.md).

## Related GitHub tracking

Planning epic: [BirdLense-Hub#325](https://github.com/Gfermoto/BirdLense-Hub/issues/325) (product DoD + UI map).
