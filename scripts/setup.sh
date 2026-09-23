#!/usr/bin/env bash
# Idempotent bootstrap for the Mappet monorepo (frontend + route engine).
# Safe to run repeatedly; installs/refreshes dependencies for both apps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Ensuring Python venv support"
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv || true
fi

echo "==> Installing frontend dependencies (apps/web)"
cd "$ROOT/apps/web"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi

echo "==> Installing route engine dependencies (services/engine)"
cd "$ROOT/services/engine"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "==> Setup complete."
