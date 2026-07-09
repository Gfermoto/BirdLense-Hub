#!/usr/bin/env bash
# Download Visual-WetlandBirds annotations from Zenodo (no 9GB videos.zip).
set -euo pipefail
ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
OUT="${OUT:-$ROOT/app/data/datasets/Visual-WetlandBirds/raw}"
BASE="https://zenodo.org/api/records/15696105/files"
mkdir -p "$OUT"
for f in crops.csv behaviors_ID.csv species_ID.csv splits.json; do
  echo "Downloading $f ..."
  curl -fsSL -o "$OUT/$f" "$BASE/$f/content"
done
echo "OK: $OUT"
ls -la "$OUT"
