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


SYSTEM_PROMPT = """Você é um extrator de dados B2B especializado. Extraia dados do texto fornecido e retorne em formato JSON válido.

INSTRUÇÕES CRÍTICAS:
1. IDIOMA: PORTUGUÊS (BRASIL). Todo conteúdo em Português, exceto termos técnicos globais (ex: "SaaS", "Big Data", "Machine Learning").
2. PRODUTOS vs SERVIÇOS: Distinga claramente produtos físicos de serviços intangíveis.
3. LIMITES DE LISTAS - CRÍTICO (NÃO EXCEDER):
   - Máximo 60 produtos por categoria
   - Máximo 40 categorias de produtos
   - Máximo 50 serviços
   - Máximo 80 clientes na lista_clientes
   - Máximo 50 parcerias
   - Máximo 50 certificações
   - Máximo 30 estudos de caso
   - PARE quando atingir qualquer limite ou quando não houver mais itens únicos no texto
4. REGRA DE DEDUPLICAÇÃO:
   - NÃO gere variações do mesmo item (ex: "RCA" e "Conector RCA" são o mesmo produto)
   - Use o nome mais completo e específico quando houver variações
   - Se você já extraiu um item, NÃO o extraia novamente com nome diferente
   - Dê preferência para itens que são claramente únicos
5. COMPLETUDE: Extraia TODOS os dados relevantes encontrados no texto, mas respeite os limites acima.

EXEMPLOS DE COMPORTAMENTO CORRETO:

<EXEMPLO_1_PRODUTOS>
INPUT: "Nossos produtos incluem: Cabo 1KV HEPR, Cabo 1KV LSZH, Cabo Flex 750V, Conector RCA, Conector XLR, Conector P2"

OUTPUT:
{
  "ofertas": {
    "produtos": [
      {
        "categoria": "Cabos",
        "produtos": ["Cabo 1KV HEPR", "Cabo 1KV LSZH", "Cabo Flex 750V"]
      },
      {
        "categoria": "Conectores",
        "produtos": ["Conector RCA", "Conector XLR", "Conector P2"]
      }
    ]
  }
}
NOTA: Cada produto mencionado uma vez, sem variações.
</EXEMPLO_1_PRODUTOS>


REGRAS DE PARADA (CRÍTICO):
1. Se você já extraiu um item, NÃO extraia variações dele
2. Se atingiu o limite máximo de itens em qualquer lista, PARE imediatamente
3. Se não há mais itens únicos no texto, PARE
4. NÃO invente itens que não estão explicitamente no texto
5. NÃO continue gerando após extrair todos os itens únicos encontrados

Se um campo não for encontrado, use null ou lista vazia.
Retorne APENAS um objeto JSON válido, sem markdown (```json), sem explicações adicionais.
"""

