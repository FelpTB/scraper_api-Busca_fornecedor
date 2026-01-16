"""
Pré-processamento de conteúdo para chunking.

Responsável por:
1. Deduplicação de linhas repetidas
2. Normalização de whitespace
3. Limpeza geral do conteúdo

Objetivo: Reduzir tamanho do conteúdo removendo redundâncias sem perder informação útil.
"""

import logging
import re
from dataclasses import dataclass
from typing import Tuple

from .config import ChunkingConfig, DedupeConfig

logger = logging.getLogger(__name__)


@dataclass
class DedupeStats:
    """Estatísticas de deduplicação."""
    
    original_lines: int
    unique_lines: int
    removed_lines: int
    reduction_percent: float
    original_chars: int
    final_chars: int
    
    def __str__(self) -> str:
        return (
            f"DedupeStats(lines: {self.original_lines:,} → {self.unique_lines:,} "
            f"(-{self.removed_lines:,}, -{self.reduction_percent:.1f}%), "
            f"chars: {self.original_chars:,} → {self.final_chars:,})"
        )


@dataclass
class PreprocessStats:
    """Estatísticas completas do pré-processamento."""
    
    dedupe_stats: DedupeStats
    original_chars: int
    final_chars: int
    reduction_percent: float
    original_lines: int
    final_lines: int
    
    def __str__(self) -> str:
        return (
            f"PreprocessStats("
            f"chars: {self.original_chars:,} → {self.final_chars:,} "
            f"(-{self.reduction_percent:.1f}%), "
            f"lines: {self.original_lines:,} → {self.final_lines:,}, "
            f"{self.dedupe_stats})"
        )


