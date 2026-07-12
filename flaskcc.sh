#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  flaskcc.sh  —  FlaskCode Client launcher (Linux / macOS)
#
#  Usage:
#    ./flaskcc.sh HOST@PORT [-p PASSWORD] [-u USERNAME]
#
#  If installed in PATH:
#    flaskcc HOST@PORT [-p PASSWORD]
# ─────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_PY="$SCRIPT_DIR/flaskcc.py"

# ── find python ───────────────────────────────────────────────
PYTHON=""
for candidate in python3 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "")
        if [[ "$ver" > "(3, 8)" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Error: Python 3.9+ is required but not found in PATH." >&2
    exit 1
fi

# ── check client script ────────────────────────────────────────
if [[ ! -f "$CLIENT_PY" ]]; then
    echo "Error: flaskcc.py not found at $CLIENT_PY" >&2
    exit 1
fi

# ── forward all args to the Python client ─────────────────────
exec "$PYTHON" "$CLIENT_PY" "$@"
