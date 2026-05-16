#!/usr/bin/env bash
set -euo pipefail

# Run detector SOTA matrix from scripts/sota_detector_matrix.yaml.
# Requires Python env with ultralytics + pyyaml.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MATRIX_FILE="${1:-${ROOT_DIR}/scripts/sota_detector_matrix.yaml}"

if [[ ! -f "${MATRIX_FILE}" ]]; then
  echo "ERROR: matrix file not found: ${MATRIX_FILE}" >&2
  exit 2
fi

python3 - "${MATRIX_FILE}" <<'PY'
import json
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

matrix_path = Path(sys.argv[1]).resolve()
root = matrix_path.parent.parent
cfg = yaml.safe_load(matrix_path.read_text(encoding='utf-8')) or {}
defaults = cfg.get('defaults') or {}
dataset_yaml = str(cfg.get('dataset_yaml') or '').strip()
if not dataset_yaml:
    raise SystemExit('dataset_yaml is required in matrix file')
experiments = cfg.get('experiments') or []
if not experiments:
    raise SystemExit('experiments list is empty')

project = str(defaults.get('project') or 'runs/detect-sota')
project_path = root / project
project_path.mkdir(parents=True, exist_ok=True)

def build_cmd(exp: dict) -> list[str]:
    exp_id = str(exp.get('id') or '').strip()
    model = str(exp.get('model') or '').strip()
    if not exp_id or not model:
        raise SystemExit(f'invalid experiment entry: {exp!r}')
    return [
        'yolo',
        'task=detect',
        'mode=train',
        f'model={model}',
        f'data={dataset_yaml}',
        f'name={exp_id}',
        f'project={project}',
        f'imgsz={int(defaults.get("imgsz", 960))}',
        f'epochs={int(defaults.get("epochs", 80))}',
        f'patience={int(defaults.get("patience", 20))}',
        f'batch={int(defaults.get("batch", 16))}',
        f'seed={int(defaults.get("seed", 42))}',
        f'optimizer={defaults.get("optimizer", "AdamW")}',
        f'cos_lr={str(bool(defaults.get("cos_lr", True))).lower()}',
        f'close_mosaic={int(defaults.get("close_mosaic", 10))}',
        f'warmup_epochs={int(defaults.get("warmup_epochs", 3))}',
    ]

for exp in experiments:
    cmd = build_cmd(exp)
    print(json.dumps({'run': exp.get('id'), 'cmd': ' '.join(shlex.quote(x) for x in cmd)}, ensure_ascii=False))
    subprocess.run(cmd, check=True, cwd=root)
PY
