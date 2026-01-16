"""
Chunking de conteúdo para processamento por LLM.
Divide conteúdo grande em partes menores respeitando limites de tokens.

⚠️ DEPRECATED: Este módulo está deprecated. Use app.core.chunking.process_content() ao invés.

Este módulo será removido em uma versão futura. Migre para:
    from app.core.chunking import process_content
    
    chunks = process_content(raw_content)
    chunk_strings = [chunk.content for chunk in chunks]  # Se precisar de strings
"""

import logging
import warnings
from typing import List
from .constants import llm_config
from app.core.token_utils import estimate_tokens, calculate_safety_margin

logger = logging.getLogger(__name__)


def chunk_content(text: str, max_tokens: int = 500_000) -> List[str]:
    """
    ⚠️ DEPRECATED: Use app.core.chunking.process_content() ao invés.
    
    Divide o conteúdo em chunks respeitando o limite de tokens.
    
    Estratégia: Agrupamento Inteligente (Smart Chunking)
    - Agrupa múltiplas páginas pequenas em um único chunk
    - Mantém páginas processadas isoladamente se forem muito grandes
    - Só divide uma página se ela exceder o limite de tokens
    
    OTIMIZAÇÃO v2.0: group_target_tokens aumentado para 100K
    - Reduz significativamente o número de chamadas LLM
    - Empresa típica: 1-2 chunks ao invés de 5-10
    
    FIX v3.0: Considera overhead do system prompt e mensagens
    - Calcula effective_max_tokens descontando overhead
    - Previne chunks que excederiam limite ao enviar ao LLM
    """
    warnings.warn(
        "content_chunker.chunk_content está deprecated. "
        "Use app.core.chunking.process_content() ao invés.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # RECOMENDAÇÃO 1: Calcular effective_max_tokens descontando overhead
    # Overhead inclui: system prompt (~2500 tokens) + message formatting (~200 tokens para 2 mensagens)
    message_overhead = 200  # ~100 tokens por mensagem * 2 mensagens (system + user)
    base_effective_max_tokens = max_tokens - llm_config.system_prompt_overhead - message_overhead
    
    if base_effective_max_tokens <= 0:
        logger.warning(
            f"⚠️ max_tokens ({max_tokens}) muito pequeno após descontar overhead "
            f"({llm_config.system_prompt_overhead} + {message_overhead}). "
            f"Usando 80% do max_tokens como fallback."
        )
        base_effective_max_tokens = int(max_tokens * 0.8)
    
    total_tokens = estimate_tokens(text, include_overhead=False)
    
    # NOVA: Calcular margem de segurança dinâmica baseada no conteúdo
    # Isso aplica margens extras para conteúdo repetitivo ou chunks grandes
    effective_max_tokens, margin_info = calculate_safety_margin(
        content=text,
        estimated_tokens=total_tokens,
        base_effective_max=base_effective_max_tokens
    )
    
    if margin_info["total_margin"] > 0:
        logger.info(
            f"Chunking: Margem de segurança aplicada "
            f"(repetição: {margin_info['repetition_rate']*100:.1f}%, "
            f"tamanho: {total_tokens:,} tokens) → "
            f"margem: {margin_info['total_margin']*100:.0f}% "
            f"(effective_max: {base_effective_max_tokens:,} → {effective_max_tokens:,})"
        )
    else:
        logger.debug(
            f"Chunking: max_tokens={max_tokens:,}, effective_max_tokens={effective_max_tokens:,} "
            f"(descontados {llm_config.system_prompt_overhead + message_overhead} tokens de overhead)"
        )
    
    page_markers = text.split("--- PAGE START:")
    raw_pages = []
    
    for i, page in enumerate(page_markers):
        if i == 0 and not page.strip():
            continue
        
        page_content = "--- PAGE START:" + page if i > 0 else page
        page_tokens = estimate_tokens(page_content, include_overhead=False)
        
        # Usar effective_max_tokens ao invés de max_tokens
        if page_tokens > effective_max_tokens:
            logger.warning(
                f"⚠️ Página {i+1} muito grande ({page_tokens:,} tokens), dividindo..."
            )
            page_chunks = _split_large_page(page_content, effective_max_tokens)
            raw_pages.extend(page_chunks)
            logger.info(f"  📄 Página {i+1} dividida em {len(page_chunks)} partes")
        else:
            raw_pages.append(page_content)
    
    # Agrupar páginas em chunks maiores
    group_target = llm_config.group_target_tokens
    grouped_chunks = []
    current_group = ""
    current_tokens = 0
    
    logger.debug(f"Agrupando {len(raw_pages)} páginas em chunks (Alvo: {group_target:,} tokens)")
    
    for page in raw_pages:
        page_tokens = estimate_tokens(page, include_overhead=False)
        
        # Calcular margem de segurança para o chunk potencial (current_group + page)
        potential_chunk = current_group + "\n\n" + page if current_group else page
        potential_tokens = current_tokens + page_tokens
        
        # Calcular effective_max ajustado com margem de segurança
        potential_adjusted_max, _ = calculate_safety_margin(
            content=potential_chunk,
            estimated_tokens=potential_tokens,
            base_effective_max=effective_max_tokens
        )
        
        # Validar se adicionar esta página excederia o effective_max_tokens ajustado
        if potential_tokens > potential_adjusted_max and current_group:
            # Chunk atual está completo (ou seria muito grande), salvar e começar novo
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
        # Validar último chunk antes de adicionar (com margem de segurança)
        last_chunk_tokens = estimate_tokens(current_group, include_overhead=False)
        last_adjusted_max, _ = calculate_safety_margin(
            content=current_group,
            estimated_tokens=last_chunk_tokens,
            base_effective_max=effective_max_tokens
        )
        
        if last_chunk_tokens > last_adjusted_max:
            # Último chunk excede mesmo com margem, precisa ser dividido
            logger.warning(
                f"⚠️ Último chunk excede limite mesmo com margem ({last_chunk_tokens:,} > {last_adjusted_max:,} tokens), "
                f"dividindo..."
            )
            # Dividir o último chunk
            last_chunks = _split_large_page(current_group, last_adjusted_max)
            grouped_chunks.extend(last_chunks)
        else:
            grouped_chunks.append(current_group)
    
    # Log de otimização: mostrar economia de chamadas LLM
    old_chunks_estimate = max(1, total_tokens // 20_000)  # Estimativa com config antiga
    chunks_saved = old_chunks_estimate - len(grouped_chunks)
    
    if chunks_saved > 0:
        logger.info(
            f"📦 Chunking otimizado: {len(grouped_chunks)} chunks "
            f"({total_tokens:,} tokens, {len(raw_pages)} páginas) "
            f"[economia: {chunks_saved} chamadas LLM]"
        )
    else:
        logger.debug(f"✅ Consolidado: {len(grouped_chunks)} chunks de {len(raw_pages)} páginas")
    
    return grouped_chunks


def _split_large_page(page_content: str, max_tokens: int) -> List[str]:
    """
    Divide uma página muito grande em múltiplos chunks menores.
    Tenta dividir por parágrafos ou linhas para manter contexto.

    CORREÇÃO: Considera overhead completo para chunking mais conservador.

    Args:
        page_content: Conteúdo da página a dividir
        max_tokens: Limite máximo de tokens (já deve ser effective_max_tokens)
    """
    # CORREÇÃO CRÍTICA: Reduzir limite considerando overhead total
    message_overhead = 200
    total_overhead = llm_config.system_prompt_overhead + message_overhead
    effective_max_for_chunking = max_tokens - total_overhead
    safe_max_tokens = int(effective_max_for_chunking * 0.85)  # 85% para margem extra conservadora
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
    
    # Validar que todos os chunks estão dentro do limite (usando overhead completo)
    for i, chunk in enumerate(chunks):
        chunk_tokens_total = estimate_tokens(chunk, include_overhead=True)
        if chunk_tokens_total > max_tokens:
            logger.warning(
                f"⚠️ Chunk {i+1} ainda excede limite ({chunk_tokens_total:,} > {max_tokens:,} tokens), truncando..."
            )
            # Usar lógica iterativa para truncar corretamente
            max_chars = len(chunk)
            while max_chars > 1000:
                max_chars = int(max_chars * 0.9)
                truncated_chunk = chunk[:max_chars]
                truncated_tokens = estimate_tokens(truncated_chunk, include_overhead=True)
                if truncated_tokens <= max_tokens:
                    chunks[i] = truncated_chunk
                    break
    
    return chunks

