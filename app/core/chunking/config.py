"""
Configurações do módulo de Chunking v4.0

Centraliza todas as configurações de chunking carregadas do JSON.
Fornece dataclasses tipadas e singleton para acesso global.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Caminho do arquivo de configuração
CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "chunking" / "chunking.json"


@dataclass
class DedupeConfig:
    """Configurações de deduplicação de linhas."""
    
    enabled: bool = True
    scope: str = "document"  # "document" | "consecutive"
    min_line_length: int = 5
    preserve_first_occurrence: bool = True
    
    def __post_init__(self):
        if self.scope not in ("document", "consecutive"):
            raise ValueError(f"scope deve ser 'document' ou 'consecutive', recebido: {self.scope}")


@dataclass
class TokenizerConfig:
    """Configurações do tokenizer."""
    
    type: str = "mistral-common"  # "mistral-common" | "tiktoken" | "estimate"
    model: str = "mistralai/Ministral-3-8B-Instruct-2512"
    fallback_chars_per_token: int = 3
    
    def __post_init__(self):
        valid_types = ("mistral-common", "tiktoken", "estimate")
        if self.type not in valid_types:
            raise ValueError(f"type deve ser um de {valid_types}, recebido: {self.type}")


@dataclass
class ChunkingConfig:
    """
    Configuração principal do módulo de chunking.
    
    Atributos:
        max_chunk_tokens: Limite máximo de tokens por chunk
        system_prompt_overhead: Tokens reservados para system prompt
        message_overhead: Tokens para formatação de mensagens
        safety_margin: Fator de segurança (0.0 a 1.0)
        group_target_tokens: Alvo de tokens ao agrupar páginas
        min_chunk_chars: Mínimo de caracteres por chunk
        dedupe: Configurações de deduplicação
        tokenizer: Configurações do tokenizer
    """
    
    max_chunk_tokens: int = 20000
    system_prompt_overhead: int = 2500
    message_overhead: int = 200
    safety_margin: float = 0.85
    group_target_tokens: int = 12000
    min_chunk_chars: int = 500
    
    dedupe: DedupeConfig = field(default_factory=DedupeConfig)
    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    
    def __post_init__(self):
        """Valida configurações após inicialização."""
        if self.max_chunk_tokens <= 0:
            raise ValueError(f"max_chunk_tokens deve ser > 0, recebido: {self.max_chunk_tokens}")
        
        if not 0.0 < self.safety_margin <= 1.0:
            raise ValueError(f"safety_margin deve estar entre 0.0 e 1.0, recebido: {self.safety_margin}")
        
        if self.group_target_tokens > self.effective_max_tokens:
            logger.warning(
                f"group_target_tokens ({self.group_target_tokens}) > effective_max_tokens "
                f"({self.effective_max_tokens}). Ajustando para effective_max_tokens."
            )
            self.group_target_tokens = self.effective_max_tokens
    
    @property
    def effective_max_tokens(self) -> int:
        """
        Calcula o limite efetivo de tokens para conteúdo.
        
        Fórmula: (max_chunk_tokens - system_prompt_overhead - message_overhead) * safety_margin
        
        Returns:
            Número máximo de tokens que o conteúdo do chunk pode ter
        """
        base = self.max_chunk_tokens - self.system_prompt_overhead - self.message_overhead
        return int(base * self.safety_margin)
    
    @property
    def available_tokens(self) -> int:
        """
        Tokens disponíveis sem margem de segurança.
        
        Útil para logs e comparações.
        """
        return self.max_chunk_tokens - self.system_prompt_overhead - self.message_overhead
    
    def to_dict(self) -> dict:
        """Converte configuração para dicionário."""
        return {
            "max_chunk_tokens": self.max_chunk_tokens,
            "system_prompt_overhead": self.system_prompt_overhead,
            "message_overhead": self.message_overhead,
            "safety_margin": self.safety_margin,
            "group_target_tokens": self.group_target_tokens,
            "min_chunk_chars": self.min_chunk_chars,
            "effective_max_tokens": self.effective_max_tokens,
            "available_tokens": self.available_tokens,
            "dedupe": {
                "enabled": self.dedupe.enabled,
                "scope": self.dedupe.scope,
                "min_line_length": self.dedupe.min_line_length,
                "preserve_first_occurrence": self.dedupe.preserve_first_occurrence,
            },
            "tokenizer": {
                "type": self.tokenizer.type,
                "model": self.tokenizer.model,
                "fallback_chars_per_token": self.tokenizer.fallback_chars_per_token,
            }
        }
    
    def __str__(self) -> str:
        return (
            f"ChunkingConfig("
            f"max_chunk_tokens={self.max_chunk_tokens}, "
            f"effective_max={self.effective_max_tokens}, "
            f"safety_margin={self.safety_margin:.0%}, "
            f"dedupe={self.dedupe.enabled})"
        )


def load_chunking_config(config_path: Optional[Path] = None) -> ChunkingConfig:
    """
    Carrega configuração do arquivo JSON.
    
    Args:
        config_path: Caminho opcional para o arquivo de configuração.
                    Se None, usa o caminho padrão.
    
    Returns:
        ChunkingConfig carregado do JSON
    
    Raises:
        FileNotFoundError: Se o arquivo não existir
        json.JSONDecodeError: Se o JSON for inválido
    """
    path = config_path or CONFIG_PATH
    
    if not path.exists():
        logger.warning(f"Arquivo de configuração não encontrado: {path}. Usando defaults.")
        return ChunkingConfig()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_config = json.load(f)
        
        # Remover campos "_note" do JSON
        config_data = {k: v for k, v in raw_config.items() if not k.endswith("_note")}
        
        # Processar sub-configurações
        dedupe_data = config_data.pop("dedupe", {})
        if isinstance(dedupe_data, dict):
            dedupe_data = {k: v for k, v in dedupe_data.items() if not k.endswith("_note")}
            dedupe_config = DedupeConfig(**dedupe_data)
        else:
            dedupe_config = DedupeConfig()
        
        tokenizer_data = config_data.pop("tokenizer", {})
        if isinstance(tokenizer_data, dict):
            tokenizer_data = {k: v for k, v in tokenizer_data.items() if not k.endswith("_note")}
            tokenizer_config = TokenizerConfig(**tokenizer_data)
        else:
            tokenizer_config = TokenizerConfig()
        
        # Criar config principal
        config = ChunkingConfig(
            dedupe=dedupe_config,
            tokenizer=tokenizer_config,
            **config_data
        )
        
        logger.info(f"✅ Chunking config carregado: {config}")
        logger.debug(f"   effective_max_tokens = {config.effective_max_tokens:,}")
        logger.debug(f"   cálculo: ({config.max_chunk_tokens} - {config.system_prompt_overhead} - {config.message_overhead}) × {config.safety_margin}")
        
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear JSON de configuração: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}")
        raise


# Cache singleton da configuração
_chunking_config: Optional[ChunkingConfig] = None


def get_chunking_config() -> ChunkingConfig:
    """
    Retorna instância singleton da configuração de chunking.
    
    Carrega do JSON na primeira chamada e reutiliza nas subsequentes.
    
    Returns:
        ChunkingConfig singleton
    """
    global _chunking_config
    
    if _chunking_config is None:
        _chunking_config = load_chunking_config()
    
    return _chunking_config


def reset_chunking_config() -> None:
    """
    Reseta o singleton para forçar recarregamento.
    
    Útil para testes ou quando o arquivo de configuração é alterado.
    """
    global _chunking_config
    _chunking_config = None
    logger.debug("Chunking config singleton resetado")

