import os

class Settings:
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    
    # LLM Settings
    # 1. Primary: Google Native
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = "gemini-2.0-flash"
    GOOGLE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # 2. Secondary: xAI Native
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    XAI_MODEL: str = "grok-2-vision-1212" # Or grok-beta
    XAI_BASE_URL: str = "https://api.x.ai/v1"

    # 3. Tertiary: OpenRouter
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Logic to select provider (Priority: Google > xAI > OpenRouter)
    if GOOGLE_API_KEY:
        LLM_API_KEY: str = GOOGLE_API_KEY
        LLM_BASE_URL: str = GOOGLE_BASE_URL
        LLM_MODEL: str = GOOGLE_MODEL
    elif XAI_API_KEY:
        LLM_API_KEY: str = XAI_API_KEY
        LLM_BASE_URL: str = XAI_BASE_URL
        LLM_MODEL: str = XAI_MODEL
    else:
        LLM_API_KEY: str = OPENROUTER_API_KEY
        LLM_BASE_URL: str = OPENROUTER_BASE_URL
        LLM_MODEL: str = OPENROUTER_MODEL
    
    # Security
    API_ACCESS_TOKEN: str = os.getenv("API_ACCESS_TOKEN", "my-secret-token-dev")

    WEBSHARE_PROXY_LIST_URL: str = os.getenv(
        "WEBSHARE_PROXY_LIST_URL", 
        "https://proxy.webshare.io/api/v2/proxy/list/download/rxcoovfjvlksjgkmpytxglhsdioqvpleggyqllve/-/any/username/direct/-/?plan_id=12303950"
    )

settings = Settings()
