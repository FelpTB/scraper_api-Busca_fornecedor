#!/bin/sh
# Sobe API + N discovery workers + N profile workers no mesmo container.
# Número de workers: N_WORKERS (default 2). Porta: PORT (default 8000).
set -e
PORT="${PORT:-8000}"
N_WORKERS="${N_WORKERS:-2}"

i=1
while [ "$i" -le "$N_WORKERS" ]; do
  echo "[start] Iniciando discovery_worker #$i em background..."
  python -m app.workers.discovery_worker &
  i=$((i + 1))
done

i=1
while [ "$i" -le "$N_WORKERS" ]; do
  echo "[start] Iniciando profile_worker #$i em background..."
  python -m app.workers.profile_worker &
  i=$((i + 1))
done

echo "[start] Workers: $N_WORKERS discovery, $N_WORKERS profile. Iniciando API..."
exec hypercorn app.main:app --bind "[::]:${PORT}"
