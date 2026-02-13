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


def main():
    """
    Retorna 0 se subiu pelo menos um worker (sglang_targets com instâncias).
    Retorna 1 se não subiu nenhum (fallback: start_web_and_workers.sh deve usar N_WORKERS).
    """
    instances = load_sglang_targets(use_cache=False)
    if not instances:
        return 1

    total = 0
    for inst in instances:
        name = inst.get("name") or "default"
        base_url = (inst.get("base_url") or "").strip()
        workers = int(inst.get("workers") or 0)
        if not base_url or workers <= 0:
            continue
        base_url = _ensure_v1(base_url)
        env = os.environ.copy()
        env["SGLANG_BASE_URL"] = base_url
        env["SGLANG_INSTANCE_NAME"] = name
        env["SGLANG_WORKERS_GROUP"] = str(workers)
        stagger_sec = float(os.environ.get("STAGGER_PROFILE_SEC", "0.2"))
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
