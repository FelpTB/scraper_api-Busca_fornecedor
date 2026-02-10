"""
Agregador de requisições Serper - Processa conjuntos grandes em chamadas batch.

Quando múltiplas requisições chegam simultaneamente, agrupa até 100 queries
em uma única chamada à API Serpshot, reduzindo requisições HTTP e melhorando
throughput sob carga alta.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable, List, Optional, Any, Tuple

from app.services.concurrency_manager.config_loader import get_section as get_config
from app.services.discovery_manager.serper_manager import serper_manager
from app.services.database_service import get_db_service

logger = logging.getLogger(__name__)

_SERPER_CFG = get_config("discovery/serper", {})
BATCH_MAX_SIZE = _SERPER_CFG.get("batch_aggregator_max_size", 100)
BATCH_MAX_WAIT_MS = _SERPER_CFG.get("batch_aggregator_max_wait_ms", 200)
NUM_RESULTS = 10


@dataclass
class SerperBatchItem:
    """Item enfileirado para processamento em batch."""
    cnpj_basico: str
    query: str
    razao_social: Optional[str]
    nome_fantasia: Optional[str]
    municipio: Optional[str]


class SerperBatchAggregator:
    """
    Agrega requisições de busca Serper e processa em lotes de até 100 queries
    por chamada à API Serpshot.
    """

    def __init__(
        self,
        batch_max_size: int = BATCH_MAX_SIZE,
        batch_max_wait_ms: float = BATCH_MAX_WAIT_MS,
    ):
        self._batch_max_size = min(100, max(1, batch_max_size))
        self._batch_max_wait = batch_max_wait_ms / 1000.0
        self._queue: asyncio.Queue[Optional[SerperBatchItem]] = asyncio.Queue()
        self._consumer_task: Optional[asyncio.Task] = None
        self._db_service = get_db_service()

    async def submit(self, item: SerperBatchItem) -> None:
        """Enfileira um item para processamento em batch."""
        await self._queue.put(item)

    async def _collect_batch(self) -> Tuple[List[SerperBatchItem], bool]:
        """
        Coleta itens até atingir batch_max_size ou timeout.
        Returns:
            (batch, shutdown) - shutdown=True quando recebe sinal de encerramento
        """
        batch: List[SerperBatchItem] = []
        deadline = asyncio.get_event_loop().time() + self._batch_max_wait

        while len(batch) < self._batch_max_size:
            timeout = max(0.001, deadline - asyncio.get_event_loop().time())
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                if item is None:
                    return batch, True
                batch.append(item)
                if len(batch) >= self._batch_max_size:
                    return batch, False
            except asyncio.TimeoutError:
                return batch, False

        return batch, False

    async def _process_batch(self, items: List[SerperBatchItem]) -> None:
        """Processa um lote via search_batch e grava resultados."""
        if not items:
            return

        queries = [item.query for item in items]
        try:
            results_batch, retries, total_failure = await serper_manager.search_batch(
                queries,
                num_results=NUM_RESULTS,
                country="br",
                language="pt-br",
                request_id="",
            )
            logger.info(
                f"📦 [BATCH] Serpshot: {len(queries)} queries processadas, "
                f"{sum(len(r) for r in results_batch)} resultados totais"
            )

            for item, results in zip(items, results_batch):
                if results:
                    self._db_service.enqueue_serper_results(
                        cnpj_basico=item.cnpj_basico,
                        results=results,
                        query_used=item.query,
                        company_name=item.nome_fantasia or item.razao_social,
                        razao_social=item.razao_social,
                        nome_fantasia=item.nome_fantasia,
                        municipio=item.municipio,
                    )
                logger.debug(
                    f"✅ [BATCH] cnpj={item.cnpj_basico} -> {len(results)} resultados"
                )
        except Exception as e:
            logger.error(
                f"❌ [BATCH] Erro ao processar lote de {len(items)} queries: {e}",
                exc_info=True,
            )
            for item in items:
                logger.warning(f"⚠️ [BATCH] CNPJ {item.cnpj_basico} não processado devido a erro")

    async def _consumer_loop(self) -> None:
        """Loop do consumer: coleta e processa lotes."""
        while True:
            batch, shutdown = await self._collect_batch()
            if batch:
                await self._process_batch(batch)
            if shutdown:
                break

    async def start(self) -> None:
        """Inicia o consumer de batch."""
        if self._consumer_task is not None:
            return
        self._consumer_task = asyncio.create_task(
            self._consumer_loop(), name="serper_batch_aggregator"
        )
        await asyncio.sleep(0)  # Garantir que a task começou
        logger.info(
            f"📥 SerperBatchAggregator iniciado: max_size={self._batch_max_size}, "
            f"max_wait_ms={self._batch_max_wait * 1000:.0f}"
        )

    async def stop(self) -> None:
        """Encerra o consumer de batch."""
        await self._queue.put(None)
        if self._consumer_task:
            try:
                await asyncio.wait_for(self._consumer_task, timeout=30.0)
            except asyncio.TimeoutError:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
            self._consumer_task = None
        logger.info("📥 SerperBatchAggregator encerrado")


# Instância global
_aggregator: Optional[SerperBatchAggregator] = None


def get_serper_batch_aggregator() -> SerperBatchAggregator:
    """Retorna a instância global do agregador."""
    global _aggregator
    if _aggregator is None:
        _aggregator = SerperBatchAggregator()
    return _aggregator


async def start_serper_batch_aggregator() -> None:
    """Inicia o agregador de batch."""
    await get_serper_batch_aggregator().start()


async def stop_serper_batch_aggregator() -> None:
    """Encerra o agregador de batch."""
    global _aggregator
    if _aggregator:
        await _aggregator.stop()
