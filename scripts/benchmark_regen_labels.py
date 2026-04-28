"""Gold labels sidecar for ``benchmark-track-regen.py`` (#372).

Схема JSON (``schema_version``: ``1``):

```json
{
  "schema_version": 1,
  "gold_by_basename": {
    "clip.mp4": ["Eurasian Blue Tit", "Great Tit"]
  }
}
```

Ключи — **basename** файла (как ``os.path.basename`` для ``--video``).
Значения — списки ожидаемых имён видов (как у fused после классификатора).
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping


def load_gold_by_basename(path: str) -> dict[str, list[str]]:
    """Загрузить и проверить sidecar; вернуть карту basename → список видов."""
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    ver = data.get('schema_version', 1)
    if ver != 1:
        raise ValueError(
            f'Unsupported labels schema_version: {ver!r} (expected 1)',
        )
    raw = data.get('gold_by_basename')
    if raw is None:
        raise ValueError('labels JSON: missing gold_by_basename')
    if not isinstance(raw, Mapping):
        raise ValueError('labels JSON: gold_by_basename must be an object')
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if isinstance(v, list):
            out[key] = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(v, str):
            s = v.strip()
            out[key] = [s] if s else []
        else:
            raise ValueError(f'labels JSON: invalid gold list for {key!r}')
    return out


def eval_video_against_gold(
    gold_map: Mapping[str, list[str]],
    video_path: str,
    fused_tracks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Сравнить уникальные виды из fused-треков с gold для basename ролика.

    Возвращает ``None``, если для этого basename нет записи в ``gold_map``.
    """
    base = os.path.basename(video_path)
    gold = gold_map.get(base)
    if gold is None:
        return None
    pred_names: list[str] = []
    for t in fused_tracks:
        sn = t.get('species_name')
        if sn:
            pred_names.append(str(sn).strip())
    pred_unique = sorted(set(pred_names))
    gold_set = set(gold)
    pred_set = set(pred_unique)
    matched = gold_set & pred_set
    return {
        'video_basename': base,
        'gold_species': gold,
        'predicted_species_unique': pred_unique,
        'missing_vs_gold': sorted(gold_set - pred_set),
        'extra_vs_gold': sorted(pred_set - gold_set),
        'gold_species_recall': (
            len(matched) / len(gold_set) if gold_set else None
        ),
    }
