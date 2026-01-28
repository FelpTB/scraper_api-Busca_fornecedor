"""
Agente de Extração de Perfil - Extrai dados estruturados de conteúdo scraped.

Responsável por analisar conteúdo de sites e extrair informações de perfil
de empresa em formato estruturado.
"""

import json
import logging
from typing import Optional, Any

import json_repair

from .base_agent import BaseAgent
from app.services.llm_manager import LLMPriority
from app.schemas.profile import CompanyProfile
from app.services.concurrency_manager.config_loader import get_section as get_config

logger = logging.getLogger(__name__)


class ProfileExtractorAgent(BaseAgent):
    """
    Agente especializado em extrair perfil de empresa de conteúdo scraped.
    
    Usa prioridade NORMAL por padrão pois roda após Discovery e LinkSelector.
    """
    
    # Timeout e retries configuráveis via app/configs/llm_agents.json
    _CFG = get_config("profile/llm_agents", {}).get("profile_extractor", {})
    DEFAULT_TIMEOUT = _CFG.get("timeout", 90.0)
    DEFAULT_MAX_RETRIES = _CFG.get("max_retries", 2)
    
    # Prompt 1 — Schema-first com estrutura até nível 3 (docs/PESQUISA_PROMPT_E_PROPOSTA_3_PROMPTS.md)
    SYSTEM_PROMPT = """Você é um extrator de dados B2B. Extraia do texto fornecido e retorne UM ÚNICO objeto JSON válido.

OBRIGATÓRIO: O JSON deve conter SEMPRE estas 6 chaves raiz (use null ou [] quando não houver dados):

- identidade: { nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios }
- classificacao: { industria, modelo_negocio, publico_alvo, cobertura_geografica }
- ofertas: { produtos: [ { categoria, produtos: [] } ], servicos: [ { nome, descricao } ] }
- reputacao: { certificacoes: [], premios: [], parcerias: [], lista_clientes: [], estudos_caso: [ { titulo, nome_cliente, industria, desafio, solucao, resultado } ] }
- contato: { emails: [], telefones: [], url_linkedin, url_site, endereco_matriz, localizacoes: [] }
- fontes: [ URLs das páginas analisadas ]

REGRAS:
1. IDIOMA: Português (Brasil). Termos técnicos globais podem ficar em inglês.
2. Produtos vs serviços: produtos = itens físicos; serviços = atividades intangíveis.
3. DEDUPLICAÇÃO (CRÍTICO): Cada produto ou serviço deve aparecer NO MÁXIMO UMA VEZ em todo o JSON. Não repita o mesmo item em categorias diferentes. Se houver variações (ex.: "RCA" e "Conector RCA"), inclua só uma, a mais completa.
4. Limites: máx. 60 produtos por categoria, 40 categorias, 50 serviços, 80 clientes, 50 parcerias, 50 certificações, 30 estudos de caso. PARE ao atingir qualquer limite ou quando não houver mais itens únicos.
5. Não invente dados. Use null ou [] quando não encontrar.
6. Seja conciso em descrições longas para caber na resposta.

Saída: APENAS o objeto JSON, sem markdown (sem ```json), sem texto antes ou depois.
"""
    
    def _get_response_format(self) -> Optional[dict]:
        """
        Retorna formato de resposta usando json_schema do SGLang.
        Usa o schema do CompanyProfile para garantir formato estruturado.
        
        Returns:
            Dict com json_schema format para SGLang
        """
        # Gerar JSON Schema do CompanyProfile usando Pydantic
        json_schema = CompanyProfile.model_json_schema()
        
        # Retornar formato compatível com SGLang e OpenAI API
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "company_profile",
                "schema": json_schema
            }
        }
    
    def _build_user_prompt(self, content: str = "", **kwargs) -> str:
        """
        Constrói prompt com conteúdo para análise.
        
        Args:
            content: Conteúdo scraped para análise
        
        Returns:
            Prompt formatado
        """
        return f"Analise este conteúdo e extraia os dados em Português:\n\n{content}"
    
    def _parse_response(self, response: str, **kwargs) -> CompanyProfile:
        """
        Processa resposta e cria CompanyProfile.
        
        Args:
            response: Resposta JSON do LLM
        
        Returns:
            CompanyProfile com dados extraídos
        """
        try:
            # Limpar markdown
            content = response
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            # Tentar parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("ProfileExtractorAgent: JSON padrão falhou, tentando reparar")
                try:
                    data = json_repair.loads(content)
                except Exception as e:
                    logger.error(f"ProfileExtractorAgent: Falha crítica no parse JSON: {e}")
                    return CompanyProfile()
            
            # Normalizar estrutura
            if isinstance(data, list):
                data = data[0] if data and isinstance(data[0], dict) else {}
            if not isinstance(data, dict):
                data = {}
            
            # Normalizar resposta
            data = self._normalize_response(data)
            
            # Criar perfil
            try:
                return CompanyProfile(**data)
            except Exception as e:
                logger.error(f"ProfileExtractorAgent: Erro ao criar CompanyProfile: {e}")
                return CompanyProfile()
                
        except Exception as e:
            logger.error(f"ProfileExtractorAgent: Erro ao processar resposta: {e}")
            return CompanyProfile()
    
    def _normalize_response(self, data: dict) -> dict:
        """
        Normaliza a resposta do LLM para o formato esperado.
        
        Args:
            data: Dados extraídos pelo LLM
        
        Returns:
            Dados normalizados
        """
        # Importar normalizador do módulo profile_builder
        try:
            from app.services.profile_builder.response_normalizer import normalize_llm_response
            return normalize_llm_response(data)
        except ImportError:
            # Fallback se normalizador não disponível
            return data
    
    async def extract_profile(
        self,
        content: str,
        ctx_label: str = "",
        request_id: str = ""
    ) -> CompanyProfile:
        """
        Método principal para extrair perfil de conteúdo.
        
        Args:
            content: Conteúdo scraped para análise
            ctx_label: Label de contexto para logs
            request_id: ID da requisição
        
        Returns:
            CompanyProfile com dados extraídos
        """
        if not content or len(content.strip()) < 100:
            logger.warning(f"{ctx_label}ProfileExtractorAgent: Conteúdo muito curto ou vazio")
            return CompanyProfile()
        
        try:
            return await self.execute(
                priority=LLMPriority.NORMAL,  # Profile usa prioridade normal
                timeout=self.DEFAULT_TIMEOUT,
                ctx_label=ctx_label,
                request_id=request_id,
                content=content
            )
        except Exception as e:
            logger.error(f"{ctx_label}ProfileExtractorAgent: Erro na extração: {e}")
            return CompanyProfile()


# Instância singleton
_profile_extractor_agent: Optional[ProfileExtractorAgent] = None


def get_profile_extractor_agent() -> ProfileExtractorAgent:
    """Retorna instância singleton do ProfileExtractorAgent."""
    global _profile_extractor_agent
    if _profile_extractor_agent is None:
        _profile_extractor_agent = ProfileExtractorAgent()
    return _profile_extractor_agent

