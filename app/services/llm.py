import json
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import logging
import json_repair
from app.core.config import settings
from app.schemas.profile import CompanyProfile

# Configurar logger
logger = logging.getLogger(__name__)

# Prepare client args based on provider
client_args = {
    "api_key": settings.LLM_API_KEY,
    "base_url": settings.LLM_BASE_URL,
}

# Only add OpenRouter-specific headers if using OpenRouter
if "openrouter.ai" in settings.LLM_BASE_URL:
    client_args["default_headers"] = {
        "HTTP-Referer": "https://github.com/waltagan/busca_fornecedo_crawl",
        "X-Title": "B2B Flash Profiler",
    }

client = AsyncOpenAI(**client_args)

SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Gere estritamente um JSON válido correspondente ao schema abaixo.
Extraia dados do texto Markdown e PDF fornecido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA DE SAÍDA: PORTUGUÊS (BRASIL). Todo o conteúdo extraído deve estar em Português. Traduza descrições, cargos e categorias. Mantenha em inglês apenas termos técnicos globais (ex: "SaaS", "Big Data", "Machine Learning") ou nomes próprios de produtos não traduzíveis.
2. PRODUTOS vs SERVIÇOS: Distinga claramente entre produtos físicos e serviços intangíveis.
3. DETALHES DO SERVIÇO: Para os principais serviços, tente extrair 'metodologia' (como eles fazem) e 'entregáveis' (o que o cliente recebe).
4. LISTAGEM DE PRODUTOS EXAUSTIVA: Ao extrair 'product_categories', liste TODOS os produtos individuais encontrados dentro de cada categoria. NÃO RESUMA (ex: não use "Luminárias diversas", use "Luminárias High Bay", "Luminárias Herméticas", "Refletores", etc). Seja o mais específico e completo possível na lista de 'items'.
5. PROVA SOCIAL: Extraia Estudos de Caso específicos, Nomes de Clientes e Certificações. Estes são de alta prioridade.
6. ENGAJAMENTO: Procure como eles vendem (Mensalidade? Por Projeto? Alocação de equipe?).

Se um campo não for encontrado, use null ou lista vazia. NÃO gere blocos de código markdown (```json). Gere APENAS a string JSON bruta.

Schema (Mantenha as chaves em inglês, valores em Português):
{
  "identity": { 
    "company_name": "string", 
    "cnpj": "string",
    "tagline": "string", 
    "description": "string", 
    "founding_year": "string",
    "employee_count_range": "string"
  },
  "classification": { 
    "industry": "string", 
    "business_model": "string", 
    "target_audience": "string",
    "geographic_coverage": "string"
  },
  "team": {
    "size_range": "string",
    "key_roles": ["string"],
    "team_certifications": ["string"]
  },
  "offerings": { 
    "products": ["string"],
    "product_categories": [
        { "category_name": "string", "items": ["string"] }
    ],
    "services": ["string"], 
    "service_details": [
        { 
          "name": "string", 
          "description": "string", 
          "methodology": "string", 
          "deliverables": ["string"],
          "ideal_client_profile": "string"
        }
    ],
    "engagement_models": ["string"],
    "key_differentiators": ["string"] 
  },
  "reputation": {
    "certifications": ["string"],
    "awards": ["string"],
    "partnerships": ["string"],
    "client_list": ["string"],
    "case_studies": [
        {
          "title": "string",
          "client_name": "string",
          "industry": "string",
          "challenge": "string",
          "solution": "string",
          "outcome": "string"
        }
    ]
  },
  "contact": { 
    "emails": ["string"], 
    "phones": ["string"], 
    "linkedin_url": "string", 
    "website_url": "string",
    "headquarters_address": "string",
    "locations": ["string"]
  }
}
"""

@retry(
    retry=retry_if_exception_type((RateLimitError, APIError, APITimeoutError)),
    wait=wait_exponential(multiplier=1, min=2, max=60), # Wait 2s, 4s, 8s... up to 60s
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def analyze_content(text_content: str) -> CompanyProfile:
    """
    Sends the accumulated text content to the LLM and parses the JSON response into a CompanyProfile.
    Uses Tenacity for robust retries on Rate Limits and API Errors.
    """
    # Note: We removed the generic try/except block. 
    # Let specific errors propagate or be handled by the retry decorator.
    # If all retries fail, the exception will bubble up to the main handler.
    
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analise este conteúdo e extraia os dados em Português:\n\n{text_content}"}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    raw_content = response.choices[0].message.content.strip()
    print(f"DEBUG LLM RESPONSE START\n{raw_content}\nDEBUG LLM RESPONSE END")
    
    if raw_content.startswith("```json"):
        raw_content = raw_content[7:]
    if raw_content.startswith("```"):
        raw_content = raw_content[3:]
    if raw_content.endswith("```"):
        raw_content = raw_content[:-3]
        
    try:
        data = json.loads(raw_content)
        return CompanyProfile(**data)
    except json.JSONDecodeError:
        logger.warning("JSON padrão falhou. Tentando reparar JSON malformado do LLM...")
        try:
            # Tenta reparar o JSON quebrado (ex: vírgulas faltando, aspas erradas)
            data = json_repair.loads(raw_content)
            return CompanyProfile(**data)
        except Exception as e:
            logger.error(f"Falha crítica no parse do JSON mesmo após reparo: {e}")
            raise e
