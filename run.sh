#!/usr/bin/env bash
# LINTO Starter Script
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export PYTHONPATH="$DIR/src:$PYTHONPATH"
exec "$DIR/.venv/bin/python3" -m linto "$@"
