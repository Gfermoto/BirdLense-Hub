#!/usr/bin/env bash
# Локальный прогон CodeQL (как в CI): Python app/web + UI после сборки.
# Требования: gh, unzip, Node 22+, Python 3.12+, ~1.5 ГБ на диск.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEQL_DIR="${CODEQL_DIR:-$ROOT/.tools/codeql}"
CODEQL_VERSION="${CODEQL_VERSION:-v2.25.0}"
DB_ROOT="$ROOT/.tools/codeql-dbs"
OUT="$ROOT/.tools/codeql-results"
mkdir -p "$DB_ROOT" "$OUT"

if [[ ! -x "$CODEQL_DIR/codeql" ]]; then
  echo "Скачивание CodeQL $CODEQL_VERSION в $CODEQL_DIR …"
  mkdir -p "$ROOT/.tools"
  (cd "$ROOT/.tools" && gh release download "$CODEQL_VERSION" -R github/codeql-cli-binaries -p codeql-linux64.zip \
    && unzip -q -o codeql-linux64.zip && rm -f codeql-linux64.zip)
fi

"$CODEQL_DIR/codeql" version
"$CODEQL_DIR/codeql" pack download codeql/python-queries
"$CODEQL_DIR/codeql" pack download codeql/javascript-queries

PY_PACK="$(echo "$HOME"/.codeql/packages/codeql/python-queries/*)"
JS_PACK="$(echo "$HOME"/.codeql/packages/codeql/javascript-queries/*)"

echo "=== Python: база app/web ==="
rm -rf "$DB_ROOT/python-web"
"$CODEQL_DIR/codeql" database create "$DB_ROOT/python-web" --language=python --build-mode=none \
  --source-root="$ROOT/app/web"

echo "=== Python: security-extended → SARIF ==="
"$CODEQL_DIR/codeql" database analyze "$DB_ROOT/python-web" --threads=0 --format=sarif-latest \
  --output="$OUT/python-web.sarif" "$PY_PACK/codeql-suites/python-security-extended.qls"

echo "=== JavaScript: база app/ui (npm ci && build) ==="
rm -rf "$DB_ROOT/javascript-ui"
(cd "$ROOT/app/ui" && "$CODEQL_DIR/codeql" database create "$DB_ROOT/javascript-ui" \
  --language=javascript --source-root="$ROOT/app/ui" --command="npm ci && npm run build")

echo "=== JavaScript: security-extended → SARIF ==="
"$CODEQL_DIR/codeql" database analyze "$DB_ROOT/javascript-ui" --threads=0 --format=sarif-latest \
  --output="$OUT/javascript-ui.sarif" "$JS_PACK/codeql-suites/javascript-security-extended.qls"

echo "=== Краткая сводка (кол-во findings в SARIF) ==="
python3 -c "
import json, pathlib
root = pathlib.Path('$OUT')
for name in ('python-web.sarif', 'javascript-ui.sarif'):
    p = root / name
    if not p.exists():
        print(name, '— нет файла')
        continue
    d = json.loads(p.read_text())
    n = len(d['runs'][0].get('results', []))
    print(f'{name}: {n} срабатываний')
"

echo "Готово. SARIF: $OUT/*.sarif — откройте в VS Code / Cursor (CodeQL: View SARIF)."
