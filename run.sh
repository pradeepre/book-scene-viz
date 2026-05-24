#!/usr/bin/env bash
# Start the dev server using the project virtualenv (avoids missing pytesseract on system Python).
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
exec uvicorn app.main:app --reload --port 8000
