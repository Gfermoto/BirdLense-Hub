# ADR: Classifier hints contract (external metadata)

**Status:** accepted  
**Date:** 2026-06-10  
**Issues:** [#634](https://github.com/Gfermoto/BirdLense-Hub/issues/634)  
**Related:** [#635](https://github.com/Gfermoto/BirdLense-Hub/issues/635) recording gate, [linear-fusion-safeguards.md](../contributor/linear-fusion-safeguards.md), [wave1_processor.md](consortium/wave1_processor.md)  
**Incident:** [a656199a](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057) — detect-first blind lores + ByteTrack zone merge; partial fix [`2ff464057`](https://github.com/Gfermoto/BirdLense-Hub/commit/2ff464057) (raw-hits anchor, native lores aspect). Wave 1 removes **recording gate**, not anchor quality work.

---

## Context

BirdLense ingests several **external** signals alongside on-device YOLO + ByteTrack:

| Source | Transport / config | Today (pre-Wave 1) |
|--------|-------------------|---------------------|
| Frigate MQTT | `mqtt_aggregator`, Frigate events | Recording gate assist, salvage, standalone rows, activity hold |
| BirdNET MQTT | `birdnet/sightings`, FIFO persist | Confidence bias, fusion prior, species merge |
| eBird regional top | `ebird_regional_confidence.py`, API key | `species_confidence_overrides` thresholds |
| Multicam metadata | `processor.multi_camera_groups`, `multi_camera_confidence.py` | Cross-camera confidence boost in fusion |

YOLO on the **detect substream** and FFmpeg on the **main stream** are the primary motion/recording path. External metadata must not block or replace that path.

**Hardware constraint (Wave 1):** Intel CPU + iGPU (OpenVINO `intel:gpu`). No Coral/CUDA assumptions in processor contracts.

---

## Decision

1. **Classifier hints only:** Frigate MQTT, BirdNET, eBird regional metadata, and multicam group metadata are **hints to classifier and scoring** — confidence bias, species priors, fusion weighting, arbitration tie-breaks.
2. **MUST NOT gate:**
   - Motion/trigger → main-stream recording start (`processor.recording_gate_mode`, #635)
   - Detect-first lores anchor requirement (legacy `detect_first` mode only when explicitly opted in)
   - Primary fusion persist driver (YOLO + ByteTrack rows remain primary in linear/standalone-first)
3. **Recording default:** `processor.recording_gate_mode: motion_immediate` — OpenCV/Frigate/motion trigger starts hires recording; YOLO runs **inside** the session (Frigate-like). `detect_first` remains for rollback.
4. **Frigate as trigger vs hint:** Frigate may **trigger** a recording (motion/event path) but Frigate bbox/species must not **substitute** for a missing lores YOLO anchor when `recording_gate_mode: motion_immediate`.

---

## Migration — code paths to demote

Paths that currently elevate external metadata beyond hints. Wave 1+ demotes or gates behind explicit opt-in / legacy mode.

| Path | Module | Current role | Target |
|------|--------|--------------|--------|
| `build_frigate_assisted_detect_first_anchor` | `detect_first.py` | Synthetic lores anchor from Frigate bbox when YOLO missed | **Demote:** only when `recording_gate_mode: detect_first` + `detect_first_frigate_assist_enabled` |
| `detect_first_frigate_assist_*` config | `default_config.yaml`, settings | Enables Frigate-as-anchor | **Legacy opt-in** under `detect_first` gate mode |
| `requires_detect_first_before_record` | `detection_scheduler.py` | Blocks main FFmpeg until lores anchor | **Off** when `recording_gate_mode: motion_immediate` (#635) |
| `frigate_salvage_opted_in` / `linear_skip_frigate_salvage_paths` | `linear_pipeline.py`, `recording_finalize.py` | Frigate-only persist salvage | **Hint-only default;** salvage stays opt-in (`tuning_role: frigate_site`) |
| `frigate_trigger_salvage` / weak salvage | `recording_finalize_parts/salvage.py` | Post-hoc Frigate rows without YOLO | **Opt-in** only; not default persist driver |
| `_frigate_standalone_prepared_rows` | `detection_fusion.py` | Synthetic visit rows from Frigate without YOLO | **Classifier hint / review-only** unless `frigate_standalone_when_no_yolo` explicitly enabled |
| `merge_birdnet_mqtt_bias_into_overrides` | `birdnet_mqtt_confidence.py`, `recording_session.py` | Session threshold bias | **Keep** as hint (already pre-decision) |
| `_aggregate_birdnet_scores` / `_birdnet_prior` | `detection_fusion.py` | Fusion confidence prior | **Keep** as hint |
| `merge_species_confidence_overrides_with_ebird_top` | `ebird_regional_confidence.py` | Lower species thresholds | **Keep** as hint |
| `apply_multi_camera_confidence_boost` | `multi_camera_confidence.py` | Cross-cam fusion boost | **Keep** as hint |
| `trigger_graph` `detect_first_ok` gate | `trigger_graph.py` | Suppresses nodes without detect-first | **Demote:** diagnostic only under `motion_immediate` |
| `frigate_activity_hold_seconds` | `recording_session.py` | Extends clip on Frigate MQTT | **Session extension hint** — must not be sole start condition |

**Invariants (do not break during migration):**

- Dual-stream detect/main (`media_runtime.py`, `go2rtc_stream_source.py`)
- Bbox remap detector → overlay → playback (`frame_geometry.py`, `playback_geometry.py`)
- `single_rtsp_read: false` during recording
- OpenVINO paths on Intel iGPU

---

## Consequences

**Positive**

- Recording starts on motion like Frigate/NVR; fewer missed clips when lores YOLO is slow or blind.
- Clear contract for operators: external integrations tune confidence, not the record button.
- Rollback: `recording_gate_mode: detect_first` restores pre-Wave-1 gate behavior.

**Negative**

- More empty or generic-only clips until in-session YOLO catches up — mitigated by `min_seconds_between_recordings`, moratorium, finalize filters.
- Sites relying on Frigate-as-anchor must set `detect_first` gate mode explicitly.

---

## Verification

| Check | How |
|-------|-----|
| ADR published | This file + `docs/ru/adr-classifier-hints-only.ru.md` |
| Default gate mode | `default_config.yaml`: `recording_gate_mode: motion_immediate` |
| Detect-first rollback | `recording_gate_mode: detect_first` + existing detect_first keys |
| Unit test | BirdBox mock: trigger fires, lores hits=0 → `run()` still called |
| Processor light CI | `make test-processor-light` on changed tests |

---

## Revisit when

- #635 deploy verified on VPS/LAN with OpenVINO `intel:gpu`
- Golden clips show regression in bbox remap or dual-stream timeline
- Consortium Wave 2 fusion simplification (#601 children)
