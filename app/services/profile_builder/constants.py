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
# Prompt 1 — Schema-first com estrutura até nível 3 (docs/PESQUISA_PROMPT_E_PROPOSTA_3_PROMPTS.md)
SYSTEM_PROMPT = """Você é um extrator de dados B2B. Extraia do texto fornecido e retorne UM ÚNICO objeto JSON válido.

OBRIGATÓRIO: O JSON deve conter SEMPRE estas 6 chaves raiz (use null ou [] quando não houver dados):

- identidade: { nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios }
- classificacao: { industria, modelo_negocio, publico_alvo, cobertura_geografica }
- ofertas: { produtos: [ { categoria, produtos: [] } ], servicos: [ { nome, descricao } ] }
- reputacao: { certificacoes: [], premios: [], parcerias: [], lista_clientes: [], estudos_caso: [ { titulo, nome_cliente, industria, desafio, solucao, resultado } ] }
- contato: { emails: [], telefones: [], url_linkedin, url_site, endereco_matriz, localizacoes: [] }
- fontes: [ URLs das páginas analisadas ]

PRODUTOS vs SERVIÇOS — ONDE E COMO PREENCHER:

- PRODUTO = item tangível, que pode ter catálogo, modelo, SKU (ex.: cabo, disjuntor, luminária, equipamento). Vai em ofertas.produtos.
  Estrutura: lista de categorias; cada categoria tem "categoria" (nome do tipo, ex.: "Cabos", "Conectores") e "produtos" (lista de nomes de itens). Ex.: { "categoria": "Cabos", "produtos": ["Cabo 1KV HEPR", "Cabo Flex 750V"] }.
  NUNCA crie uma categoria chamada "Serviços" ou "Serviço" dentro de ofertas.produtos. Se o texto falar em "serviços oferecidos", use ofertas.servicos.

- SERVIÇO = atividade intangível que a empresa realiza (consultoria, manutenção, instalação, suporte, treinamento). Vai em ofertas.servicos.
  Estrutura: lista de objetos com "nome" e "descricao". Ex.: { "nome": "Manutenção Preventiva", "descricao": "Inspeção periódica dos equipamentos." }.
  NUNCA coloque serviços na lista de produtos nem como categoria de produtos.

Regra rápida: Se tem modelo/SKU ou é item de catálogo físico → ofertas.produtos. Se é algo que a empresa FAZ (atividade, projeto) → ofertas.servicos.

CLIENTES E PROVA SOCIAL (PRIORIDADE MÁXIMA) — reputacao.lista_clientes:

Se existir trecho com: "CLIENTES", "Nossos clientes", "Algumas obras executadas", "Quem confia", "Projetos realizados", "Cases", "Quem já nos escolheu" ou similar:
• Extraia TODOS os nomes de empresas/clientes listados e preencha reputacao.lista_clientes.
• Normalize encoding nos nomes extraídos (ex.: EmpÃ³rio → Empório).

ESTUDOS DE CASO — reputacao.estudos_caso:

Preencha reputacao.estudos_caso SOMENTE quando existir, para o mesmo case:
• Cliente identificado (nome_cliente)
• Solução descrita (solucao)
• Resultado descrito (resultado)

Caso contrário (ex.: só lista de clientes sem desafio/solução/resultado), use: "estudos_caso": []

REGRAS:
1. IDIOMA: Português (Brasil). Termos técnicos globais podem ficar em inglês.
2. Respeite PRODUTOS vs SERVIÇOS acima: produtos em ofertas.produtos (por categoria); serviços em ofertas.servicos (nome + descricao).
3. DEDUPLICAÇÃO (CRÍTICO): Cada produto ou serviço deve aparecer NO MÁXIMO UMA VEZ em todo o JSON. Não repita o mesmo item em categorias diferentes. Se houver variações (ex.: "RCA" e "Conector RCA"), inclua só uma, a mais completa.
4. Limites: máx. 60 produtos por categoria, 40 categorias, 50 serviços, 80 clientes, 50 parcerias, 50 certificações, 30 estudos de caso. PARE ao atingir qualquer limite ou quando não houver mais itens únicos.
5. Não invente dados. Use null ou [] quando não encontrar.
6. Seja conciso em descrições longas para caber na resposta.

Saída: APENAS o objeto JSON, sem markdown (sem ```json), sem texto antes ou depois.
"""

