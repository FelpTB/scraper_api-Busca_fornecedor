"""
Execução de um job de descoberta de site (1 CNPJ).
Usado pelo discovery_worker após claim na queue_discovery.
"""
import logging
from app.services.database_service import get_db_service
from app.services.agents.discovery_agent import get_discovery_agent
from app.core.phoenix_tracer import trace_llm_call
from app.services.discovery.discovery_service import _filter_search_results

logger = logging.getLogger(__name__)


async def run_discovery_job(cnpj_basico: str) -> None:
    """
    Processa descoberta de site para um CNPJ: lê serper_results, filtra,
    chama LLM e grava website_discovery.
    """
    db_service = get_db_service()
    try:
        logger.info(f"🔍 [DISCOVERY JOB] cnpj={cnpj_basico}")

        serper_data = await db_service.get_serper_results(cnpj_basico)
        if not serper_data:
            logger.warning(f"⚠️ [DISCOVERY JOB] Nenhum resultado Serper para cnpj={cnpj_basico}")
            await db_service.save_discovery(
                cnpj_basico=cnpj_basico,
                website_url=None,
                discovery_status="not_found",
                serper_id=None,
                confidence_score=None,
                llm_reasoning="Nenhum resultado Serper encontrado",
            )
            return

        razao_social = serper_data.get("razao_social") or ""
        nome_fantasia = serper_data.get("nome_fantasia") or serper_data.get("company_name") or ""
        municipio = serper_data.get("municipio") or ""
        serper_id = serper_data.get("id")
        search_results = serper_data.get("results_json", [])

        if not search_results:
            logger.warning(f"⚠️ [DISCOVERY JOB] Nenhum resultado de busca para cnpj={cnpj_basico}")
            await db_service.save_discovery(
                cnpj_basico=cnpj_basico,
                website_url=None,
                discovery_status="not_found",
                serper_id=serper_id,
                confidence_score=None,
                llm_reasoning="Nenhum resultado de busca disponível",
            )
            return

        filtered_results = _filter_search_results(search_results, ctx_label="")
        if not filtered_results:
            logger.warning(f"⚠️ [DISCOVERY JOB] Todos filtrados (blacklist) cnpj={cnpj_basico}")
            await db_service.save_discovery(
                cnpj_basico=cnpj_basico,
                website_url=None,
                discovery_status="not_found",
                serper_id=serper_id,
                confidence_score=None,
                llm_reasoning="Todos os resultados foram filtrados (blacklist)",
            )
            return

        discovery_agent = get_discovery_agent()
        website_url = None
        llm_reasoning = None

        try:
            async with trace_llm_call("discovery-llm", "find_website") as span:
                if span:
                    span.set_attribute("cnpj_basico", cnpj_basico)
                    span.set_attribute("nome_fantasia", nome_fantasia)
                    span.set_attribute("razao_social", razao_social)
                    span.set_attribute("results_count", len(filtered_results))

                website_url = await discovery_agent.find_website(
                    nome_fantasia=nome_fantasia,
                    razao_social=razao_social,
                    cnpj=cnpj_basico,
                    email="",
                    municipio=municipio,
                    cnaes=None,
                    search_results=filtered_results,
                    ctx_label="",
                    request_id="",
                )

                if span:
                    span.set_attribute("website_found", website_url is not None)
                    if website_url:
                        span.set_attribute("website_url", website_url)
        except Exception as e:
            logger.error(f"❌ [DISCOVERY JOB] Erro no DiscoveryAgent: {e}", exc_info=True)
            llm_reasoning = f"Erro no DiscoveryAgent: {str(e)}"

        discovery_status = "found" if website_url else "not_found"
        confidence_score = 0.9 if website_url else None

        discovery_id = await db_service.save_discovery(
            cnpj_basico=cnpj_basico,
            website_url=website_url,
            discovery_status=discovery_status,
            serper_id=serper_id,
            confidence_score=confidence_score,
            llm_reasoning=llm_reasoning,
        )

        logger.info(
            f"✅ [DISCOVERY JOB] cnpj={cnpj_basico}, status={discovery_status}, "
            f"website={website_url}, discovery_id={discovery_id}"
        )
    except Exception as e:
        logger.error(f"❌ [DISCOVERY JOB] Erro ao processar discovery: {e}", exc_info=True)
        try:
            await db_service.save_discovery(
                cnpj_basico=cnpj_basico,
                website_url=None,
                discovery_status="error",
                serper_id=None,
                confidence_score=None,
                llm_reasoning=f"Erro: {str(e)}",
            )
        except Exception:
            pass
        raise
