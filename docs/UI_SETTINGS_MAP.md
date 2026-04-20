# UI settings map (Library → Settings → System)

[Русский](./UI_SETTINGS_MAP.ru.md)

Single-page map of **where** operator and admin tasks live in the Hub UI. Deep links use hash fragments where supported.

| Area | Route / entry | What you change |
|------|-----------------|-----------------|
| **Library** | `/timeline` (clips, review, exports) | Browse recordings; filters; CSV/PDF flows — not global stack config. |
| **Settings** (admin) | `/settings` | YAML-backed hub + processor tuning. Sections are accordions: **General**, **Connections**, **Capture & Feeder**, **Integrations**, **Processor & Detection**, etc. |
| **Processor & Detection** | `/settings#processor-weights` or `/settings#processor-models` | Scrolls/opens the Processor accordion; anchors `#processor-weights` / `#processor-models` target weights blocks inside Settings (not a separate route). |
| **System** | `/system` | Readiness, **config audit** (`GET /api/ui/system/config-audit`), catalog repair, processor weights status, diagnostics cards. |
| **Live** | `/live` | Streams and overlays — runtime, not persistent YAML. |
| **Migration / species** | `/migration-calendar` | Region comparison, species tooling linked from Overview. |

## Cross-links

- Release smoke checklist: [Definition of Done](./DEFINITION_OF_DONE.md).
- Operator playbooks (slow frames, Frigate, logs): [RUNBOOKS](./RUNBOOKS.md).
- Full config keys: [CONFIGURATION](./CONFIGURATION.md).
- Triggers / merge / Frigate overlap (inventory): [CONFIGURATION_TRIGGERS_INVENTORY](./CONFIGURATION_TRIGGERS_INVENTORY.md).

## Related GitHub tracking

Planning epic: [BirdLense-Hub#325](https://github.com/Gfermoto/BirdLense-Hub/issues/325) (product DoD + UI map).
