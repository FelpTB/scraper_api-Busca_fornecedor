#!/bin/sh
# Sobe API + N discovery workers + N profile workers no mesmo container.
# Número de workers: N_WORKERS (default 2). Porta: PORT (default 8000).
# Regra: (processos × DATABASE_POOL_MAX_SIZE) < max_connections do PostgreSQL (ex.: Railway 100).
# No Railway: defina MAX_TOTAL_PROFILE_WORKERS=4 ou 8 e opcionalmente DATABASE_POOL_MAX_SIZE=2.
set -e
# Evitar que OpenBLAS/OpenMP criem dezenas de threads por processo (Railway tem limite de threads).
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
PORT="${PORT:-8000}"
N_WORKERS="${N_WORKERS:-2}"

# Escalonar subida para evitar pico de conexões ao PostgreSQL (thundering herd)
STAGGER_DISCOVERY="${STAGGER_DISCOVERY_SEC:-0.2}"
STAGGER_PROFILE="${STAGGER_PROFILE_SEC:-0.2}"
i=1
while [ "$i" -le "$N_WORKERS" ]; do
  echo "[start] Iniciando discovery_worker #$i em background..."
  python -m app.workers.discovery_worker &
  i=$((i + 1))
  [ "$i" -le "$N_WORKERS" ] && sleep "$STAGGER_DISCOVERY" 2>/dev/null || true
done

# Profile workers: por instância SGLang (sglang_targets.json) ou N_WORKERS genérico
if python scripts/run_profile_workers_by_sglang.py; then
  echo "[start] Profile workers iniciados via sglang_targets.json"
else
  i=1
  while [ "$i" -le "$N_WORKERS" ]; do
    echo "[start] Iniciando profile_worker #$i em background..."
    python -m app.workers.profile_worker &
    i=$((i + 1))
    [ "$i" -le "$N_WORKERS" ] && sleep "$STAGGER_PROFILE" 2>/dev/null || true
  done
  echo "[start] Workers: $N_WORKERS discovery, $N_WORKERS profile"
fi

echo "[start] Iniciando API..."
exec hypercorn app.main:app --bind "[::]:${PORT}"
