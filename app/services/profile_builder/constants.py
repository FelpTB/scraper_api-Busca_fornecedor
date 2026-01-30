"""
Constantes e configurações do módulo de LLM.

NOTA: Configurações de chunking foram movidas para app.core.chunking.config.
Este módulo mantém apenas SYSTEM_PROMPT e configurações não relacionadas a chunking
(como similarity_threshold, text_score_divisor).

SYSTEM_PROMPT: ÚNICA FONTE do prompt de extração de perfil B2B. Usado por
ProfileExtractorAgent (agents) e por provider_caller.call_llm(). Alterar apenas aqui.
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


# Única fonte do prompt de extração de perfil (ProfileExtractorAgent e provider_caller usam daqui)
SYSTEM_PROMPT = """Você é um extrator de dados B2B. Extraia do texto e retorne UM ÚNICO JSON válido.

ESTRUTURA OBRIGATÓRIA (6 chaves raiz — use null ou [] se não houver dados):

1. identidade: { nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios }
   - descricao: OBRIGATÓRIA. Escreva 2-3 frases explicando O QUE a empresa faz, PARA QUEM e QUAL o diferencial. Não seja vago.

2. classificacao: { industria, modelo_negocio, publico_alvo, cobertura_geografica }
   - industria: ARRAY de strings. Ex.: ["Tecnologia", "Saúde"]
   - modelo_negocio: ARRAY com APENAS termos padronizados: "B2B", "B2C", "B2B2C", "D2C", "Marketplace". Ex.: ["B2B"] ou ["B2B", "B2C"]
   - publico_alvo: ARRAY de strings. Ex.: ["Empresas de construção", "Indústrias"]
   - cobertura_geografica: ARRAY de strings. Ex.: ["São Paulo", "Rio de Janeiro", "Nacional"]

3. ofertas: { produtos, servicos }
   - produtos: [ { categoria: "Nome da Categoria", produtos: ["Item1", "Item2"] } ]
     PRODUTO = item tangível com modelo/SKU (cabo, equipamento, luminária). NUNCA crie categoria "Serviços".
   - servicos: [ { nome: "Nome do Serviço", descricao: "Descrição DETALHADA do que inclui" } ]
     SERVIÇO = atividade intangível (consultoria, manutenção, instalação).
     CRÍTICO: Todo serviço DEVE ter descricao com 1-2 frases explicando O QUE inclui e COMO funciona. Nunca deixe descricao vazia.

4. reputacao: { certificacoes: [], premios: [], parcerias: [], lista_clientes: [], estudos_caso: [] }
   - lista_clientes: extraia TODOS os nomes de empresas mencionadas como clientes.
   - estudos_caso: preencha SOMENTE se houver nome_cliente + solucao + resultado juntos.

5. contato: { emails: [], telefones: [], url_linkedin, url_site, endereco_matriz, localizacoes: [] }

6. fontes: [ URLs das páginas analisadas ]

REGRAS IMPORTANTES:
- FORMATO: campos industria, modelo_negocio, publico_alvo, cobertura_geografica são SEMPRE arrays, nunca strings.
- DEDUPLICAÇÃO: cada item aparece NO MÁXIMO uma vez no JSON inteiro.
- IDIOMA: Português (Brasil). Termos técnicos globais podem ficar em inglês.
- Limites: máx. 60 produtos/categoria, 40 categorias, 50 serviços, 80 clientes.
- Não invente dados. Use null ou [] quando não encontrar.

SAÍDA: APENAS o JSON, sem markdown, sem texto antes ou depois.
"""

