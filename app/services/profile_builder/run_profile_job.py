"""
Execução de um job de montagem de perfil para um cnpj_basico.
Reutilizado pelo endpoint v2 montagem_perfil (in-process) e pelo worker (queue).
1 job = 1 empresa = todos os chunks = 1 perfil.
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any

from app.schemas.profile import CompanyProfile
from app.services.database_service import get_db_service
from app.services.agents.profile_extractor_agent import get_profile_extractor_agent
from app.services.profile_builder.profile_merger import merge_profiles
from app.core.phoenix_tracer import trace_llm_call

logger = logging.getLogger(__name__)


async def run_profile_job(
    cnpj_basico: str,
    chunks_data: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Processa todos os chunks do cnpj_basico: extrai perfil por chunk em paralelo,
    merge e salva em company_profile. Não levanta exceção em caso de sem chunks
    ou sem perfis válidos (apenas return). Levanta exceção em falha de merge/save
    para o worker fazer fail(job_id).

    Se chunks_data for passado (ex.: do get_chunks_batch no worker), não busca no DB.
    """
    db_service = get_db_service()
    if chunks_data is None:
        chunks_data = await db_service.get_chunks(cnpj_basico)

    if not chunks_data:
        logger.warning(f"[run_profile_job] Nenhum chunk encontrado para cnpj={cnpj_basico}")
        return

    chunks_count = len(chunks_data)
    logger.info(f"[run_profile_job] {chunks_count} chunks para cnpj={cnpj_basico}")

    profile_extractor = get_profile_extractor_agent()

    async def extract_chunk(chunk_data: dict, chunk_idx: int) -> CompanyProfile:
        chunk_content = chunk_data.get("chunk_content", "")
        if not chunk_content or len(chunk_content.strip()) < 100:
            return CompanyProfile()
        try:
            async with trace_llm_call("profile-llm", f"extract_profile_chunk_{chunk_idx}") as span:
                if span:
                    span.set_attribute("cnpj_basico", cnpj_basico)
                    span.set_attribute("chunk_index", chunk_idx)
                    span.set_attribute("chunk_tokens", chunk_data.get("token_count", 0))
                profile = await profile_extractor.extract_profile(
                    content=chunk_content,
                    ctx_label="",
                    request_id="",
                )
                if span:
                    span.set_attribute(
                        "profile_empty",
                        profile.is_empty() if hasattr(profile, "is_empty") else False,
                    )
                return profile
        except Exception as e:
            logger.warning(f"[run_profile_job] Erro chunk {chunk_idx}: {e}")
            return CompanyProfile()

    profile_tasks = [
        extract_chunk(chunk_data, idx) for idx, chunk_data in enumerate(chunks_data)
    ]
    profiles_results = await asyncio.gather(*profile_tasks, return_exceptions=True)

    valid_profiles = []
    for idx, profile_result in enumerate(profiles_results):
        if isinstance(profile_result, Exception):
            logger.warning(f"[run_profile_job] Exceção chunk {idx}: {profile_result}")
            continue
        if profile_result and isinstance(profile_result, CompanyProfile):
            if hasattr(profile_result, "is_empty") and not profile_result.is_empty():
                valid_profiles.append(profile_result)
            elif not hasattr(profile_result, "is_empty"):
                profile_dict = (
                    profile_result.model_dump()
                    if hasattr(profile_result, "model_dump")
                    else {}
                )
                ide = profile_dict.get("identidade") or {}
                cla = profile_dict.get("classificacao") or {}
                if ide.get("nome_empresa") or cla.get("industria"):
                    valid_profiles.append(profile_result)

    if not valid_profiles:
        logger.warning(f"[run_profile_job] Nenhum perfil válido para cnpj={cnpj_basico}")
        return

    try:
        merged_profile = merge_profiles(valid_profiles)
    except Exception as e:
        logger.error(f"[run_profile_job] Erro ao mergear perfis: {e}", exc_info=True)
        merged_profile = valid_profiles[0] if valid_profiles else CompanyProfile()

    company_id = await db_service.save_profile(
        cnpj_basico=cnpj_basico,
        profile=merged_profile,
    )
    logger.info(
        f"[run_profile_job] Concluído cnpj={cnpj_basico}, "
        f"chunks={len(valid_profiles)}/{chunks_count}, company_id={company_id}"
    )
