"""
Utilitários para estimativa de tokens unificados.

Centraliza a lógica de estimativa de tokens para garantir consistência
em todo o sistema (chunking, provider_manager, etc).

v3.0: Usa mistral-common tokenizer para contagem precisa de tokens.
      Compatível com modelos Mistral 3 (V3-Tekken).
"""

import logging
from typing import List, Dict, Union, Optional

try:
    from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
    from mistral_common.protocol.instruct.request import ChatCompletionRequest
    from mistral_common.protocol.instruct.messages import UserMessage, AssistantMessage, SystemMessage
    MISTRAL_TOKENIZER_AVAILABLE = True
except ImportError:
    MISTRAL_TOKENIZER_AVAILABLE = False
    import warnings
    warnings.warn("mistral-common não está instalado. Usando estimativa manual. Instale com: pip install 'mistral-common[sentencepiece]'")

from app.services.concurrency_manager.config_loader import get_section as get_config

logger = logging.getLogger(__name__)

# Carregar configuração
_token_config = get_config("profile/profile_llm", {}) or {}
CHARS_PER_TOKEN = _token_config.get("chars_per_token", 3)
SYSTEM_PROMPT_OVERHEAD = _token_config.get("system_prompt_overhead", 2500)
MESSAGE_OVERHEAD = 100  # Overhead por mensagem (role, separadores, etc)

# Cache do tokenizer Mistral para performance
_mistral_tokenizer_cache = None


def _get_mistral_tokenizer():
    """
    Retorna tokenizer Mistral com cache.
    
    Usa o modelo específico Mistral-3-8B-Instruct-2512 para contagem precisa de tokens.
    
    Returns:
        MistralTokenizer ou None se não disponível
    """
    global _mistral_tokenizer_cache
    
    if not MISTRAL_TOKENIZER_AVAILABLE:
        return None
    
    if _mistral_tokenizer_cache is None:
        try:
            # Usar from_hf_hub para carregar o tokenizer do modelo Mistral
            _mistral_tokenizer_cache = MistralTokenizer.from_hf_hub("mistralai/Ministral-3-8B-Instruct-2512")
            logger.info("Mistral tokenizer inicializado com sucesso (Mistral-3-8B-Instruct-2512)")
        except Exception as e:
            logger.warning(f"Erro ao carregar tokenizer Mistral: {e}. Usando estimativa manual.")
            return None
    
    return _mistral_tokenizer_cache


def calculate_repetition_rate(content: str) -> float:
    """
    Calcula a taxa de repetição de um conteúdo.
    
    Taxa de repetição = (linhas repetidas) / (total de linhas)
    
    Args:
        content: Texto para analisar
    
    Returns:
        Taxa de repetição entre 0.0 e 1.0
    """
    lines = content.splitlines()
    if not lines:
        return 0.0
    
    unique_lines = len(set(lines))
    total_lines = len(lines)
    repetition_rate = (total_lines - unique_lines) / total_lines
    
    return float(repetition_rate)


def calculate_safety_margin(
    content: str,
    estimated_tokens: int,
    base_effective_max: int
) -> tuple[int, dict]:
    """
    Calcula margem de segurança dinâmica baseada em características do conteúdo.
    
    Aplica margens extras quando:
    - Conteúdo tem alta repetição (>70%)
    - Chunk é grande (>60k tokens)
    
    Para casos extremos (>75k tokens), aplica margem mais agressiva para garantir
    que o chunk seja dividido antes de exceder o limite.
    
    Args:
        content: Conteúdo do chunk
        estimated_tokens: Tokens estimados do chunk
        base_effective_max: Effective max tokens base (após descontar overhead)
    
    Returns:
        Tuple (effective_max_ajustado, info_dict) onde info_dict contém:
        - repetition_rate: Taxa de repetição
        - repetition_margin: Margem aplicada por repetição
        - size_margin: Margem aplicada por tamanho
        - total_margin: Margem total aplicada
    """
    # Calcular taxa de repetição
    repetition_rate = calculate_repetition_rate(content)
    
    # Margem baseada em repetição
    if repetition_rate > 0.90:
        repetition_margin = 0.15  # 15% para >90% repetição
    elif repetition_rate > 0.80:
        repetition_margin = 0.10  # 10% para >80% repetição
    elif repetition_rate > 0.70:
        repetition_margin = 0.05  # 5% para >70% repetição
    else:
        repetition_margin = 0.0
    
    # Margem baseada em tamanho do chunk (escalonada)
    if estimated_tokens > 80000:
        size_margin = 0.25  # 25% para chunks > 80k tokens (casos extremos)
    elif estimated_tokens > 75000:
        size_margin = 0.20  # 20% para chunks > 75k tokens
    elif estimated_tokens > 70000:
        size_margin = 0.15  # 15% para chunks > 70k tokens
    elif estimated_tokens > 60000:
        size_margin = 0.10  # 10% para chunks > 60k tokens
    elif estimated_tokens > 50000:
        size_margin = 0.05  # 5% para chunks > 50k tokens
    else:
        size_margin = 0.0
    
    # Margem combinada (máximo das duas)
    total_margin = max(repetition_margin, size_margin)
    
    # Caso especial: Se chunk ainda excederia mesmo com margem padrão,
    # aplicar margem baseada no necessário + 5% extra de segurança
    adjusted_effective_max = int(base_effective_max * (1 - total_margin))
    
    if estimated_tokens > adjusted_effective_max:
        # Chunk ainda excederia, aplicar margem baseada no necessário
        required_margin = 1 - (estimated_tokens / base_effective_max)
        safe_margin = required_margin + 0.05  # 5% extra para segurança
        # Mas limitar a no máximo 30% para não ser muito agressivo
        safe_margin = min(safe_margin, 0.30)
        total_margin = safe_margin
        adjusted_effective_max = int(base_effective_max * (1 - total_margin))
    
    info = {
        "repetition_rate": repetition_rate,
        "repetition_margin": repetition_margin,
        "size_margin": size_margin,
        "total_margin": total_margin,
        "base_effective_max": base_effective_max,
        "adjusted_effective_max": adjusted_effective_max
    }
    
    return adjusted_effective_max, info


