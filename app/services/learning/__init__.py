"""
Learning Engine v2.0

Sistema de aprendizado que rastreia falhas, analisa padrões
e aplica otimizações de configuração automaticamente.
"""

from .failure_tracker import (
    failure_tracker,
    FailureTracker,
    FailureRecord,
    FailureModule,
    FailureType
)
from .pattern_analyzer import (
    pattern_analyzer,
    PatternAnalyzer,
    ScraperAnalysis,
    LLMAnalysis,
    Recommendation
)
from .config_optimizer import (
    config_optimizer,
    ConfigOptimizer,
    ConfigSuggestion
)
from .site_knowledge import (
    site_knowledge,
    SiteKnowledgeBase,
    SiteKnowledge
)
from .adaptive_config import (
    adaptive_config,
    AdaptiveConfigManager,
    AdaptiveState
)

__all__ = [
    # Failure Tracker
    'failure_tracker',
    'FailureTracker',
    'FailureRecord',
    'FailureModule',
    'FailureType',
    
    # Pattern Analyzer
    'pattern_analyzer',
    'PatternAnalyzer',
    'ScraperAnalysis',
    'LLMAnalysis',
    'Recommendation',
    
    # Config Optimizer
    'config_optimizer',
    'ConfigOptimizer',
    'ConfigSuggestion',
    
    # Site Knowledge
    'site_knowledge',
    'SiteKnowledgeBase',
    'SiteKnowledge',
    
    # Adaptive Config (auto-aplicação)
    'adaptive_config',
    'AdaptiveConfigManager',
    'AdaptiveState',
]

