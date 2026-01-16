"""
Módulo para salvar arquivos brutos do profile_builder para análise.

Salva:
1. Conteúdo bruto que entra no analyze_content
2. Chunks gerados pelo chunking
3. Estatísticas de tokens
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from app.core.token_utils import estimate_tokens

logger = logging.getLogger(__name__)

# Diretório para salvar arquivos de debug
DEBUG_DIR = Path("debug_profile_builder")
DEBUG_DIR.mkdir(exist_ok=True, parents=True)


def save_raw_content(
    content: str,
    request_id: str,
    url: str = None,
    cnpj: str = None,
    company_name: str = None
) -> Dict[str, Any]:
    """
    Salva o conteúdo bruto que entra no analyze_content.
    
    Returns:
        Dict com informações sobre o arquivo salvo
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Nome do arquivo
    safe_name = (company_name or cnpj or "unknown")[:50].replace("/", "_").replace("\\", "_")
    filename = f"raw_content_{timestamp}_{request_id}_{safe_name}.txt"
    filepath = DEBUG_DIR / filename
    
    # Estatísticas
    stats = {
        "request_id": request_id,
        "url": url,
        "cnpj": cnpj,
        "company_name": company_name,
        "timestamp": timestamp,
        "content_length": len(content),
        "content_length_chars": len(content),
        "estimated_tokens": estimate_tokens(content, include_overhead=False),
        "estimated_tokens_with_overhead": estimate_tokens(content, include_overhead=True),
        "num_pages": content.count("--- PAGE START:") + 1 if "--- PAGE START:" in content else 1,
        "filepath": str(filepath),
        "filename": filename
    }
    
    # Salvar conteúdo
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"💾 [DEBUG] Conteúdo bruto salvo: {filename}")
        
        # Salvar metadados em JSON separado
        metadata_file = filepath.with_suffix(".metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        return stats
    except Exception as e:
        logger.error(f"❌ [DEBUG] Erro ao salvar conteúdo bruto: {e}")
        return stats


def save_chunks(
    chunks: List[str],
    request_id: str,
    raw_content_stats: Dict[str, Any],
    max_chunk_tokens: int
) -> Dict[str, Any]:
    """
    Salva os chunks gerados pelo chunking.
    
    Returns:
        Dict com informações sobre os chunks salvos
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Nome base
    safe_name = (raw_content_stats.get("company_name") or raw_content_stats.get("cnpj") or "unknown")[:50]
    safe_name = safe_name.replace("/", "_").replace("\\", "_")
    
    chunks_info = []
    chunks_dir = DEBUG_DIR / f"chunks_{timestamp}_{request_id}_{safe_name}"
    chunks_dir.mkdir(exist_ok=True, parents=True)
    
    # Salvar cada chunk
    for i, chunk in enumerate(chunks):
        chunk_filename = f"chunk_{i+1}_of_{len(chunks)}.txt"
        chunk_filepath = chunks_dir / chunk_filename
        
        chunk_stats = {
            "chunk_number": i + 1,
            "total_chunks": len(chunks),
            "chunk_length_chars": len(chunk),
            "estimated_tokens": estimate_tokens(chunk, include_overhead=False),
            "estimated_tokens_with_overhead": estimate_tokens(chunk, include_overhead=True),
            "max_chunk_tokens": max_chunk_tokens,
            "exceeds_limit": estimate_tokens(chunk, include_overhead=True) > max_chunk_tokens,
            "filepath": str(chunk_filepath),
            "filename": chunk_filename
        }
        
        try:
            with open(chunk_filepath, "w", encoding="utf-8") as f:
                f.write(chunk)
            chunks_info.append(chunk_stats)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Erro ao salvar chunk {i+1}: {e}")
            chunks_info.append(chunk_stats)
    
    # Salvar índice de chunks
    index_file = chunks_dir / "index.json"
    index_data = {
        "request_id": request_id,
        "timestamp": timestamp,
        "total_chunks": len(chunks),
        "raw_content_stats": raw_content_stats,
        "max_chunk_tokens": max_chunk_tokens,
        "chunks": chunks_info
    }
    
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ [DEBUG] Erro ao salvar índice de chunks: {e}")
    
    logger.info(f"💾 [DEBUG] {len(chunks)} chunks salvos em: {chunks_dir.name}")
    
    return index_data


def analyze_content_quality(content: str) -> Dict[str, Any]:
    """
    Analisa a qualidade do conteúdo para identificar problemas.
    
    Returns:
        Dict com métricas de qualidade
    """
    # Contar caracteres especiais/desnecessários
    whitespace_chars = sum(1 for c in content if c.isspace())
    newlines = content.count('\n')
    tabs = content.count('\t')
    spaces = content.count(' ')
    
    # Contar sequências de espaços em branco excessivas
    import re
    excessive_whitespace = len(re.findall(r'\n{3,}', content))
    excessive_spaces = len(re.findall(r' {3,}', content))
    
    # Contar caracteres não-ASCII
    non_ascii_chars = sum(1 for c in content if ord(c) > 127)
    
    # Contar caracteres de controle (exceto newlines e tabs normais)
    control_chars = sum(1 for c in content if ord(c) < 32 and c not in '\n\r\t')
    
    # Estimar redundância (linhas duplicadas consecutivas)
    lines = content.split('\n')
    duplicate_lines = sum(1 for i in range(1, len(lines)) if lines[i] == lines[i-1] and lines[i].strip())
    
    return {
        "total_length": len(content),
        "whitespace_chars": whitespace_chars,
        "newlines": newlines,
        "tabs": tabs,
        "spaces": spaces,
        "excessive_whitespace_segments": excessive_whitespace,
        "excessive_spaces_segments": excessive_spaces,
        "non_ascii_chars": non_ascii_chars,
        "control_chars": control_chars,
        "duplicate_lines": duplicate_lines,
        "total_lines": len(lines),
        "avg_line_length": sum(len(line) for line in lines) / len(lines) if lines else 0,
        "has_page_markers": "--- PAGE START:" in content,
        "num_pages": content.count("--- PAGE START:") + 1 if "--- PAGE START:" in content else 1
    }

