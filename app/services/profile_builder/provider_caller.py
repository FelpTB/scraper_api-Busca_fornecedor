"""
Chamadas aos provedores de LLM com retry e fallback.
NOTA: Este módulo é mantido para compatibilidade.
Use LLMService para novas implementações.
"""

import json
import re
import asyncio
import time
import logging
from typing import Optional
import json_repair

from app.schemas.profile import CompanyProfile
from .constants import SYSTEM_PROMPT
from .response_normalizer import normalize_llm_response

# Importar diretamente de llm_manager
from app.services.llm_manager import (
    provider_manager,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderBadRequestError,
    health_monitor,
    FailureType
)

logger = logging.getLogger(__name__)


async def call_llm(provider: str, text_content: str) -> CompanyProfile:
    """
    Faz a chamada ao LLM via ProviderManager.
    """
    content_size = len(text_content)
    logger.info(f"🚀 [LLM_REQUEST_START] {provider}: {content_size:,} chars")
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analise este conteúdo e extraia os dados em Português:\n\n{text_content}"}
    ]
    
    start_ts = time.perf_counter()
    
    # Usar json_schema quando disponível (SGLang), fallback para json_object
    try:
        # Gerar JSON Schema do CompanyProfile
        json_schema = CompanyProfile.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "company_profile",
                "schema": json_schema
            }
        }
    except Exception as e:
        logger.warning(f"⚠️ Erro ao gerar json_schema, usando json_object: {e}")
        response_format = {"type": "json_object"}
    
    try:
        response_content, latency_ms = await provider_manager.call(
            provider=provider,
            messages=messages,
            response_format=response_format
        )
        
        health_monitor.record_success(provider, latency_ms)
        
        # Parse resposta
        return _parse_llm_response(response_content, provider, start_ts)
    
    except ProviderRateLimitError as e:
        health_monitor.record_failure(provider, FailureType.RATE_LIMIT)
        raise
    except ProviderTimeoutError as e:
        health_monitor.record_failure(provider, FailureType.TIMEOUT)
        raise
    except ProviderError as e:
        health_monitor.record_failure(provider, FailureType.ERROR)
        raise


def _parse_llm_response(raw_content: str, provider: str, start_ts: float) -> CompanyProfile:
    """Parse e valida resposta JSON do LLM com extração robusta."""
    content = raw_content.strip()
    
    # Estratégia 1: Parse direto
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Estratégia 2: Remover markdown
        if "```json" in content:
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                content = match.group(1).strip()
        elif "```" in content:
            match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                content = match.group(1).strip()
        
        # Estratégia 3: Extrair primeiro objeto JSON válido
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Procurar por { ... } balanceado
            brace_start = content.find('{')
            if brace_start != -1:
                brace_count = 0
                brace_end = -1
                for i in range(brace_start, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            brace_end = i + 1
                            break
                
                if brace_end > brace_start:
                    content = content[brace_start:brace_end]
            
            # Estratégia 4: json_repair como último recurso
            try:
                data = json_repair.loads(content)
            except Exception:
                logger.warning(f"⚠️ JSON padrão falhou para {provider}. Tentando reparar...")
                try:
                    data = json_repair.loads(raw_content)
                except Exception as e:
                    logger.error(f"❌ Falha crítica no parse JSON: {e}")
                    return CompanyProfile()
    
    # Normalizar estrutura
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    if not isinstance(data, dict):
        data = {}
    
    try:
        data = normalize_llm_response(data)
        profile = CompanyProfile(**data)
        total_duration = time.perf_counter() - start_ts
        logger.info(f"✅ [LLM_SUCCESS] CompanyProfile criado de {provider} em {total_duration:.3f}s")
        return profile
    except Exception as e:
        logger.error(f"❌ Erro ao construir CompanyProfile: {e}")
        return CompanyProfile()


async def analyze_content_with_fallback(
    text_content: str, 
    provider_name: Optional[str] = None
) -> CompanyProfile:
    """
    Analisa conteúdo com fallback automático entre provedores.
    """
    providers = provider_manager.available_providers
    
    if provider_name and provider_name in providers:
        providers_to_try = [provider_name] + [p for p in providers if p != provider_name]
    else:
        providers_to_try = providers
    
    last_error = None
    
    for provider in providers_to_try:
        try:
            logger.debug(f"🚀 [LLM_ATTEMPT] {provider}")
            return await call_llm(provider, text_content)
        
        except ProviderBadRequestError as e:
            logger.error(f"❌ [LLM_BAD_REQUEST] {provider}: {e}")
            raise
        
        except (ProviderRateLimitError, ProviderTimeoutError, ProviderError) as e:
            logger.warning(f"⚠️ [LLM_ERROR] {provider}: {type(e).__name__}")
            last_error = e
            continue
    
    logger.error(f"💥 [LLM_ALL_FAILED] Todos provedores falharam")
    return CompanyProfile()


async def process_chunk_with_retry(
    chunk: str, 
    chunk_num: int, 
    total_chunks: int, 
    primary_provider: Optional[str] = None
) -> Optional[CompanyProfile]:
    """
    Processa um chunk com retry e fallback entre provedores.
    """
    logger.info(f"📄 Processando Chunk {chunk_num}/{total_chunks}")
    
    try:
        profile = await analyze_content_with_fallback(chunk, primary_provider)
        logger.info(f"✅ Chunk {chunk_num}/{total_chunks} processado")
        return profile
    except Exception as e:
        logger.warning(f"⚠️ Chunk {chunk_num}: primeira tentativa falhou: {type(e).__name__}")
    
    # Retry com delay
    await asyncio.sleep(2)
    
    try:
        profile = await analyze_content_with_fallback(chunk, primary_provider)
        logger.info(f"✅ Chunk {chunk_num}: sucesso no retry")
        return profile
    except Exception as e:
        logger.error(f"❌ Chunk {chunk_num}: falhou após retry: {e}")
        return None
