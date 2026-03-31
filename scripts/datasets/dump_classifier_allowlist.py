#!/usr/bin/env python3
"""
Выгрузить имена классов из YOLO classification (.pt) в текстовый allowlist для Hub.

Формат строк — как после нормализации процессора (пробелы вместо подчёркиваний),
совместимо с папками merged_cls «Scientific (Common)».

Зависимости: ultralytics (как в Docker-образе хаба или pip install -r app/processor/requirements.txt).

Примеры:
  python dump_classifier_allowlist.py /path/to/best.pt
  python dump_classifier_allowlist.py ../app/processor/models/classification/weights/best.pt \\
      -o ../app/processor/models/classification/weights/class_names.txt
"""
from __future__ import annotations

import argparse
from pathlib import Path


def normalize_classifier_label(name: str) -> str:
    """Как TwoStageStrategy._normalize_class_name в processor."""
    return str(name).replace('_OR_', '/').replace('_', ' ')


def main() -> None:
    p = argparse.ArgumentParser(description='Dump YOLO cls class names for BirdLense allowlist')
    p.add_argument('weights', type=Path, help='Path to best.pt (classification)')
    p.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        help='Output .txt (default: stdout)',
    )
    args = p.parse_args()
    if not args.weights.is_file():
        raise SystemExit(f'not a file: {args.weights}')

    from ultralytics import YOLO

    model = YOLO(str(args.weights), task='classify')
    names = model.names
    if isinstance(names, dict):
        def _ko(k):
            try:
                return int(k)
            except (TypeError, ValueError):
                return k

        raw = [str(names[k]) for k in sorted(names.keys(), key=_ko)]
    else:
        raw = [str(x) for x in names]

    lines = [normalize_classifier_label(x).strip() for x in raw if str(x).strip()]
    text = '\n'.join(lines) + ('\n' if lines else '')

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
        print(f'Wrote {len(lines)} classes to {args.output}')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
