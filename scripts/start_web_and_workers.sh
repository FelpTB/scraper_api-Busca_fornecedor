#!/bin/sh
# Sobe API + workers no mesmo container (1 processo web em foreground, 2 workers em background).
# Útil quando o Railway (ou outro host) roda apenas um container.
set -e
PORT="${PORT:-8000}"

echo "[start] Iniciando discovery_worker em background..."
python -m app.workers.discovery_worker &
DISCOVERY_PID=$!

echo "[start] Iniciando profile_worker em background..."
python -m app.workers.profile_worker &
PROFILE_PID=$!

echo "[start] Workers em background (discovery PID=$DISCOVERY_PID, profile PID=$PROFILE_PID). Iniciando API..."
exec hypercorn app.main:app --bind "[::]:${PORT}"
