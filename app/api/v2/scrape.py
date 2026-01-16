"""
Endpoint Scrape v2 - Scraping assíncrono de site com chunking e persistência.
"""
import logging
import time
from typing import List
from fastapi import APIRouter, HTTPException
from app.schemas.v2.scrape import ScrapeRequest, ScrapeResponse
from app.services.scraper import scrape_all_subpages
from app.services.scraper.models import ScrapedPage
from app.services.database_service import DatabaseService, get_db_service
from app.core.chunking import process_content

logger = logging.getLogger(__name__)

router = APIRouter()
db_service = get_db_service()


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_website(request: ScrapeRequest) -> ScrapeResponse:
    """
    Faz scraping do site oficial da empresa e salva chunks no banco de dados.
    
    Fluxo:
    1. Faz scraping de todas as subpáginas usando heurísticas (sem LLM)
    2. Agrega conteúdo de todas as páginas
    3. Processa conteúdo em chunks usando process_content_v4 (síncrono, mas rápido)
    4. Busca discovery_id do banco (se existir)
    5. Salva chunks no banco usando batch insert (transação única)
    6. Retorna resposta com estatísticas de scraping e chunking
    
    Args:
        request: CNPJ básico e URL do site
    
    Returns:
        ScrapeResponse com estatísticas (chunks_saved, total_tokens, pages_scraped, processing_time_ms)
    
    Raises:
        HTTPException: Em caso de erro no scraping ou persistência
    """
    start_time = time.perf_counter()
    
    try:
        logger.info(f"🔍 Scrape: cnpj={request.cnpj_basico}, url={request.website_url}")
        
        # 1. Fazer scraping de todas as subpáginas (assíncrono, sem LLM)
        scrape_start = time.perf_counter()
        pages = await scrape_all_subpages(
            url=request.website_url,
            max_subpages=100,
            ctx_label="",
            request_id=""
        )
        scrape_duration = (time.perf_counter() - scrape_start) * 1000
        
        if not pages:
            logger.warning(f"⚠️ Nenhuma página scraped para cnpj={request.cnpj_basico}, url={request.website_url}")
            return ScrapeResponse(
                success=False,
                chunks_saved=0,
                total_tokens=0,
                pages_scraped=0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        # Filtrar apenas páginas com sucesso
        successful_pages = [page for page in pages if page.success]
        pages_scraped = len(successful_pages)
        
        if pages_scraped == 0:
            logger.warning(f"⚠️ Nenhuma página com conteúdo válido para cnpj={request.cnpj_basico}")
            return ScrapeResponse(
                success=False,
                chunks_saved=0,
                total_tokens=0,
                pages_scraped=0,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        logger.info(
            f"✅ Scrape concluído: {pages_scraped} páginas em {scrape_duration:.1f}ms "
            f"(cnpj={request.cnpj_basico})"
        )
        
        # 2. Agregar conteúdo de todas as páginas
        aggregated_content_parts = []
        visited_urls = []
        
        for page in successful_pages:
            aggregated_content_parts.append(
                f"--- PAGE START: {page.url} ---\n{page.content}\n--- PAGE END ---"
            )
            visited_urls.append(page.url)
        
        aggregated_content = "\n\n".join(aggregated_content_parts)
        
        if not aggregated_content or len(aggregated_content.strip()) < 100:
            logger.warning(f"⚠️ Conteúdo agregado insuficiente para cnpj={request.cnpj_basico}")
            return ScrapeResponse(
                success=False,
                chunks_saved=0,
                total_tokens=0,
                pages_scraped=pages_scraped,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        # 3. Processar conteúdo em chunks (síncrono, mas rápido ~20ms)
        chunking_start = time.perf_counter()
        chunks = process_content(aggregated_content)
        chunking_duration = (time.perf_counter() - chunking_start) * 1000
        
        if not chunks:
            logger.warning(f"⚠️ Nenhum chunk gerado para cnpj={request.cnpj_basico}")
            return ScrapeResponse(
                success=False,
                chunks_saved=0,
                total_tokens=0,
                pages_scraped=pages_scraped,
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
        
        # Adicionar informações de páginas aos chunks
        # Cada chunk pode ter múltiplas páginas incluídas
        for chunk in chunks:
            # Se o chunk não tiver pages_included, adicionar todas as URLs
            if not hasattr(chunk, 'pages_included') or not chunk.pages_included:
                chunk.pages_included = visited_urls[:5]  # Limitar a 5 URLs
        
        total_tokens = sum(chunk.tokens for chunk in chunks)
        
        logger.info(
            f"✅ Chunking concluído: {len(chunks)} chunks, {total_tokens:,} tokens "
            f"em {chunking_duration:.1f}ms (cnpj={request.cnpj_basico})"
        )
        
        # 4. Buscar discovery_id do banco (opcional)
        discovery_id = None
        try:
            discovery = await db_service.get_discovery(request.cnpj_basico)
            if discovery:
                discovery_id = discovery.get('id')
                logger.debug(f"✅ Discovery encontrado: id={discovery_id} (cnpj={request.cnpj_basico})")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao buscar discovery: {e} (continuando sem discovery_id)")
        
        # 5. Salvar chunks no banco usando batch insert (assíncrono, transação única)
        save_start = time.perf_counter()
        try:
            chunks_saved = await db_service.save_chunks_batch(
                cnpj_basico=request.cnpj_basico,
                chunks=chunks,
                website_url=request.website_url,
                discovery_id=discovery_id
            )
            save_duration = (time.perf_counter() - save_start) * 1000
            
            logger.info(
                f"✅ Chunks salvos no banco: {chunks_saved} chunks em {save_duration:.1f}ms "
                f"(cnpj={request.cnpj_basico})"
            )
        except Exception as e:
            logger.error(f"❌ Erro ao salvar chunks no banco: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao salvar chunks no banco de dados: {str(e)}"
            )
        
        # 6. Retornar resposta
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"✅ Scrape endpoint concluído: cnpj={request.cnpj_basico}, "
            f"{chunks_saved} chunks, {total_tokens:,} tokens, {pages_scraped} páginas, "
            f"{processing_time_ms:.1f}ms total"
        )
        
        return ScrapeResponse(
            success=True,
            chunks_saved=chunks_saved,
            total_tokens=total_tokens,
            pages_scraped=pages_scraped,
            processing_time_ms=processing_time_ms
        )
    
    except HTTPException:
        # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(f"❌ Erro no endpoint scrape: {e}", exc_info=True)
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar scraping: {str(e)}"
        )

