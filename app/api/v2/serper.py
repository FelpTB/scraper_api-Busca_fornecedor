"""
Endpoint Serper v2 - Busca assíncrona no Google via API Serpshot.
Processamento em background - retorna imediatamente após aceitar requisição.
Usa batch aggregator para agrupar múltiplas requisições em chamadas únicas à API.
"""
import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.v2.serper import SerperRequest, SerperResponse
from app.services.serper_batch_aggregator import get_serper_batch_aggregator, SerperBatchItem

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_search_query(
    razao_social: Optional[str],
    nome_fantasia: Optional[str],
    municipio: Optional[str]
) -> str:
    """
    Constrói query de busca otimizada.
    
    Prioridade:
    1. Nome Fantasia + Municipio
    2. Razão Social + Municipio (se nome fantasia não existir)
    
    Args:
        razao_social: Razão social da empresa
        nome_fantasia: Nome fantasia da empresa
        municipio: Município da empresa
    
    Returns:
        Query formatada para busca
    """
    nf = nome_fantasia.strip() if nome_fantasia else ""
    rs = razao_social.strip() if razao_social else ""
    city = municipio.strip() if municipio else ""
    
    # Prioridade 1: Nome Fantasia + Municipio
    if nf:
        query = f'{nf} {city} site oficial'.strip()
        return query
    
    # Prioridade 2: Razão Social + Municipio
    if rs:
        # Limpar sufixos comuns
        clean_rs = rs.replace(" LTDA", "").replace(" S.A.", "").replace(" EIRELI", "")
        clean_rs = clean_rs.replace(" ME", "").replace(" EPP", "").replace(" S/A", "").strip()
        if clean_rs:
            query = f'{clean_rs} {city} site oficial'.strip()
            return query
    
    # Fallback: apenas municipio (se existir)
    if city:
        return f'site oficial {city}'.strip()
    
    # Último fallback
    return "site oficial"


async def _process_serper_background(request: SerperRequest):
    """
    Enfileira busca Serper no agregador de batch.
    Requisições simultâneas são agrupadas em chamadas de até 100 queries à API.
    """
    try:
        query = _build_search_query(
            razao_social=request.razao_social,
            nome_fantasia=request.nome_fantasia,
            municipio=request.municipio
        )

        item = SerperBatchItem(
            cnpj_basico=request.cnpj_basico,
            query=query,
            razao_social=request.razao_social,
            nome_fantasia=request.nome_fantasia,
            municipio=request.municipio,
        )
        aggregator = get_serper_batch_aggregator()
        await aggregator.submit(item)
        logger.info(f"🔍 [BATCH] Requisição enfileirada: cnpj={request.cnpj_basico}, query='{query[:60]}'")
    except Exception as e:
        logger.error(f"❌ [BATCH] Erro ao enfileirar busca Serpshot: {e}", exc_info=True)


@router.post("/serper", response_model=SerperResponse)
async def buscar_serper(request: SerperRequest) -> SerperResponse:
    """
    Busca informações da empresa no Google via API Serpshot.
    
    Processamento assíncrono: retorna imediatamente após aceitar a requisição.
    O processamento (busca Serpshot e salvamento) ocorre em background.
    
    Args:
        request: Dados da empresa para busca (cnpj_basico, razao_social, nome_fantasia, municipio)
    
    Returns:
        SerperResponse com confirmação de recebimento da requisição
    
    Raises:
        HTTPException: Em caso de erro ao aceitar requisição
    """
    try:
        logger.info(f"📥 Requisição busca (Serpshot) recebida: cnpj={request.cnpj_basico}")
        
        # Iniciar processamento em background
        asyncio.create_task(_process_serper_background(request))
        
        # Retornar confirmação imediata
        return SerperResponse(
            success=True,
            message=f"Requisição de busca aceita para CNPJ {request.cnpj_basico}. Processamento em background.",
            cnpj_basico=request.cnpj_basico,
            status="accepted"
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao aceitar requisição de busca: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao aceitar requisição: {str(e)}"
        )

