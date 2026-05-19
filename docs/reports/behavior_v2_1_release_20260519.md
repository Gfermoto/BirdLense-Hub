# Behavior v2.1 — Release & Go/No-Go (2026-05-19)

## Summary

| | v2 (hub-only) | v2.1 (hub + WetlandBirds) |
|---|---------------|---------------------------|
| `flying` train tracklets | 4 | **100** |
| Holdout Macro-F1 | 0.44 | 0.37 |
| Holdout `flying` correct | 0 | **9/9** |
| Canary replay discrepancy | ~31% (13 clips) | **39.1%** (23 clips) |
| Video `flying` predictions | rare | **6** / 23 |
| Production `engine` | canary | **auto** |

**Было:** модель не видела полёт. **Стало:** flying в обучении и в runtime; discrepancy слегка выше из‑за нового класса, но **<50%** и без крашей.

## Validation (Этап 1)

- Config: `video_v2_1`, OpenVINO `behavior_v2_1_openvino` — OK
- Offline replay: `/app/data/datasets/behavior_v2_1/canary_replay_v21.json`
- Daylight 2h monitor: мало новых видео (0 sessions с треками) — птицы неактивны; решение по replay + holdout

### Canary replay v2.1

```
n_videos: 23
discrepancy_rate: 0.3913
label_pairs: flying|feeding: 7, feeding|flying: 2
flying video_label: 6
flying meta_label: 11
```

## Go/No-Go → **GO**

| Критерий | Статус |
|----------|--------|
| `flying` детектируется | ✅ 6 video + holdout 9/9 |
| Discrepancy < 50% | ✅ 39.1% |
| Discrepancy < 35% | ⚠️ 39.1% (допустимо по policy v2.1) |
| FP flying массово | ❌ нет (2× feeding→flying) |
| Инференс / краши | ✅ IR загружается |

## Этап 3 — Applied

```bash
# VPS 2026-05-19T12:27Z
scripts/user-config-behavior-auto-v2_1.partial.yaml → user_config.yaml
engine: auto
docker compose restart birdlense
```

## Follow-up (24h)

- Мониторить `behavior_label` / логи finalize
- При discrepancy >50% за сутки — откат на `user-config-behavior-canary-v2_1.partial.yaml`
- Следующий шаг качества: real RGB crops из Zenodo `videos.zip`, больше hub `flying` с треками

## Issues

- #476 — closed (WetlandBirds + merge)
- #460 — closed (auto rollout v2.1)
- #451 — reliability note (blind fixes + better behavior model)
