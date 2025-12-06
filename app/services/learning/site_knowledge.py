"""
Site Knowledge Base - Base de conhecimento sobre sites específicos.
Armazena perfis de sites com suas características e melhores estratégias.
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Optional, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class SiteKnowledge:
    """Perfil de conhecimento sobre um site."""
    domain: str
    protection_type: str = "none"  # none, cloudflare, waf, captcha, rate_limit
    best_strategy: str = "standard"  # fast, standard, robust, aggressive
    avg_response_time_ms: float = 0.0
    success_rate: float = 0.0  # 0.0 a 1.0
    total_attempts: int = 0
    total_successes: int = 0
    last_success: str = ""
    last_failure: str = ""
    special_config: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    
    def update_success(self, response_time_ms: float):
        """Registra um sucesso."""
        self.total_attempts += 1
        self.total_successes += 1
        self.last_success = datetime.utcnow().isoformat()
        
        # Atualizar média móvel
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = response_time_ms
        else:
            self.avg_response_time_ms = (self.avg_response_time_ms * 0.8) + (response_time_ms * 0.2)
        
        self._recalculate_success_rate()
    
    def update_failure(self, error_type: str):
        """Registra uma falha."""
        self.total_attempts += 1
        self.last_failure = datetime.utcnow().isoformat()
        self._recalculate_success_rate()
    
    def _recalculate_success_rate(self):
        """Recalcula taxa de sucesso."""
        if self.total_attempts > 0:
            self.success_rate = self.total_successes / self.total_attempts


class SiteKnowledgeBase:
    """
    Base de conhecimento sobre sites.
    
    Armazena e gerencia perfis de sites para otimizar scraping futuro.
    """
    
    MAX_PROFILES = 5000  # Limite máximo de perfis
    
    def __init__(self, storage_path: str = "data/site_knowledge.json"):
        self.storage_path = storage_path
        self.profiles: Dict[str, SiteKnowledge] = {}
        self._ensure_storage_dir()
        self._load()
    
    def _ensure_storage_dir(self):
        """Garante que o diretório de storage existe."""
        dir_path = os.path.dirname(self.storage_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
    
    def _load(self):
        """Carrega perfis do arquivo JSON."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = {
                        k: SiteKnowledge(**v) for k, v in data.items()
                    }
                    logger.info(f"SiteKnowledge: Carregados {len(self.profiles)} perfis")
            except Exception as e:
                logger.error(f"SiteKnowledge: Erro ao carregar: {e}")
                self.profiles = {}
    
    def _save(self):
        """Persiste perfis no arquivo JSON."""
        try:
            # Limitar número de perfis (manter os mais recentes)
            if len(self.profiles) > self.MAX_PROFILES:
                sorted_profiles = sorted(
                    self.profiles.items(),
                    key=lambda x: x[1].last_success or x[1].last_failure or "",
                    reverse=True
                )
                self.profiles = dict(sorted_profiles[:self.MAX_PROFILES])
            
            data = {k: asdict(v) for k, v in self.profiles.items()}
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"SiteKnowledge: Erro ao salvar: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """Extrai domínio de uma URL."""
        parsed = urlparse(url)
        return parsed.netloc or url
    
    def get_profile(self, domain_or_url: str) -> Optional[SiteKnowledge]:
        """
        Busca perfil de um site.
        
        Args:
            domain_or_url: Domínio ou URL do site
        
        Returns:
            SiteKnowledge ou None
        """
        domain = self._extract_domain(domain_or_url)
        return self.profiles.get(domain)
    
    def get_or_create_profile(self, domain_or_url: str) -> SiteKnowledge:
        """
        Busca ou cria perfil de um site.
        
        Args:
            domain_or_url: Domínio ou URL do site
        
        Returns:
            SiteKnowledge existente ou novo
        """
        domain = self._extract_domain(domain_or_url)
        
        if domain not in self.profiles:
            self.profiles[domain] = SiteKnowledge(domain=domain)
        
        return self.profiles[domain]
    
    def add_profile(self, profile: SiteKnowledge):
        """
        Adiciona ou atualiza perfil de um site.
        
        Args:
            profile: Perfil a adicionar
        """
        self.profiles[profile.domain] = profile
        self._save()
        logger.debug(f"SiteKnowledge: Perfil adicionado/atualizado para {profile.domain}")
    
    def update_profile(
        self,
        domain_or_url: str,
        protection_type: Optional[str] = None,
        best_strategy: Optional[str] = None,
        special_config: Optional[Dict[str, Any]] = None
    ):
        """
        Atualiza perfil existente ou cria novo.
        
        Args:
            domain_or_url: Domínio ou URL do site
            protection_type: Tipo de proteção detectada
            best_strategy: Melhor estratégia de scraping
            special_config: Configurações especiais
        """
        profile = self.get_or_create_profile(domain_or_url)
        
        if protection_type is not None:
            profile.protection_type = protection_type
        if best_strategy is not None:
            profile.best_strategy = best_strategy
        if special_config is not None:
            profile.special_config.update(special_config)
        
        self._save()
    
    def record_success(
        self,
        domain_or_url: str,
        response_time_ms: float,
        strategy_used: str = ""
    ):
        """
        Registra sucesso de scraping.
        
        Args:
            domain_or_url: Domínio ou URL
            response_time_ms: Tempo de resposta em ms
            strategy_used: Estratégia utilizada
        """
        profile = self.get_or_create_profile(domain_or_url)
        profile.update_success(response_time_ms)
        
        # Atualizar melhor estratégia se taxa de sucesso for alta
        if strategy_used and profile.success_rate > 0.8:
            profile.best_strategy = strategy_used
        
        self._save()
    
    def record_failure(
        self,
        domain_or_url: str,
        error_type: str,
        protection_detected: Optional[str] = None
    ):
        """
        Registra falha de scraping.
        
        Args:
            domain_or_url: Domínio ou URL
            error_type: Tipo de erro
            protection_detected: Proteção detectada (se houver)
        """
        profile = self.get_or_create_profile(domain_or_url)
        profile.update_failure(error_type)
        
        # Atualizar proteção se detectada
        if protection_detected and protection_detected != "none":
            profile.protection_type = protection_detected
        
        self._save()
    
    def get_best_strategy(self, domain_or_url: str) -> str:
        """
        Retorna melhor estratégia para um site.
        
        Args:
            domain_or_url: Domínio ou URL do site
        
        Returns:
            Nome da estratégia (default: "standard")
        """
        profile = self.get_profile(domain_or_url)
        
        if profile:
            # Se taxa de sucesso for muito baixa, sugerir estratégia mais agressiva
            if profile.total_attempts > 3 and profile.success_rate < 0.3:
                if profile.protection_type in ["cloudflare", "waf", "captcha"]:
                    return "aggressive"
                else:
                    return "robust"
            
            return profile.best_strategy
        
        return "standard"
    
    def get_protection_type(self, domain_or_url: str) -> str:
        """
        Retorna tipo de proteção conhecida para um site.
        
        Args:
            domain_or_url: Domínio ou URL do site
        
        Returns:
            Tipo de proteção (default: "none")
        """
        profile = self.get_profile(domain_or_url)
        return profile.protection_type if profile else "none"
    
    def get_problematic_domains(self, min_failures: int = 3) -> List[SiteKnowledge]:
        """
        Retorna domínios com taxa de sucesso baixa.
        
        Args:
            min_failures: Mínimo de tentativas para considerar
        
        Returns:
            Lista de perfis problemáticos
        """
        return [
            p for p in self.profiles.values()
            if p.total_attempts >= min_failures and p.success_rate < 0.5
        ]
    
    def get_protected_domains(self) -> Dict[str, List[str]]:
        """
        Retorna domínios agrupados por tipo de proteção.
        
        Returns:
            Dict com tipo de proteção como chave
        """
        result: Dict[str, List[str]] = {}
        
        for domain, profile in self.profiles.items():
            if profile.protection_type != "none":
                if profile.protection_type not in result:
                    result[profile.protection_type] = []
                result[profile.protection_type].append(domain)
        
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo da base de conhecimento."""
        if not self.profiles:
            return {"total_profiles": 0}
        
        total = len(self.profiles)
        protected = sum(1 for p in self.profiles.values() if p.protection_type != "none")
        problematic = len(self.get_problematic_domains())
        
        avg_success_rate = sum(
            p.success_rate for p in self.profiles.values() if p.total_attempts > 0
        )
        profiles_with_attempts = sum(1 for p in self.profiles.values() if p.total_attempts > 0)
        
        return {
            "total_profiles": total,
            "protected_sites": protected,
            "problematic_sites": problematic,
            "avg_success_rate": (avg_success_rate / profiles_with_attempts) if profiles_with_attempts > 0 else 0,
            "protection_distribution": self.get_protected_domains()
        }
    
    def clear_old_profiles(self, days: int = 90):
        """Remove perfis não acessados há muito tempo."""
        cutoff = datetime.utcnow().timestamp() - (days * 24 * 3600)
        
        to_remove = []
        for domain, profile in self.profiles.items():
            last_activity = profile.last_success or profile.last_failure
            if last_activity:
                try:
                    activity_time = datetime.fromisoformat(last_activity).timestamp()
                    if activity_time < cutoff:
                        to_remove.append(domain)
                except:
                    pass
            else:
                to_remove.append(domain)
        
        for domain in to_remove:
            del self.profiles[domain]
        
        if to_remove:
            self._save()
            logger.info(f"SiteKnowledge: Removidos {len(to_remove)} perfis antigos")


# Instância singleton
site_knowledge = SiteKnowledgeBase()

