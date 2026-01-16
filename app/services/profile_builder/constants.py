"""
Constantes e configurações do módulo de LLM.

NOTA: Configurações de chunking foram movidas para app.core.chunking.config.
Este módulo mantém apenas SYSTEM_PROMPT e configurações não relacionadas a chunking
(como similarity_threshold, text_score_divisor).
"""

from app.services.concurrency_manager.config_loader import get_section as get_config

# Carregar configuração centralizada; fallback para defaults anteriores.
DEFAULT_CONFIG = get_config("profile/profile_llm", {}) or {
    'max_chunk_tokens': 800_000,
    'system_prompt_overhead': 2500,
    'chars_per_token': 3,
    'group_target_tokens': 100_000,
    'min_chunk_chars': 500,
    'retry_attempts': 3,
    'retry_min_wait': 2,
    'retry_max_wait': 120,
    'similarity_threshold': 0.3,
    'text_score_divisor': 10
}


class LLMConfig:
    """Gerenciador de configuração do LLM."""
    
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
    
    @property
    def max_chunk_tokens(self) -> int:
        return self._config['max_chunk_tokens']
    
    @property
    def chars_per_token(self) -> int:
        return self._config['chars_per_token']
    
    @property
    def system_prompt_overhead(self) -> int:
        return self._config['system_prompt_overhead']
    
    @property
    def group_target_tokens(self) -> int:
        return self._config['group_target_tokens']
    
    @property
    def min_chunk_chars(self) -> int:
        return self._config['min_chunk_chars']
    
    @property
    def similarity_threshold(self) -> float:
        return self._config['similarity_threshold']
    
    @property
    def text_score_divisor(self) -> int:
        return self._config['text_score_divisor']
    
    def update(self, **kwargs):
        """Atualiza configurações dinamicamente."""
        for key, value in kwargs.items():
            if key in self._config:
                self._config[key] = value


llm_config = LLMConfig()


SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Gere estritamente um JSON válido correspondente ao schema abaixo.
Extraia dados do texto Markdown e PDF fornecido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA DE SAÍDA: PORTUGUÊS (BRASIL). Todo o conteúdo extraído deve estar em Português. Traduza descrições, cargos e categorias. Mantenha em inglês apenas termos técnicos globais (ex: "SaaS", "Big Data", "Machine Learning") ou nomes próprios de produtos não traduzíveis.
2. PRODUTOS vs SERVIÇOS: Distinga claramente entre produtos físicos e serviços intangíveis.
3. DETALHES DO SERVIÇO: Para os principais serviços, tente extrair 'metodologia' (como eles fazem) e 'entregáveis' (o que o cliente recebe).
4. LISTAGEM DE PRODUTOS EXAUSTIVA - CRÍTICO E OBRIGATÓRIO: 
   - Ao extrair 'product_categories', você DEVE preencher o campo 'items' de CADA categoria com TODOS os produtos individuais encontrados.
   - NUNCA deixe 'items' vazio ou como array vazio []. Se uma categoria é mencionada, você DEVE encontrar e listar os produtos específicos.
   - O QUE SÃO ITEMS: Items são PRODUTOS ESPECÍFICOS (nomes de produtos, modelos, referências, SKUs). NÃO são nomes de categorias, NÃO são marcas isoladas, NÃO são descrições genéricas de categorias.
   - EXEMPLO CORRETO: Se o texto menciona "Fios e Cabos" e lista "Cabo 1KV HEPR", "Cabo 1KV LSZH", "Cabo Flex 750V", então 'items' DEVE ser ["Cabo 1KV HEPR", "Cabo 1KV LSZH", "Cabo Flex 750V"].
   - EXEMPLO INCORRETO: NÃO faça {"category_name": "Fios e Cabos", "items": ["Fios e Cabos", "Automação"]} - esses são nomes de categorias, não produtos.
   - EXEMPLO INCORRETO: NÃO faça {"category_name": "Marcas", "items": ["Philips", "Siemens"]} - marcas isoladas não são produtos. Se houver "Luminária Philips XYZ", extraia "Luminária Philips XYZ" como item.
   - PROCURE no texto: nomes de produtos, modelos, referências, SKUs, códigos de produto, listas de itens, catálogos, especificações técnicas.
   - Se você criar uma categoria, você DEVE preencher seus items com produtos encontrados no texto. Se não encontrar produtos específicos, NÃO crie a categoria.
   - NÃO crie categorias genéricas como "Outras Categorias", "Marcas", "Geral" - apenas categorias específicas mencionadas no conteúdo.
   - Extraia TUDO que encontrar: nomes completos de produtos, modelos, marcas quando parte do nome do produto, referências. NÃO resuma, NÃO filtre por "qualidade".
5. PROVA SOCIAL: Extraia Estudos de Caso específicos, Nomes de Clientes e Certificações. Estes são de alta prioridade.
6. ENGAJAMENTO: Procure como eles vendem (Mensalidade? Por Projeto? Alocação de equipe?).
7. CONSOLIDAÇÃO: Se receber múltiplos fragmentos de conteúdo, consolide as informações sem duplicar. Priorize informações mais detalhadas e completas.

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

