"""
Failure Tracker - Rastreador de falhas do sistema.
Registra e persiste todas as falhas para análise posterior.
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
from urllib.parse import urlparse
from collections import defaultdict

logger = logging.getLogger(__name__)


class FailureModule(Enum):
    """Módulos do sistema que podem falhar."""
    SCRAPER = "scraper"
    LLM = "llm"
    DISCOVERY = "discovery"


class FailureType(Enum):
    """Tipos de falha categorizados."""
    # Scraper
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    CLOUDFLARE = "cloudflare"
    WAF = "waf"
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"
    EMPTY_CONTENT = "empty_content"
    SOFT_404 = "soft_404"
    SSL_ERROR = "ssl_error"
    DNS_ERROR = "dns_error"
    
    # LLM
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_BAD_REQUEST = "llm_bad_request"
    LLM_PARSE_ERROR = "llm_parse_error"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    
    # Discovery
    NO_RESULTS = "no_results"
    INVALID_URL = "invalid_url"
    
    # Genérico
    UNKNOWN = "unknown"


@dataclass
class FailureRecord:
    """Registro de uma falha no sistema."""
    timestamp: str
    module: str
    error_type: str
    url: str
    domain: str
    context: Dict[str, Any] = field(default_factory=dict)
    strategy_used: str = ""
    retry_count: int = 0
    error_message: str = ""
    duration_ms: float = 0.0
    
    @classmethod
    def create(
        cls,
        module: FailureModule,
        error_type: FailureType,
        url: str,
        error_message: str = "",
        context: Dict[str, Any] = None,
        strategy_used: str = "",
        retry_count: int = 0,
        duration_ms: float = 0.0
    ) -> 'FailureRecord':
        """Factory method para criar um registro de falha."""
        parsed = urlparse(url)
        domain = parsed.netloc or url
        
        return cls(
            timestamp=datetime.utcnow().isoformat(),
            module=module.value,
            error_type=error_type.value,
            url=url,
            domain=domain,
            context=context or {},
            strategy_used=strategy_used,
            retry_count=retry_count,
            error_message=error_message,
            duration_ms=duration_ms
        )


class FailureTracker:
    """
    Rastreador de falhas com persistência em JSON.
    
    Funcionalidades:
    - Registrar falhas de qualquer módulo
    - Buscar falhas por domínio
    - Agrupar falhas por padrão
    - Persistir em disco para análise histórica
    """
    
    MAX_RECORDS = 10000  # Limite máximo de registros em memória
    
    def __init__(self, storage_path: str = "data/failures.json"):
        self.storage_path = storage_path
        self.records: List[FailureRecord] = []
        self._ensure_storage_dir()
        self._load()
    
    def _ensure_storage_dir(self):
        """Garante que o diretório de storage existe."""
        dir_path = os.path.dirname(self.storage_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    def _load(self):
        """Carrega registros do arquivo JSON."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [FailureRecord(**r) for r in data]
                    logger.info(f"FailureTracker: Carregados {len(self.records)} registros")
            except Exception as e:
                logger.error(f"FailureTracker: Erro ao carregar: {e}")
                self.records = []
    
    def _save(self):
        """Persiste registros no arquivo JSON."""
        try:
            data = [asdict(r) for r in self.records[-self.MAX_RECORDS:]]
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"FailureTracker: Erro ao salvar: {e}")
    
    def record(self, failure: FailureRecord):
        """
        Registra uma nova falha.
        
        Args:
            failure: Registro de falha a ser salvo
        """
        self.records.append(failure)
        
        # Truncar se exceder limite
        if len(self.records) > self.MAX_RECORDS:
            self.records = self.records[-self.MAX_RECORDS:]
        
        self._save()
        logger.debug(f"FailureTracker: Registrada falha {failure.error_type} em {failure.domain}")
    
    def record_failure(
        self,
        module: FailureModule,
        error_type: FailureType,
        url: str,
        error_message: str = "",
        context: Dict[str, Any] = None,
        strategy_used: str = "",
        retry_count: int = 0,
        duration_ms: float = 0.0
    ):
        """
        Método de conveniência para registrar falha.
        
        Args:
            module: Módulo que falhou
            error_type: Tipo de falha
            url: URL envolvida
            error_message: Mensagem de erro
            context: Contexto adicional
            strategy_used: Estratégia usada
            retry_count: Número de retentativas
            duration_ms: Duração da operação em ms
        """
        failure = FailureRecord.create(
            module=module,
            error_type=error_type,
            url=url,
            error_message=error_message,
            context=context,
            strategy_used=strategy_used,
            retry_count=retry_count,
            duration_ms=duration_ms
        )
        self.record(failure)
    
    def get_by_domain(self, domain: str) -> List[FailureRecord]:
        """
        Busca falhas por domínio.
        
        Args:
            domain: Domínio a buscar
        
        Returns:
            Lista de falhas do domínio
        """
        return [r for r in self.records if r.domain == domain]
    
    def get_by_module(self, module: FailureModule) -> List[FailureRecord]:
        """
        Busca falhas por módulo.
        
        Args:
            module: Módulo a buscar
        
        Returns:
            Lista de falhas do módulo
        """
        return [r for r in self.records if r.module == module.value]
    
    def get_by_type(self, error_type: FailureType) -> List[FailureRecord]:
        """
        Busca falhas por tipo de erro.
        
        Args:
            error_type: Tipo de erro a buscar
        
        Returns:
            Lista de falhas do tipo
        """
        return [r for r in self.records if r.error_type == error_type.value]
    
    def get_patterns(self, period_hours: int = 24) -> Dict[str, Dict[str, int]]:
        """
        Agrupa falhas por padrão (módulo + tipo).
        
        Args:
            period_hours: Período em horas para análise
        
        Returns:
            Dict com contagem por módulo e tipo
        """
        cutoff = datetime.utcnow().timestamp() - (period_hours * 3600)
        
        patterns = defaultdict(lambda: defaultdict(int))
        
        for record in self.records:
            try:
                record_time = datetime.fromisoformat(record.timestamp).timestamp()
                if record_time >= cutoff:
                    patterns[record.module][record.error_type] += 1
            except:
                continue
        
        return {k: dict(v) for k, v in patterns.items()}
    
    def get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """
        Estatísticas de falhas para um domínio.
        
        Args:
            domain: Domínio a analisar
        
        Returns:
            Dict com estatísticas
        """
        domain_failures = self.get_by_domain(domain)
        
        if not domain_failures:
            return {"domain": domain, "total_failures": 0}
        
        error_types = defaultdict(int)
        strategies = defaultdict(int)
        
        for f in domain_failures:
            error_types[f.error_type] += 1
            if f.strategy_used:
                strategies[f.strategy_used] += 1
        
        return {
            "domain": domain,
            "total_failures": len(domain_failures),
            "error_types": dict(error_types),
            "strategies_tried": dict(strategies),
            "last_failure": domain_failures[-1].timestamp,
            "avg_retry_count": sum(f.retry_count for f in domain_failures) / len(domain_failures)
        }
    
    def get_recent_failures(self, limit: int = 100) -> List[FailureRecord]:
        """Retorna as N falhas mais recentes."""
        return self.records[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo geral das falhas."""
        patterns = self.get_patterns(24)
        
        total_by_module = {m: sum(v.values()) for m, v in patterns.items()}
        
        return {
            "total_records": len(self.records),
            "last_24h": patterns,
            "total_by_module_24h": total_by_module,
            "unique_domains": len(set(r.domain for r in self.records))
        }
    
    def clear_old_records(self, days: int = 30):
        """Remove registros mais antigos que N dias."""
        cutoff = datetime.utcnow().timestamp() - (days * 24 * 3600)
        
        original_count = len(self.records)
        self.records = [
            r for r in self.records
            if datetime.fromisoformat(r.timestamp).timestamp() >= cutoff
        ]
        
        removed = original_count - len(self.records)
        if removed > 0:
            self._save()
            logger.info(f"FailureTracker: Removidos {removed} registros antigos")


# Instância singleton
failure_tracker = FailureTracker()

