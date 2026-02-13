#!/usr/bin/env python3
"""
Launcher de profile_workers por instância SGLang.
Lê app/configs/sglang_targets.json e, para cada instância, sobe N processos
profile_worker com SGLANG_BASE_URL, SGLANG_INSTANCE_NAME e SGLANG_WORKERS_GROUP.
Se o arquivo não existir ou instances estiver vazio, não sobe nenhum worker
(a chamada é feita pelo start_web_and_workers.sh que trata o fallback).
Uso: python scripts/run_profile_workers_by_sglang.py
"""
import os
import sys
import time
import subprocess

# Garantir que o project root está no path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

from app.services.concurrency_manager import load_sglang_targets


def _ensure_v1(url: str) -> str:
    if not url:
        return url
    return url if url.rstrip("/").endswith("/v1") else url.rstrip("/") + "/v1"


def _distribute_cap(total_requested: int, max_total: int, instance_workers: list) -> list:
    """Distribui max_total entre instâncias proporcionalmente (pelo menos 1 por instância quando caber)."""
    if total_requested <= 0 or max_total <= 0:
        return [0] * len(instance_workers)
    n = len(instance_workers)
    if n == 0:
        return []
    if max_total >= total_requested:
        return list(instance_workers)
    ratio = max_total / total_requested
    out = [max(1, int(w * ratio)) for w in instance_workers]
    remainder = max_total - sum(out)
    while remainder > 0:
        order = sorted(range(n), key=lambda i: -instance_workers[i])
        for i in order:
            if remainder <= 0:
                break
            if out[i] < instance_workers[i]:
                out[i] += 1
                remainder -= 1
    while sum(out) > max_total:
        i = max(range(n), key=lambda i: out[i])
        if out[i] <= 1:
            break
        out[i] -= 1
    return out


def main():
    """
    Retorna 0 se subiu pelo menos um worker (sglang_targets com instâncias).
    Retorna 1 se não subiu nenhum (fallback: start_web_and_workers.sh deve usar N_WORKERS).
    MAX_TOTAL_PROFILE_WORKERS: se definido, limita o total de profile workers (ex.: 8 no Railway).
    """
    instances = load_sglang_targets(use_cache=False)
    if not instances:
        return 1

    # Resolver workers por instância (só as que têm base_url e workers > 0)
    resolved = []
    for inst in instances:
        name = inst.get("name") or "default"
        base_url = (inst.get("base_url") or "").strip()
        workers = int(inst.get("workers") or 0)
        if not base_url or workers <= 0:
            continue
        resolved.append({"name": name, "base_url": _ensure_v1(base_url), "workers": workers})

    if not resolved:
        return 1

    requested_per = [r["workers"] for r in resolved]
    total_requested = sum(requested_per)
    max_total = int(os.environ.get("MAX_TOTAL_PROFILE_WORKERS", "0") or "0")
    if max_total > 0 and total_requested > max_total:
        workers_per = _distribute_cap(total_requested, max_total, requested_per)
        print(
            f"[start] MAX_TOTAL_PROFILE_WORKERS={max_total}: limitando de {total_requested} para {sum(workers_per)} profile_worker(s)",
            flush=True,
        )
    else:
        workers_per = requested_per

    stagger_sec = float(os.environ.get("STAGGER_PROFILE_SEC", "0.35") or "0.35")
    total = 0
    for r, workers in zip(resolved, workers_per):
        name, base_url = r["name"], r["base_url"]
        if workers <= 0:
            continue
        env = os.environ.copy()
        env["SGLANG_BASE_URL"] = base_url
        env["SGLANG_INSTANCE_NAME"] = name
        env["SGLANG_WORKERS_GROUP"] = str(workers)
        for i in range(workers):
            total += 1
            subprocess.Popen(
                [sys.executable, "-m", "app.workers.profile_worker"],
                env=env,
                cwd=_project_root,
                stdout=None,
                stderr=None,
            )
            if i < workers - 1 and stagger_sec > 0:
                time.sleep(stagger_sec)
        print(f"[start] Instância {name}: {workers} profile_worker(s) (base_url={base_url})", flush=True)
    if total:
        print(f"[start] Total: {total} profile_worker(s) por sglang_targets.json", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
