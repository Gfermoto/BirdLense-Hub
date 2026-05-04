# Configuration inventory — triggers, merge, Frigate/MQTT

[Русский](./CONFIGURATION_TRIGGERS_INVENTORY.ru.md)

Living notes to reduce **multiple sources of truth** between legacy keys, dotted YAML, and UI merge behaviour. For full key reference see [CONFIGURATION](./CONFIGURATION.md).

## Top overlaps (processor vs UI)

| Topic | Keys / surfaces | Notes |
|-------|-------------------|--------|
| Motion / capture source | Canonical **`triggers.*`** plus optional persisted migration from legacy **`motion:`** | Trigger blocks under **Settings → Capture & Feeder**. Processor reads merged config after fold; compare audit vs YAML export. |
| Frigate without YOLO | `detection.frigate_standalone_when_no_yolo` | When Frigate+MQTT drive detections and YOLO is intentionally off, standalone mode avoids empty fusion. Symptoms: ByteTrack / “0 YOLO tracks” warnings — see [RUNBOOKS](./RUNBOOKS.md) and **System → config audit** recall rows. |
| Boolean from YAML | String `"false"` vs boolean `false` | YAML can produce strings; audit uses normalisation helpers (`_bool_config` pattern in backend). If a value “won’t stick”, check type in exported YAML. |

## Docs / code alignment

- Fusion logic: `detection_fusion.py` (processor) should match what **config audit** and **Settings → Processor → Frigate fusion** describe.

Tracking: [BirdLense-Hub#329](https://github.com/Gfermoto/BirdLense-Hub/issues/329).
