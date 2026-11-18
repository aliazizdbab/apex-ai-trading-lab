#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[APEX] Checking GitHub for latest updates..."
if command -v git >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1 || true
  git pull --ff-only origin main || true
fi

cd "$ROOT_DIR/backend"
if [ -x ".venv/bin/alembic" ]; then
  ".venv/bin/alembic" upgrade head
  ".venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 &
else
  python3 -m alembic upgrade head
  python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
fi

sleep 2
cd "$ROOT_DIR/frontend"
if [ -f "dist/index.html" ]; then
  npx vite preview --host 127.0.0.1 --port 5173 &
else
  npm run dev &
fi

sleep 2
open "http://127.0.0.1:5173" || true
wait