def estimate_tokens(content: Union[str, List[Dict[str, str]]], include_overhead: bool = False) -> int:
    """
    Estima/Conta a quantidade de tokens em um conteúdo usando tokenizer Mistral.
    
    v3.0: Usa mistral-common tokenizer (V3-Instruct) para contagem precisa.
          Compatível com modelos Mistral 3 (V3-Tekken).
          Fallback para estimativa manual se mistral-common não estiver disponível.
    
    Função unificada para estimativa de tokens que pode ser usada tanto para:
    - Texto simples (str)
    - Lista de mensagens (List[Dict[str, str]]) no formato OpenAI
    
    Args:
        content: Texto ou lista de mensagens
        include_overhead: Se True, adiciona overhead do system prompt (apenas para texto simples)
                         Para mensagens, o overhead é calculado automaticamente
    
    Returns:
        Número de tokens (preciso se mistral-common disponível, estimado caso contrário)
    """
    tokenizer = _get_mistral_tokenizer()
    use_mistral_tokenizer = tokenizer is not None
    
    if isinstance(content, str):
        # Texto simples
        if use_mistral_tokenizer:
            # Usar tokenizer Mistral para contagem precisa
            try:
                # Para texto simples, criar uma mensagem user e usar encode_chat_completion
                # Isso garante que a contagem inclui formatação de chat
                messages = [UserMessage(content=content)]
                request = ChatCompletionRequest(messages=messages)
                result = tokenizer.encode_chat_completion(request)
                
                # Extrair tokens do resultado
                if hasattr(result, 'tokens'):
                    base_tokens = len(result.tokens)
                elif isinstance(result, (list, tuple)):
                    base_tokens = len(result)
                elif hasattr(result, 'token_ids'):
                    base_tokens = len(result.token_ids)
                else:
                    # Fallback: tentar acessar como lista
                    base_tokens = len(list(result))
            except Exception as e:
                logger.warning(f"Erro ao usar tokenizer Mistral, fallback para estimativa manual: {e}")
                use_mistral_tokenizer = False
        
        if not use_mistral_tokenizer:
            # Fallback: estimativa manual
            total_chars = len(content)
            base_tokens = total_chars // CHARS_PER_TOKEN
        
        if include_overhead:
            return int(base_tokens + SYSTEM_PROMPT_OVERHEAD)
        
        return int(base_tokens)
    
    elif isinstance(content, list):
        # Lista de mensagens (formato OpenAI)
        if use_mistral_tokenizer:
            # Usar tokenizer Mistral para contagem precisa de mensagens
            try:
                # Converter mensagens OpenAI para formato Mistral
                mistral_messages = []
                for msg in content:
                    role = msg.get("role", "user")
                    msg_content = msg.get("content", "")
                    
                    if not msg_content:  # Ignorar mensagens vazias
                        continue
                    
                    if role == "system":
                        mistral_messages.append(SystemMessage(content=msg_content))
                    elif role == "user":
                        mistral_messages.append(UserMessage(content=msg_content))
                    elif role == "assistant":
                        mistral_messages.append(AssistantMessage(content=msg_content))
                    # Ignorar outras roles (tool, etc) por enquanto
                
                # Criar request para tokenização correta
                if mistral_messages:
                    request = ChatCompletionRequest(messages=mistral_messages)
                    result = tokenizer.encode_chat_completion(request)
                    
                    # Extrair tokens do resultado
                    if hasattr(result, 'tokens'):
                        num_tokens = len(result.tokens)
                    elif isinstance(result, (list, tuple)):
                        num_tokens = len(result)
                    elif hasattr(result, 'token_ids'):
                        num_tokens = len(result.token_ids)
                    else:
                        num_tokens = len(list(result))
                else:
                    num_tokens = 0
                
                return max(100, int(num_tokens))
            except Exception as e:
                logger.warning(f"Erro ao usar tokenizer Mistral para mensagens, fallback para estimativa manual: {e}")
                use_mistral_tokenizer = False
        
        if not use_mistral_tokenizer:
            # Fallback: estimativa manual
            total_chars = 0
            for msg in content:
                msg_content = msg.get("content", "")
                if isinstance(msg_content, str):
                    total_chars += len(msg_content)
            
            # Adicionar overhead de formatação (role, separadores, etc)
            overhead = len(content) * MESSAGE_OVERHEAD
            
            base_tokens = total_chars // CHARS_PER_TOKEN
            estimated = base_tokens + overhead
            
            return max(100, int(estimated))  # Mínimo de 100 tokens
    
    else:
        raise ValueError(f"Tipo de conteúdo não suportado: {type(content)}")

