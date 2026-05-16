# BirdLense Hub — Overview

**BirdLense Hub** is open-source software for **bird monitoring at feeders, gardens, and field stations**: it detects birds and rodents on video, classifies species with on-device ML, records clips, and ties visits into a structured timeline for operators, ornithology, and citizen science.

[Русский](../ru/overview.ru.md)

---

## Why it exists

- **Privacy-first:** processing runs on **your** machine (Docker). No vendor cloud for core recognition.
- **Works with gear you already use:** [Go2RTC](https://github.com/AlexxIT/go2rtc) for streams, optional [Frigate](https://frigate.video/) + Bird Classification, [BirdNET](https://birdnet.cornell.edu/) over MQTT, Home Assistant, Telegram.
- **Citizen science friendly:** exports to **eBird** and **iNaturalist**, regional comparisons, dataset tools for retraining.

---

## Who it’s for

| Audience | Start here |
|----------|------------|
| **Observers & ringers** | [INSTALL](./install.md) → [SCENARIOS](./scenarios.md) — reliable counts, exports (eBird, CSV), review of uncertain IDs |
| **Researchers & stations** | [CONFIGURATION](./configuration.md), [DATASETS](../contributor/datasets.md), [TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.md) — catalogs, dataset export, custom weights |
| **Frigate / Home Assistant user** | [SCENARIOS](./scenarios.md) (Frigate + MQTT), [CONFIGURATION](./configuration.md) |
| **Developer / contributor** | [LOCAL_DEV](../contributor/local-dev.md), [Contributing](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CONTRIBUTING.md), [ARCHITECTURE](../contributor/architecture.md) |
| **Writer / advocate** | This page + [FEATURES](./features.md) — factual bullets for articles and landing copy |

---

## What runs where

- **One container** bundles nginx, the web API (Flask), optional MCP, and the **processor** (video pipeline, YOLO, ByteTrack, FFmpeg, MQTT client).
- **Outside the container:** Go2RTC (recommended), MQTT broker, optional Frigate, BirdNET-Pi/Go, ESPHome/Tasmota for feeders and sensors.

See the diagram and data paths in [ARCHITECTURE](../contributor/architecture.md).

---

## Recognition stack (short)

- **Detector + classifier** (YOLO family): bird/rodent in frame, then species. Default **EU-oriented** model (~491 species); US (NABirds) weights available — see [TRAINING](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/TRAINING.md).
- **Frigate** can supply **Bird Classification** `sub_label`; results merge with video ML.
- **BirdNET** audio events merge in a time window when MQTT is configured.

---

## Documentation map

| Need | Document |
|------|----------|
| Install & deploy | [INSTALL](./install.md) |
| “How do I set up X?” | [SCENARIOS](./scenarios.md) |
| Every knob in YAML/UI | [CONFIGURATION](./configuration.md) |
| Terminology | [GLOSSARY](./glossary.md) |
| Feature matrix & API hints | [FEATURES](./features.md) |
| Something broke | [TROUBLESHOOTING](./troubleshooting.md) |
| Tests & post-deploy checks | [TESTING](../contributor/testing.md) |
| CI policy & local full check (`make ci-local`) | [CI_AND_QUALITY](../contributor/ci-and-quality.md) |
| Full doc index | [docs/README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.md) |
| Static site section map | [SITE_MAP](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/SITE_MAP.md) |

**Machine-readable API:** [OpenAPI (YAML)](https://github.com/Gfermoto/BirdLense-Hub/blob/main/app/web/openapi.yaml).

---

## Building a site or blog from this repo

Use **this file** as the narrative “what & why”, **INSTALL** + **SCENARIOS** as getting-started chapters, **FEATURES** as a capability page, **ARCHITECTURE** for a technical deep dive. Conventions (placeholders, bilingual files): [Documentation](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/Documentation.md). Status of translations: [I18N_STATUS](https://github.com/Gfermoto/BirdLense-Hub/blob/main/archive/internal/docs-legacy/I18N_STATUS.md).

---

## Version

Current release line: see [root README](https://github.com/Gfermoto/BirdLense-Hub/blob/main/README.md) badge and [Changelog](https://github.com/Gfermoto/BirdLense-Hub/blob/main/CHANGELOG.md).
