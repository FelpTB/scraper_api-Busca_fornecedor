import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}
_BASE_PATH = Path(__file__).parent


def load_config(filename: str, *, use_cache: bool = True) -> Dict[str, Any]:
    """
    Carrega um arquivo JSON de configuração localizado em app/configs.
    
    Args:
        filename: Nome do arquivo (ex.: 'concurrency_config.json').
        use_cache: Se True, cacheia o conteúdo em memória.
    """
    if use_cache and filename in _CONFIG_CACHE:
        return _CONFIG_CACHE[filename]

    path = _BASE_PATH / filename
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if use_cache:
            _CONFIG_CACHE[filename] = data
        return data
    except FileNotFoundError:
        logger.warning(f"[config_loader] Arquivo não encontrado: {path}")
    except Exception as exc:
        logger.warning(f"[config_loader] Erro ao carregar {path}: {exc}")

    return {}


def get_section(filename: str, section: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retorna uma seção específica de um arquivo de config."""
    cfg = load_config(filename)
    return cfg.get(section, default or {})


def reset_cache() -> None:
    """Limpa o cache de arquivos carregados."""
    _CONFIG_CACHE.clear()
