#!/bin/sh
# Sobe API + N discovery workers + M profile workers no mesmo container.
# Variáveis: DISCOVERY_WORKERS (default 2), PROFILE_WORKERS (default 2), PORT (default 8000).
set -e
PORT="${PORT:-8000}"
DISCOVERY_WORKERS="${DISCOVERY_WORKERS:-2}"
PROFILE_WORKERS="${PROFILE_WORKERS:-2}"

i=1
while [ "$i" -le "$DISCOVERY_WORKERS" ]; do
  echo "[start] Iniciando discovery_worker #$i em background..."
  python -m app.workers.discovery_worker &
  i=$((i + 1))
done

i=1
while [ "$i" -le "$PROFILE_WORKERS" ]; do
  echo "[start] Iniciando profile_worker #$i em background..."
  python -m app.workers.profile_worker &
  i=$((i + 1))
done

echo "[start] Workers: $DISCOVERY_WORKERS discovery, $PROFILE_WORKERS profile. Iniciando API..."
exec hypercorn app.main:app --bind "[::]:${PORT}"
