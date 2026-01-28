"""
Configuração central. Variáveis de ambiente permitidas (whitelist Railway):
API_ACCESS_TOKEN, DATABASE_URL, LLM_URL, MODEL_NAME, SERPER_API_KEY.
Todas as demais configurações são derivadas ou valores padrão em código.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _build_base_v1(url: str) -> str:
    """
    Constrói BASE_V1 para API OpenAI-compatible (SGLang/vLLM).
    Regra: se url terminar com /v1 -> retorna url; senão -> url + '/v1'.
    Nunca produz /v1/v1.
    """
    if not url:
        return ""
    return url if url.endswith("/v1") else url.rstrip("/") + "/v1"


class Settings:
    # --- Whitelist: únicas variáveis de ambiente lidas do Railway ---
    API_ACCESS_TOKEN: str = os.getenv("API_ACCESS_TOKEN", "my-secret-token-dev")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    LLM_URL: str = os.getenv("LLM_URL", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "")
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")

    # --- Validação obrigatória ---
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL não configurada. Configure como variável de ambiente no Railway."
        )

    # --- Derivados de LLM_URL e MODEL_NAME (sem env adicionais) ---
    _llm_url_raw: str = LLM_URL or ""
    VLLM_BASE_URL: str = _build_base_v1(_llm_url_raw) if _llm_url_raw else ""
    VLLM_MODEL: str = MODEL_NAME or "Qwen/Qwen2.5-3B-Instruct"
    VLLM_API_KEY: str = "buscafornecedor"  # Padrão em código; SGLang frequentemente não exige key
    RUNPOD_BASE_URL: str = VLLM_BASE_URL
    RUNPOD_MODEL: str = VLLM_MODEL
    RUNPOD_API_KEY: str = "buscafornecedor"

    # --- Providers secundários: sem env, desabilitados (api_key vazio) ---
    GOOGLE_API_KEY: str = ""
    GOOGLE_MODEL: str = "gemini-2.0-flash"
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-4-1-fast-non-reasoning"
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-nano"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-lite-001"
    OPENROUTER_MODEL_2: str = "google/gemini-2.5-flash-lite"
    OPENROUTER_MODEL_3: str = "openai/gpt-4.1-nano"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # --- LLM fallback (lógica in-memory: Google > xAI > OpenAI) ---
    if GOOGLE_API_KEY:
        LLM_API_KEY: str = GOOGLE_API_KEY
        LLM_BASE_URL: str = GOOGLE_BASE_URL
        LLM_MODEL: str = GOOGLE_MODEL
    elif XAI_API_KEY:
        LLM_API_KEY: str = XAI_API_KEY
        LLM_BASE_URL: str = XAI_BASE_URL
        LLM_MODEL: str = XAI_MODEL
    else:
        LLM_API_KEY: str = OPENAI_API_KEY
        LLM_BASE_URL: str = OPENAI_BASE_URL
        LLM_MODEL: str = OPENAI_MODEL

    # --- Valores fixos (sem env) ---
    LLM_LINK_SELECTION_TIMEOUT: float = 30.0
    WEBSHARE_PROXY_LIST_URL: str = ""  # Proxy desabilitado quando vazio
    PHOENIX_COLLECTOR_URL: str = "https://arize-phoenix-buscafornecedor.up.railway.app"


settings = Settings()
