# BirdLense Hub — Overview

**BirdLense Hub** is open-source software for **smart bird feeder and garden monitoring**: it detects birds (and squirrels) on video, classifies species with on-device ML, records clips, and ties everything into a timeline you own.

[Русский](./OVERVIEW.ru.md)

---

## Why it exists

- **Privacy-first:** processing runs on **your** machine (Docker). No vendor cloud for core recognition.
- **Works with gear you already use:** [Go2RTC](https://github.com/AlexxIT/go2rtc) for streams, optional [Frigate](https://frigate.video/) + Bird Classification, [BirdNET](https://birdnet.cornell.edu/) over MQTT, Home Assistant, Telegram.
- **Citizen science friendly:** exports to **eBird** and **iNaturalist**, regional comparisons, dataset tools for retraining.

---

## Who it’s for

| Audience | Start here |
|----------|------------|
| **Home / nature enthusiast** | [INSTALL](./INSTALL.md) → [SCENARIOS](./SCENARIOS.md) |
| **Frigate / Home Assistant user** | [SCENARIOS](./SCENARIOS.md) (Frigate + MQTT), [CONFIGURATION](./CONFIGURATION.md) |
| **Developer / contributor** | [LOCAL_DEV](./LOCAL_DEV.md), [Contributing](./project/contributing.md), [ARCHITECTURE](./ARCHITECTURE.md) |
| **Writer / advocate** | This page + [FEATURES](./FEATURES.md) — factual bullets for articles and landing copy |

---

## What runs where

- **One container** bundles nginx, the web API (Flask), optional MCP, and the **processor** (video pipeline, YOLO, ByteTrack, FFmpeg, MQTT client).
- **Outside the container:** Go2RTC (recommended), MQTT broker, optional Frigate, BirdNET-Pi/Go, ESPHome/Tasmota for feeders and sensors.

See the diagram and data paths in [ARCHITECTURE](./ARCHITECTURE.md).

---

## Recognition stack (short)

- **Detector + classifier** (YOLO family): bird/squirrel in frame, then species. Default **EU-oriented** model (~491 species); US (NABirds) weights available — see [TRAINING](./TRAINING.md).
- **Frigate** can supply **Bird Classification** `sub_label`; results merge with video ML.
- **BirdNET** audio events merge in a time window when MQTT is configured.

---

## Documentation map

| Need | Document |
|------|----------|
| Install & deploy | [INSTALL](./INSTALL.md) |
| “How do I set up X?” | [SCENARIOS](./SCENARIOS.md) |
| Every knob in YAML/UI | [CONFIGURATION](./CONFIGURATION.md) |
| Terminology | [GLOSSARY](./GLOSSARY.md) |
| Feature matrix & API hints | [FEATURES](./FEATURES.md) |
| Something broke | [TROUBLESHOOTING](./TROUBLESHOOTING.md) |
| Tests & post-deploy checks | [TESTING](./TESTING.md) |
| Full doc index | [docs/README](./README.md) |
| Static site section map | [SITE_MAP](./SITE_MAP.md) |

**Machine-readable API:** [OpenAPI (YAML)](./project/openapi.md).

---

## Building a site or blog from this repo

Use **this file** as the narrative “what & why”, **INSTALL** + **SCENARIOS** as getting-started chapters, **FEATURES** as a capability page, **ARCHITECTURE** for a technical deep dive. Conventions (placeholders, bilingual files): [Documentation](./Documentation.md). Status of translations: [I18N_STATUS](./I18N_STATUS.md).

---

## Version

Current release line: see [root README](./project/root-readme.md) badge and [Changelog](./project/changelog.md).
