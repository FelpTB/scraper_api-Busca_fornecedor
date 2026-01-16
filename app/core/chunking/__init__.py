"""
Módulo de Chunking v4.0

Responsável por:
1. Pré-processamento (deduplicação de linhas)
2. Divisão de conteúdo em chunks
3. Validação de chunks

Uso:
    from app.core.chunking import process_content, get_chunking_config, preprocess_content
    
    # Pipeline completo
    chunks = process_content(raw_content)
    
    # Ou etapas individuais
    config = get_chunking_config()
    clean_content, stats = preprocess_content(raw_content)
    chunks = chunk_content(clean_content)
    valid_chunks = validate_chunks(chunks)
"""

from .config import (
    ChunkingConfig,
    DedupeConfig,
    TokenizerConfig,
    get_chunking_config,
    load_chunking_config,
)
from .preprocessor import (
    ContentPreprocessor,
    DedupeStats,
    PreprocessStats,
    preprocess_content,
)
from .chunker import (
    SmartChunker,
    Chunk,
    chunk_content,
)
from .validator import (
    ChunkValidator,
    ValidationResult,
    BatchValidationResult,
    validate_chunks,
)


def process_content(raw_content: str, config: ChunkingConfig = None) -> list[Chunk]:
    """
    Pipeline completo de processamento de conteúdo: preprocess → chunk → validate.
    
    Esta é a função principal que orquestra todo o processo de chunking:
    1. Pré-processa o conteúdo (deduplicação, normalização)
    2. Divide em chunks respeitando limites de tokens
    3. Valida e corrige chunks inválidos automaticamente
    
    Args:
        raw_content: Conteúdo bruto para processar
        config: Configuração opcional (usa singleton se None)
    
    Returns:
        Lista de Chunks válidos e prontos para envio ao LLM
    
    Exemplo:
        >>> from app.core.chunking import process_content
        >>> chunks = process_content(raw_content)
        >>> for chunk in chunks:
        ...     print(f"Chunk {chunk.index}: {chunk.tokens} tokens")
    """
    if config is None:
        config = get_chunking_config()
    
    # 1. Pré-processar (deduplicação e normalização)
    preprocessor = ContentPreprocessor(config)
    clean_content, preprocess_stats = preprocessor.preprocess(raw_content)
    
    # 2. Dividir em chunks
    chunker = SmartChunker(config)
    chunks = chunker.chunk_content(clean_content)
    
    # 3. Validar e corrigir chunks inválidos
    validator = ChunkValidator(config)
    valid_chunks = validator.validate_all(chunks).valid_chunks
    
    return valid_chunks


__all__ = [
    "ChunkingConfig",
    "DedupeConfig", 
    "TokenizerConfig",
    "get_chunking_config",
    "load_chunking_config",
    "ContentPreprocessor",
    "DedupeStats",
    "PreprocessStats",
    "preprocess_content",
    "SmartChunker",
    "Chunk",
    "chunk_content",
    "ChunkValidator",
    "ValidationResult",
    "BatchValidationResult",
    "validate_chunks",
    "process_content",
]

