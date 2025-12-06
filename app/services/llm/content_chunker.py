"""
Chunking de conteúdo para processamento por LLM.
Divide conteúdo grande em partes menores respeitando limites de tokens.
"""

import logging
from typing import List
from .constants import llm_config

logger = logging.getLogger(__name__)


def estimate_tokens(text: str, include_overhead: bool = True) -> int:
    """
    Estima a quantidade de tokens em um texto.
    Aproximação melhorada para português e conteúdo HTML/Markdown.
    """
    base_tokens = len(text) // llm_config.chars_per_token
    
    if include_overhead:
        return int(base_tokens + llm_config.system_prompt_overhead)
    
    return int(base_tokens)


def chunk_content(text: str, max_tokens: int = 500_000) -> List[str]:
    """
    Divide o conteúdo em chunks respeitando o limite de tokens.
    
    Estratégia: Agrupamento Inteligente (Smart Chunking)
    - Agrupa múltiplas páginas pequenas em um único chunk
    - Mantém páginas processadas isoladamente se forem muito grandes
    - Só divide uma página se ela exceder o limite de tokens
    """
    page_markers = text.split("--- PAGE START:")
    raw_pages = []
    
    for i, page in enumerate(page_markers):
        if i == 0 and not page.strip():
            continue
        
        page_content = "--- PAGE START:" + page if i > 0 else page
        page_tokens = estimate_tokens(page_content)
        
        if page_tokens > max_tokens:
            logger.warning(
                f"⚠️ Página {i+1} muito grande ({page_tokens:,} tokens), dividindo..."
            )
            page_chunks = _split_large_page(page_content, max_tokens)
            raw_pages.extend(page_chunks)
            logger.info(f"  📄 Página {i+1} dividida em {len(page_chunks)} partes")
        else:
            raw_pages.append(page_content)
    
    # Agrupar páginas em chunks maiores
    group_target = llm_config.group_target_tokens
    grouped_chunks = []
    current_group = ""
    current_tokens = 0
    
    logger.debug(f"Agrupando {len(raw_pages)} páginas em chunks (Alvo: {group_target} tokens)")
    
    for page in raw_pages:
        page_tokens = estimate_tokens(page, include_overhead=False)
        
        if current_tokens + page_tokens > group_target and current_group:
            grouped_chunks.append(current_group)
            current_group = page
            current_tokens = page_tokens
        else:
            if current_group:
                current_group += "\n\n" + page
            else:
                current_group = page
            current_tokens += page_tokens
            
    if current_group:
        grouped_chunks.append(current_group)
    
    logger.debug(f"✅ Consolidado: {len(grouped_chunks)} chunks de {len(raw_pages)} páginas")
    return grouped_chunks


def _split_large_page(page_content: str, max_tokens: int) -> List[str]:
    """
    Divide uma página muito grande em múltiplos chunks menores.
    Tenta dividir por parágrafos ou linhas para manter contexto.
    """
    safe_max_tokens = int(max_tokens * 0.8)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    paragraphs = page_content.split('\n\n')
    
    if len(paragraphs) == 1:
        paragraphs = page_content.split('\n')
    
    for para in paragraphs:
        para_with_sep = para + ('\n\n' if '\n\n' in page_content else '\n')
        para_tokens = estimate_tokens(para_with_sep)
        
        if para_tokens > safe_max_tokens:
            logger.warning(f"⚠️ Parágrafo muito grande ({para_tokens} tokens), dividindo por linhas...")
            para_lines = para.split('\n')
            for line in para_lines:
                line_with_newline = line + '\n'
                line_tokens = estimate_tokens(line_with_newline)
                
                if line_tokens > safe_max_tokens:
                    logger.warning(f"⚠️ Linha muito grande ({line_tokens} tokens), truncando...")
                    max_chars = int(safe_max_tokens * 2.5)
                    truncated = line[:max_chars]
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                        current_tokens = 0
                    chunks.append(truncated)
                    continue
                
                if current_tokens + line_tokens > safe_max_tokens:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = line_with_newline
                    current_tokens = line_tokens
                else:
                    current_chunk += line_with_newline
                    current_tokens += line_tokens
            continue
        
        if current_tokens + para_tokens > safe_max_tokens:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para_with_sep
            current_tokens = para_tokens
        else:
            current_chunk += para_with_sep
            current_tokens += para_tokens
    
    if current_chunk:
        chunks.append(current_chunk)
    
    # Validar que todos os chunks estão dentro do limite
    for i, chunk in enumerate(chunks):
        chunk_tokens = estimate_tokens(chunk)
        if chunk_tokens > max_tokens:
            logger.warning(f"⚠️ Chunk {i+1} ainda excede limite, truncando...")
            max_chars = int(max_tokens * 2.5)
            chunks[i] = chunk[:max_chars]
    
    return chunks

