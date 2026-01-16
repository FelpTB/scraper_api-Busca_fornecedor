"""
Endpoint Serper v2 - Busca assíncrona no Google via Serper API.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.v2.serper import SerperRequest, SerperResponse
from app.services.discovery_manager.serper_manager import serper_manager
from app.services.database_service import DatabaseService, get_db_service

logger = logging.getLogger(__name__)

router = APIRouter()
db_service = get_db_service()


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


@router.post("/serper", response_model=SerperResponse)
async def buscar_serper(request: SerperRequest) -> SerperResponse:
    """
    Busca informações da empresa no Google via Serper API.
    
    Fluxo:
    1. Constrói query de busca a partir dos dados da empresa
    2. Executa busca assíncrona via Serper API
    3. Salva resultados no banco de dados
    4. Retorna resposta com ID e contagem de resultados
    
    Args:
        request: Dados da empresa para busca (cnpj_basico, razao_social, nome_fantasia, municipio)
    
    Returns:
        SerperResponse com sucesso, ID do registro, contagem de resultados e query usada
    
    Raises:
        HTTPException: Em caso de erro na busca ou persistência
    """
    try:
        # 1. Construir query de busca
        query = _build_search_query(
            razao_social=request.razao_social,
            nome_fantasia=request.nome_fantasia,
            municipio=request.municipio
        )
        
        logger.info(f"🔍 Serper busca: cnpj={request.cnpj_basico}, query='{query}'")
        
        # 2. Executar busca assíncrona via Serper
        results, retries = await serper_manager.search(
            query=query,
            num_results=10,  # Número padrão de resultados
            country="br",
            language="pt-br",
            request_id=""
        )
        
        if not results:
            logger.warning(f"⚠️ Nenhum resultado encontrado para query: {query}")
            # Salvar mesmo sem resultados para histórico
            serper_id = await db_service.save_serper_results(
                cnpj_basico=request.cnpj_basico,
                results=[],
                query_used=query,
                company_name=request.nome_fantasia or request.razao_social,
                razao_social=request.razao_social,
                nome_fantasia=request.nome_fantasia,
                municipio=request.municipio
            )
            
            return SerperResponse(
                success=True,
                serper_id=serper_id,
                results_count=0,
                query_used=query
            )
        
        # 3. Salvar resultados no banco de dados
        serper_id = await db_service.save_serper_results(
            cnpj_basico=request.cnpj_basico,
            results=results,
            query_used=query,
            company_name=request.nome_fantasia or request.razao_social,
            razao_social=request.razao_social,
            nome_fantasia=request.nome_fantasia,
            municipio=request.municipio
        )
        
        logger.info(
            f"✅ Serper busca concluída: cnpj={request.cnpj_basico}, "
            f"results={len(results)}, serper_id={serper_id}"
        )
        
        # 4. Retornar resposta
        return SerperResponse(
            success=True,
            serper_id=serper_id,
            results_count=len(results),
            query_used=query
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao buscar Serper: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar informações no Serper: {str(e)}"
        )

