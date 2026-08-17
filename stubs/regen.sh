#!/usr/bin/env bash
# Regenerate picogame-stubs/__init__.pyi from the engine bindings (a CircuitPython checkout with
# tools/extract_pyi.py). Usage: stubs/regen.sh /path/to/circuitpython
set -euo pipefail
CP="${1:?path to a circuitpython checkout}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
python3 "$CP/tools/extract_pyi.py" "$CP/shared-bindings/picogame" "$TMP"
cp "$TMP/__init__.pyi" "$HERE/picogame-stubs/__init__.pyi"
echo "regenerated $HERE/picogame-stubs/__init__.pyi ($(wc -l < "$HERE/picogame-stubs/__init__.pyi") lines)"
