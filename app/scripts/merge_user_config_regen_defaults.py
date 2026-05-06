#!/usr/bin/env python3
"""Идемпотентно дописывает processor.track_regen_min_box_size_px в user_config на хабе.

Вызывается из deploy.sh через ``docker exec`` (после ``make start``). Rsync деплоя
``user_config.yaml`` не трогает — без этого шага на старом проде мог отсутствовать
ключ после обновления дефолтов в репо.

Пути весов по умолчанию в YAML — относительно ``processor/``; абсолютные в контейнере
вида ``/app/processor/models/...`` тоже допустимы — см. default_config / deploy rules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

UC = Path("/app/app_config/user_config.yaml")
KEY = "track_regen_min_box_size_px"
VALUE = 20


def main() -> int:
    if UC.exists():
        raw = UC.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            print("merge_user_config_regen: user_config root is not a dict — skip", file=sys.stderr)
            return 1
    else:
        data = {}

    proc = data.setdefault("processor", {})
    if not isinstance(proc, dict):
        print("merge_user_config_regen: processor is not a dict — skip", file=sys.stderr)
        return 1

    if KEY in proc:
        print(f"merge_user_config_regen: оставляем {KEY}={proc[KEY]!r}")
        return 0

    proc[KEY] = VALUE
    UC.parent.mkdir(parents=True, exist_ok=True)
    UC.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        ),
        encoding="utf-8",
    )
    print(f"merge_user_config_regen: записано {KEY}={VALUE} в {UC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