class ContentPreprocessor:
    """
    Pré-processador de conteúdo para chunking.
    
    Remove redundâncias e normaliza o conteúdo antes da divisão em chunks.
    """
    
    def __init__(self, config: ChunkingConfig):
        """
        Inicializa o pré-processador.
        
        Args:
            config: Configuração de chunking
        """
        self.config = config
        self.dedupe_config = config.dedupe
    
    def deduplicate_lines(self, content: str) -> Tuple[str, DedupeStats]:
        """
        Remove linhas repetidas do conteúdo.
        
        Estratégia (scope='document'):
        - Mantém primeira ocorrência de cada linha única
        - Remove todas as ocorrências subsequentes
        - Preserva ordem das primeiras ocorrências
        - Ignora linhas menores que min_line_length
        
        Args:
            content: Conteúdo original
        
        Returns:
            Tuple (conteúdo deduplicado, estatísticas)
        """
        if not self.dedupe_config.enabled:
            logger.debug("Deduplicação desabilitada, retornando conteúdo original")
            lines = content.splitlines()
            stats = DedupeStats(
                original_lines=len(lines),
                unique_lines=len(lines),
                removed_lines=0,
                reduction_percent=0.0,
                original_chars=len(content),
                final_chars=len(content),
            )
            return content, stats
        
        original_chars = len(content)
        original_lines = content.splitlines(keepends=True)
        total_lines = len(original_lines)
        
        # Estratégia baseada no scope
        if self.dedupe_config.scope == "document":
            # Deduplicação em todo o documento
            seen = set()
            unique_lines = []
            removed_count = 0
            
            for line in original_lines:
                # Normalizar linha para comparação (strip whitespace final)
                normalized = line.rstrip()
                
                # Ignorar linhas muito curtas se configurado
                if len(normalized) < self.dedupe_config.min_line_length:
                    # Linhas curtas sempre mantêm (podem ser importantes)
                    unique_lines.append(line)
                else:
                    # Usar linha normalizada como chave
                    if normalized not in seen:
                        seen.add(normalized)
                        unique_lines.append(line)
                    else:
                        removed_count += 1
            
            deduplicated_content = "".join(unique_lines)
            
        elif self.dedupe_config.scope == "consecutive":
            # Remover apenas linhas consecutivas repetidas
            unique_lines = []
            removed_count = 0
            prev_line = None
            
            for line in original_lines:
                normalized = line.rstrip()
                
                # Ignorar linhas muito curtas
                if len(normalized) < self.dedupe_config.min_line_length:
                    unique_lines.append(line)
                    prev_line = None
                elif normalized != prev_line:
                    unique_lines.append(line)
                    prev_line = normalized
                else:
                    removed_count += 1
            
            deduplicated_content = "".join(unique_lines)
        else:
            raise ValueError(f"scope inválido: {self.dedupe_config.scope}")
        
        # Calcular estatísticas
        final_chars = len(deduplicated_content)
        unique_count = len(unique_lines)
        reduction_percent = (removed_count / total_lines * 100) if total_lines > 0 else 0.0
        
        stats = DedupeStats(
            original_lines=total_lines,
            unique_lines=unique_count,
            removed_lines=removed_count,
            reduction_percent=reduction_percent,
            original_chars=original_chars,
            final_chars=final_chars,
        )
        
        if removed_count > 0:
            logger.info(
                f"📝 Deduplicação: {removed_count:,}/{total_lines:,} linhas removidas "
                f"({reduction_percent:.1f}%), {original_chars:,} → {final_chars:,} chars"
            )
        
        return deduplicated_content, stats
    
    def normalize_whitespace(self, content: str) -> str:
        """
        Normaliza espaços em branco excessivos.
        
        Operações:
        - Remove múltiplas linhas vazias consecutivas (mantém máx 2)
        - Remove espaços em excesso no final de linhas
        - Preserva estrutura geral do conteúdo
        
        Args:
            content: Conteúdo para normalizar
        
        Returns:
            Conteúdo normalizado
        """
        # Remover espaços no final de linhas
        lines = content.splitlines(keepends=True)
        normalized_lines = [line.rstrip() + "\n" if line.rstrip() else "\n" for line in lines]
        
        # Remover múltiplas linhas vazias consecutivas (manter máx 2)
        result = []
        empty_count = 0
        
        for line in normalized_lines:
            if line.strip() == "":
                empty_count += 1
                # Manter apenas 2 linhas vazias consecutivas
                if empty_count <= 2:
                    result.append(line)
            else:
                empty_count = 0
                result.append(line)
        
        normalized = "".join(result)
        
        # Log se houve redução significativa
        if len(normalized) < len(content):
            reduction = len(content) - len(normalized)
            reduction_percent = (reduction / len(content) * 100) if len(content) > 0 else 0
            logger.debug(
                f"🧹 Whitespace normalizado: {reduction:,} chars removidos "
                f"({reduction_percent:.1f}%)"
            )
        
        return normalized
    
    def preprocess(self, content: str) -> Tuple[str, PreprocessStats]:
        """
        Pipeline completo de pré-processamento.
        
        Ordem:
        1. Deduplicação de linhas
        2. Normalização de whitespace
        
        Args:
            content: Conteúdo bruto para pré-processar
        
        Returns:
            Tuple (conteúdo pré-processado, estatísticas)
        """
        original_chars = len(content)
        original_lines_count = len(content.splitlines())
        
        # 1. Deduplicação
        deduplicated, dedupe_stats = self.deduplicate_lines(content)
        
        # 2. Normalização de whitespace
        normalized = self.normalize_whitespace(deduplicated)
        
        # Calcular estatísticas finais
        final_chars = len(normalized)
        final_lines_count = len(normalized.splitlines())
        
        reduction_percent = (
            ((original_chars - final_chars) / original_chars * 100)
            if original_chars > 0
            else 0.0
        )
        
        stats = PreprocessStats(
            dedupe_stats=dedupe_stats,
            original_chars=original_chars,
            final_chars=final_chars,
            reduction_percent=reduction_percent,
            original_lines=original_lines_count,
            final_lines=final_lines_count,
        )
        
        if reduction_percent > 0:
            logger.info(
                f"✅ Pré-processamento: {original_chars:,} → {final_chars:,} chars "
                f"(-{reduction_percent:.1f}%), {original_lines_count:,} → {final_lines_count:,} linhas"
            )
        else:
            logger.debug("✅ Pré-processamento: sem redução significativa")
        
        return normalized, stats


def preprocess_content(content: str, config: ChunkingConfig = None) -> Tuple[str, PreprocessStats]:
    """
    Função de conveniência para pré-processar conteúdo.
    
    Args:
        content: Conteúdo para pré-processar
        config: Configuração opcional (usa singleton se None)
    
    Returns:
        Tuple (conteúdo pré-processado, estatísticas)
    """
    from .config import get_chunking_config
    
    if config is None:
        config = get_chunking_config()
    
    preprocessor = ContentPreprocessor(config)
    return preprocessor.preprocess(content)

