"""
Configuração Phoenix para observabilidade de chamadas LLM.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton do tracer provider por projeto
_tracer_providers: dict = {}

# Flag para desabilitar tracing (útil para testes)
_tracing_enabled: bool = True


def set_tracing_enabled(enabled: bool):
    """Define se o tracing está habilitado."""
    global _tracing_enabled
    _tracing_enabled = enabled


def setup_phoenix_tracing(project_name: str):
    """
    Configura tracing Phoenix para um projeto específico.
    
    Args:
        project_name: Nome do projeto no Phoenix (ex: 'discovery-llm', 'profile-llm')
    
    Returns:
        TracerProvider configurado ou None se tracing desabilitado
    """
    if not _tracing_enabled:
        logger.debug(f"🔇 Tracing desabilitado para projeto: {project_name}")
        return None
    
    if project_name not in _tracer_providers:
        try:
            from phoenix.otel import register
            from openinference.instrumentation.openai import OpenAIInstrumentor
            
            tracer_provider = register(
                project_name=project_name,
                endpoint=f"{settings.PHOENIX_COLLECTOR_URL}/v1/traces",
            )
            OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            _tracer_providers[project_name] = tracer_provider
            logger.info(f"✅ Phoenix tracing configurado para projeto: {project_name}")
        except ImportError as e:
            logger.warning(f"⚠️ Bibliotecas Phoenix não instaladas: {e}")
            logger.warning("⚠️ Tracing desabilitado. Instale: pip install arize-phoenix-otel openinference-instrumentation-openai")
            _tracer_providers[project_name] = None
        except Exception as e:
            logger.error(f"❌ Erro ao configurar Phoenix tracing: {e}")
            _tracer_providers[project_name] = None
    
    return _tracer_providers.get(project_name)


@asynccontextmanager
async def trace_llm_call(project_name: str, operation_name: str):
    """
    Context manager assíncrono para tracing de chamadas LLM.
    
    Uso:
        async with trace_llm_call("discovery-llm", "find_website") as span:
            result = await llm_call(...)
            if span:
                span.set_attribute("result", result)
    
    Args:
        project_name: Nome do projeto no Phoenix (ex: 'discovery-llm', 'profile-llm')
        operation_name: Nome da operação sendo rastreada
    
    Yields:
        Span do OpenTelemetry ou None se tracing desabilitado
    """
    if not _tracing_enabled:
        yield None
        return
    
    tracer_provider = setup_phoenix_tracing(project_name)
    
    if tracer_provider is None:
        yield None
        return
    
    try:
        from opentelemetry import trace as otel_trace
        
        tracer_instance = otel_trace.get_tracer(__name__)
        span = tracer_instance.start_span(operation_name)
        
        try:
            token = otel_trace.context_api.attach(otel_trace.context_api.set_span_in_context(span))
            try:
                yield span
            finally:
                otel_trace.context_api.detach(token)
        except Exception as e:
            if span:
                span.set_attribute("error", str(e))
                span.set_attribute("error.type", type(e).__name__)
            span.end()
            raise
        else:
            span.end()
    except Exception as e:
        logger.warning(f"⚠️ Erro ao criar span Phoenix: {e}")
        yield None

