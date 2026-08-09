#!/usr/bin/env bash
# Build one CodeQL database per language over the scanned tree and analyse it
# with the malicious-skill query pack.
#
#   run.sh <source-root> <output-dir>
#
# Writes <output-dir>/python.sarif and <output-dir>/javascript.sarif for every
# language that actually has source files.  Languages with no sources are
# skipped silently.

set -euo pipefail

SOURCE_ROOT="$1"
OUT_DIR="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
CODEQL="$HERE/codeql/codeql"
DB_DIR="$HERE/databases"

# the javascript/typescript extractor shells out to node
export PATH="$HERE/node/bin:$PATH"

mkdir -p "$OUT_DIR" "$DB_DIR"

analyse() {
  local lang="$1" name="$2" find_expr="$3"
  if [ -z "$(find "$SOURCE_ROOT" \( -name node_modules -o -name .git \) -prune -o -type f $find_expr -print -quit)" ]; then
    echo "codeql: no $name sources, skipping"
    return
  fi

  local db="$DB_DIR/$name" log="$OUT_DIR/$name.log"
  rm -rf "$db"
  echo "codeql: building $name database"
  "$CODEQL" database create "$db" \
    --language="$lang" --source-root="$SOURCE_ROOT" --overwrite --quiet >"$log" 2>&1 \
    || { tail -30 "$log" >&2; exit 1; }

  echo "codeql: analysing $name"
  "$CODEQL" database analyze "$db" "$HERE/queries/$name" \
    --format=sarif-latest --output="$OUT_DIR/$name.sarif" \
    --threads=0 --quiet >>"$log" 2>&1 \
    || { tail -30 "$log" >&2; exit 1; }
}

analyse python python '-name *.py'
analyse javascript-typescript javascript \
  '( -name *.js -o -name *.mjs -o -name *.cjs -o -name *.jsx -o -name *.ts -o -name *.tsx )'
