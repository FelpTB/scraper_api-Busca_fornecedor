"""
Endpoint Montagem Perfil v2 - Extração assíncrona de perfil com paralelismo.
"""
import logging
import time
import asyncio
from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.v2.profile import ProfileRequest, ProfileResponse
from app.services.database_service import DatabaseService, get_db_service
from app.services.agents.profile_extractor_agent import get_profile_extractor_agent
from app.services.profile_builder.profile_merger import merge_profiles
from app.core.phoenix_tracer import trace_llm_call
from app.schemas.profile import CompanyProfile

logger = logging.getLogger(__name__)

router = APIRouter()
db_service = get_db_service()


@router.post("/montagem_perfil", response_model=ProfileResponse)
async def montar_perfil(request: ProfileRequest) -> ProfileResponse:
    """
    Monta perfil completo da empresa processando chunks em paralelo.
    
    Fluxo:
    1. Busca chunks salvos no banco de dados
    2. Processa chunks em paralelo usando ProfileExtractorAgent (com Phoenix tracing)
    3. Mergeia perfis parciais em um perfil completo
    4. Salva perfil no banco de dados
    5. Retorna resposta com estatísticas de processamento
    
    Args:
        request: CNPJ básico da empresa
    
    Returns:
        ProfileResponse com estatísticas (company_id, profile_status, chunks_processed, processing_time_ms)
    
    Raises:
        HTTPException: Em caso de erro no processamento ou persistência
    """
    start_time = time.perf_counter()
    
    try:
        logger.info(f"🔍 Montagem Perfil: cnpj={request.cnpj_basico}")
        
        # 1. Buscar chunks do banco de dados (assíncrono)
        chunks_start = time.perf_counter()
        chunks_data = await db_service.get_chunks(request.cnpj_basico)
        chunks_duration = (time.perf_counter() - chunks_start) * 1000
        
        if not chunks_data:
            logger.warning(f"⚠️ Nenhum chunk encontrado para cnpj={request.cnpj_basico}")
            return ProfileResponse(
                success=False,
                company_id=None,
                profile_status="error",
                chunks_processed=0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        chunks_count = len(chunks_data)
        logger.info(f"✅ {chunks_count} chunks encontrados em {chunks_duration:.1f}ms (cnpj={request.cnpj_basico})")
        
        # 2. Processar chunks em paralelo usando ProfileExtractorAgent (assíncrono com Phoenix tracing)
        extraction_start = time.perf_counter()
        profile_extractor = get_profile_extractor_agent()
        
        # Lista de tasks para processamento paralelo
        async def extract_chunk(chunk_data: dict, chunk_idx: int) -> CompanyProfile:
            """Extrai perfil de um chunk com Phoenix tracing."""
            chunk_content = chunk_data.get('chunk_content', '')
            
            if not chunk_content or len(chunk_content.strip()) < 100:
                logger.debug(f"⚠️ Chunk {chunk_idx} muito curto ou vazio (cnpj={request.cnpj_basico})")
                return CompanyProfile()
            
            try:
                async with trace_llm_call("profile-llm", f"extract_profile_chunk_{chunk_idx}") as span:
                    if span:
                        span.set_attribute("cnpj_basico", request.cnpj_basico)
                        span.set_attribute("chunk_index", chunk_idx)
                        span.set_attribute("chunk_tokens", chunk_data.get('token_count', 0))
                    
                    profile = await profile_extractor.extract_profile(
                        content=chunk_content,
                        ctx_label="",
                        request_id=""
                    )
                    
                    if span:
                        span.set_attribute("profile_empty", profile.is_empty() if hasattr(profile, 'is_empty') else False)
                    
                    return profile
            except Exception as e:
                logger.warning(f"⚠️ Erro ao processar chunk {chunk_idx}: {e} (cnpj={request.cnpj_basico})")
                return CompanyProfile()
        
        # Processar todos os chunks em paralelo
        profile_tasks = [extract_chunk(chunk_data, idx) for idx, chunk_data in enumerate(chunks_data)]
        profiles_results = await asyncio.gather(*profile_tasks, return_exceptions=True)
        
        extraction_duration = (time.perf_counter() - extraction_start) * 1000
        
        # Filtrar perfis válidos (não são exceções e não estão vazios)
        valid_profiles = []
        for idx, profile_result in enumerate(profiles_results):
            if isinstance(profile_result, Exception):
                logger.warning(f"⚠️ Exceção ao processar chunk {idx}: {profile_result} (cnpj={request.cnpj_basico})")
                continue
            
            if profile_result and isinstance(profile_result, CompanyProfile):
                # Verificar se o perfil não está vazio
                if hasattr(profile_result, 'is_empty') and not profile_result.is_empty():
                    valid_profiles.append(profile_result)
                elif not hasattr(profile_result, 'is_empty'):
                    # Se não tem método is_empty, assumir que não está vazio se tem dados básicos
                    profile_dict = profile_result.model_dump() if hasattr(profile_result, 'model_dump') else {}
                    if profile_dict.get('identity', {}).get('company_name') or profile_dict.get('classification', {}).get('industry'):
                        valid_profiles.append(profile_result)
        
        chunks_processed = len(valid_profiles)
        
        logger.info(
            f"✅ Extração concluída: {chunks_processed}/{chunks_count} perfis válidos "
            f"em {extraction_duration:.1f}ms (cnpj={request.cnpj_basico})"
        )
        
        if chunks_processed == 0:
            logger.warning(f"⚠️ Nenhum perfil válido extraído para cnpj={request.cnpj_basico}")
            return ProfileResponse(
                success=False,
                company_id=None,
                profile_status="error",
                chunks_processed=0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        # 3. Mergear perfis parciais em um perfil completo (síncrono, mas rápido ~5ms)
        merge_start = time.perf_counter()
        try:
            merged_profile = merge_profiles(valid_profiles)
            merge_duration = (time.perf_counter() - merge_start) * 1000
            
            logger.info(
                f"✅ Merge concluído: {chunks_processed} perfis mergeados em {merge_duration:.1f}ms "
                f"(cnpj={request.cnpj_basico})"
            )
        except Exception as e:
            logger.error(f"❌ Erro ao mergear perfis: {e}", exc_info=True)
            # Tentar usar o primeiro perfil válido como fallback
            if valid_profiles:
                merged_profile = valid_profiles[0]
                logger.warning(f"⚠️ Usando primeiro perfil como fallback (cnpj={request.cnpj_basico})")
            else:
                merged_profile = CompanyProfile()
        
        # 4. Salvar perfil no banco de dados (assíncrono)
        save_start = time.perf_counter()
        try:
            company_id = await db_service.save_profile(
                cnpj_basico=request.cnpj_basico,
                profile=merged_profile
            )
            save_duration = (time.perf_counter() - save_start) * 1000
            
            logger.info(
                f"✅ Perfil salvo no banco: id={company_id} em {save_duration:.1f}ms "
                f"(cnpj={request.cnpj_basico})"
            )
        except Exception as e:
            logger.error(f"❌ Erro ao salvar perfil no banco: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao salvar perfil no banco de dados: {str(e)}"
            )
        
        # 5. Determinar status do processamento
        # Se processou todos os chunks com sucesso, status é "success"
        # Se processou alguns mas não todos, status é "partial"
        # Se não processou nenhum, status é "error" (já tratado acima)
        if chunks_processed == chunks_count:
            profile_status = "success"
        elif chunks_processed > 0:
            profile_status = "partial"
        else:
            profile_status = "error"
        
        # 6. Retornar resposta
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"✅ Montagem Perfil concluída: cnpj={request.cnpj_basico}, "
            f"status={profile_status}, {chunks_processed}/{chunks_count} chunks processados, "
            f"company_id={company_id}, {processing_time_ms:.1f}ms total"
        )
        
        return ProfileResponse(
            success=True,
            company_id=company_id,
            profile_status=profile_status,
            chunks_processed=chunks_processed,
            processing_time_ms=processing_time_ms
        )
    
    except HTTPException:
        # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(f"❌ Erro no endpoint montagem_perfil: {e}", exc_info=True)
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar montagem de perfil: {str(e)}"
        )

