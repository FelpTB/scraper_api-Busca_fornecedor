"""
Analisador Detalhado de Testes - Fase 6

Analisa cada etapa e sub-etapa do sistema para identificar
exatamente onde e por quê as falhas estão ocorrendo.

Etapas analisadas:
1. DISCOVERY
   - Serper API (busca Google)
   - LLM (decisão de URL)
   - URL Prober (validação)
   
2. SCRAPER
   - Por estratégia (fast, standard, robust, aggressive)
   - Por tipo de proteção
   - Por tempo de resposta
   
3. LLM ANALYSIS
   - Por provider (OpenAI, Gemini, OpenRouter)
   - Por tamanho de chunk
   - Por tempo de resposta
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class EtapaMetrics:
    """Métricas de uma etapa."""
    total: int = 0
    sucesso: int = 0
    falha: int = 0
    tempo_total_ms: float = 0
    erros_por_tipo: Dict[str, int] = field(default_factory=dict)
    
    @property
    def taxa_sucesso(self) -> float:
        return (self.sucesso / self.total * 100) if self.total > 0 else 0
    
    @property
    def tempo_medio_ms(self) -> float:
        return (self.tempo_total_ms / self.total) if self.total > 0 else 0


@dataclass
class DiscoveryMetrics:
    """Métricas detalhadas do Discovery."""
    # Geral
    total: int = 0
    modo_producao: bool = False  # Se ignorou site cadastrado
    com_site_cadastrado: int = 0
    sem_site_cadastrado: int = 0
    
    # Serper API (busca Google)
    serper_necessario: int = 0  # Quantas empresas precisaram de busca
    serper_sucesso: int = 0
    serper_falha: int = 0
    serper_rate_limit: int = 0
    serper_timeout: int = 0
    
    # LLM Decision (escolha do site correto)
    llm_decision_chamadas: int = 0
    llm_decision_sucesso: int = 0
    llm_decision_falha: int = 0
    llm_decision_timeout: int = 0
    
    # URL Prober (validação de URL)
    prober_sucesso: int = 0
    prober_falha: int = 0
    prober_timeout: int = 0
    prober_tempo_total_ms: float = 0


@dataclass
class ScraperMetrics:
    """Métricas detalhadas do Scraper."""
    total: int = 0
    sucesso: int = 0
    falha: int = 0
    
    # Por estratégia
    por_estrategia: Dict[str, EtapaMetrics] = field(default_factory=dict)
    
    # Por tipo de erro
    erro_timeout: int = 0
    erro_cloudflare: int = 0
    erro_waf: int = 0
    erro_captcha: int = 0
    erro_empty_content: int = 0
    erro_connection: int = 0
    erro_ssl: int = 0
    erro_outros: int = 0
    
    # Por tamanho de site
    sites_pequenos: int = 0  # < 5 páginas
    sites_medios: int = 0    # 5-20 páginas
    sites_grandes: int = 0   # > 20 páginas


@dataclass
class LLMMetrics:
    """Métricas detalhadas do LLM."""
    total: int = 0
    sucesso: int = 0
    falha: int = 0
    
    # Por provider
    por_provider: Dict[str, EtapaMetrics] = field(default_factory=dict)
    
    # Por tipo de erro
    erro_timeout: int = 0
    erro_rate_limit: int = 0
    erro_parse: int = 0
    erro_token_limit: int = 0
    erro_outros: int = 0
    
    # Por tamanho de input
    chunks_pequenos: int = 0   # < 10k tokens
    chunks_medios: int = 0     # 10k-50k tokens
    chunks_grandes: int = 0    # > 50k tokens


class DetailedAnalyzer:
    """Analisa logs de teste em detalhes."""
    
    def __init__(self):
        self.discovery = DiscoveryMetrics()
        self.scraper = ScraperMetrics()
        self.llm = LLMMetrics()
        self.raw_results: List[Dict] = []
    
    def load_test_log(self, filepath: str):
        """Carrega log de teste."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.raw_results = data.get('results', [])
        self.config = data.get('config', {})
        self.metrics_summary = data.get('metrics', {})
        
        print(f"📂 Carregado: {filepath}")
        print(f"   Empresas: {len(self.raw_results)}")
        print(f"   Config: {self.config}")
    
    def load_latest_log(self):
        """Carrega o log mais recente."""
        logs = sorted(glob.glob('tests/reports/test_log_*.json'))
        if not logs:
            # Tentar carregar parallel_test_report
            logs = sorted(glob.glob('tests/reports/parallel_test_report.json'))
        
        if logs:
            self.load_test_log(logs[-1])
        else:
            print("❌ Nenhum log encontrado")
    
    def analyze_discovery(self):
        """Analisa etapa de Discovery em detalhes."""
        print("\n" + "="*70)
        print("📍 ANÁLISE DE DISCOVERY")
        print("="*70)
        
        self.discovery.total = len(self.raw_results)
        
        # Detectar modo produção (sem site cadastrado = modo produção)
        for r in self.raw_results:
            empresa = r.get('empresa', {})
            site_original = empresa.get('site_original', '')
            
            if site_original:
                self.discovery.com_site_cadastrado += 1
            else:
                self.discovery.sem_site_cadastrado += 1
        
        # Se maioria não tem site, é modo produção
        self.discovery.modo_producao = self.discovery.sem_site_cadastrado > self.discovery.com_site_cadastrado
        self.discovery.serper_necessario = self.discovery.sem_site_cadastrado
        
        # Analisar resultados
        for r in self.raw_results:
            discovery_url = r.get('discovery_url', '')
            error = r.get('error', '')
            
            if discovery_url:
                self.discovery.prober_sucesso += 1
                # Se não tinha site e encontrou, Serper funcionou
                if not r.get('empresa', {}).get('site_original'):
                    self.discovery.serper_sucesso += 1
                    self.discovery.llm_decision_sucesso += 1
            else:
                self.discovery.prober_falha += 1
                
                # Classificar tipo de falha
                error_lower = error.lower()
                if 'timeout' in error_lower:
                    self.discovery.prober_timeout += 1
                    # Se era modo produção, pode ser timeout no Serper ou LLM
                    if not r.get('empresa', {}).get('site_original'):
                        self.discovery.serper_timeout += 1
                elif 'não encontrado' in error_lower or 'not found' in error_lower:
                    self.discovery.serper_falha += 1
                elif 'rate' in error_lower or '429' in error_lower:
                    self.discovery.serper_rate_limit += 1
        
        # Imprimir resultados
        modo_str = "PRODUÇÃO (Discovery completo)" if self.discovery.modo_producao else "TESTE (usa site cadastrado)"
        print(f"\n⚙️ MODO: {modo_str}")
        
        print(f"\n📊 DISTRIBUIÇÃO DE EMPRESAS:")
        print(f"   Total: {self.discovery.total}")
        print(f"   Com site cadastrado: {self.discovery.com_site_cadastrado} ({self.discovery.com_site_cadastrado/self.discovery.total*100:.1f}%)")
        print(f"   Sem site cadastrado: {self.discovery.sem_site_cadastrado} ({self.discovery.sem_site_cadastrado/self.discovery.total*100:.1f}%)")
        
        if self.discovery.modo_producao:
            print(f"\n🔍 SERPER API (busca Google):")
            print(f"   Empresas que precisaram buscar: {self.discovery.serper_necessario}")
            print(f"   Sucesso: {self.discovery.serper_sucesso} ({self.discovery.serper_sucesso/max(self.discovery.serper_necessario,1)*100:.1f}%)")
            print(f"   Falha (não encontrou): {self.discovery.serper_falha}")
            print(f"   Timeout: {self.discovery.serper_timeout}")
            print(f"   Rate Limit: {self.discovery.serper_rate_limit}")
            
            print(f"\n🤖 LLM DECISION (escolha do site):")
            print(f"   Decisões corretas: {self.discovery.llm_decision_sucesso}")
        
        print(f"\n🔗 URL PROBER (validação de URL):")
        print(f"   Sucesso: {self.discovery.prober_sucesso} ({self.discovery.prober_sucesso/self.discovery.total*100:.1f}%)")
        print(f"   Falha: {self.discovery.prober_falha} ({self.discovery.prober_falha/self.discovery.total*100:.1f}%)")
        print(f"   └─ Por Timeout: {self.discovery.prober_timeout}")
        
        # Identificar gargalo
        print(f"\n🚨 GARGALO PRINCIPAL NO DISCOVERY:")
        if self.discovery.prober_timeout > self.discovery.total * 0.3:
            print(f"   ❌ TIMEOUT ({self.discovery.prober_timeout} casos)")
            if self.discovery.modo_producao:
                print(f"   💡 SUGESTÃO: Verificar Serper API e LLM para rate limits")
            else:
                print(f"   💡 SUGESTÃO: Aumentar timeout do URLProber")
        elif self.discovery.serper_rate_limit > 5:
            print(f"   ❌ RATE LIMIT NO SERPER ({self.discovery.serper_rate_limit} casos)")
            print(f"   💡 SUGESTÃO: Implementar backoff ou aumentar quota do Serper")
        elif self.discovery.serper_falha > self.discovery.serper_necessario * 0.3:
            print(f"   ❌ SERPER NÃO ENCONTROU SITES ({self.discovery.serper_falha} casos)")
            print(f"   💡 SUGESTÃO: Melhorar queries de busca ou usar dados alternativos")
        else:
            print(f"   ✅ Discovery funcionando adequadamente")
    
    def analyze_scraper(self):
        """Analisa etapa de Scraper em detalhes."""
        print("\n" + "="*70)
        print("🕷️ ANÁLISE DE SCRAPER")
        print("="*70)
        
        # Filtrar apenas empresas que passaram pelo discovery
        empresas_com_url = [r for r in self.raw_results if r.get('discovery_url')]
        
        self.scraper.total = len(empresas_com_url)
        
        for r in empresas_com_url:
            scrape_chars = r.get('scrape_chars', 0)
            scrape_pages = r.get('scrape_pages', 0)
            error = r.get('error', '')
            
            if scrape_chars > 100:
                self.scraper.sucesso += 1
                
                # Classificar por tamanho
                if scrape_pages < 5:
                    self.scraper.sites_pequenos += 1
                elif scrape_pages <= 20:
                    self.scraper.sites_medios += 1
                else:
                    self.scraper.sites_grandes += 1
            else:
                self.scraper.falha += 1
                
                # Classificar erro
                error_lower = error.lower()
                if 'timeout' in error_lower:
                    self.scraper.erro_timeout += 1
                elif 'cloudflare' in error_lower:
                    self.scraper.erro_cloudflare += 1
                elif 'waf' in error_lower:
                    self.scraper.erro_waf += 1
                elif 'captcha' in error_lower:
                    self.scraper.erro_captcha += 1
                elif 'empty' in error_lower or 'insuficiente' in error_lower:
                    self.scraper.erro_empty_content += 1
                elif 'connection' in error_lower or 'connect' in error_lower:
                    self.scraper.erro_connection += 1
                elif 'ssl' in error_lower:
                    self.scraper.erro_ssl += 1
                else:
                    self.scraper.erro_outros += 1
        
        # Imprimir resultados
        if self.scraper.total == 0:
            print("\n⚠️ Nenhuma empresa chegou na etapa de scraping")
            return
        
        print(f"\n📊 RESULTADO GERAL:")
        print(f"   Total que chegou no scrape: {self.scraper.total}")
        print(f"   Sucesso: {self.scraper.sucesso} ({self.scraper.sucesso/self.scraper.total*100:.1f}%)")
        print(f"   Falha: {self.scraper.falha} ({self.scraper.falha/self.scraper.total*100:.1f}%)")
        
        print(f"\n📏 POR TAMANHO DE SITE (sucessos):")
        if self.scraper.sucesso > 0:
            print(f"   Pequenos (<5 páginas): {self.scraper.sites_pequenos} ({self.scraper.sites_pequenos/self.scraper.sucesso*100:.1f}%)")
            print(f"   Médios (5-20 páginas): {self.scraper.sites_medios} ({self.scraper.sites_medios/self.scraper.sucesso*100:.1f}%)")
            print(f"   Grandes (>20 páginas): {self.scraper.sites_grandes} ({self.scraper.sites_grandes/self.scraper.sucesso*100:.1f}%)")
        
        print(f"\n❌ DISTRIBUIÇÃO DE ERROS:")
        erros = [
            ("Timeout", self.scraper.erro_timeout),
            ("Conteúdo vazio/insuficiente", self.scraper.erro_empty_content),
            ("Cloudflare", self.scraper.erro_cloudflare),
            ("WAF", self.scraper.erro_waf),
            ("Captcha", self.scraper.erro_captcha),
            ("Erro de conexão", self.scraper.erro_connection),
            ("SSL", self.scraper.erro_ssl),
            ("Outros", self.scraper.erro_outros),
        ]
        
        for nome, qtd in sorted(erros, key=lambda x: -x[1]):
            if qtd > 0:
                pct = qtd / self.scraper.falha * 100 if self.scraper.falha > 0 else 0
                print(f"   {qtd:3d}x ({pct:5.1f}%) - {nome}")
        
        # Identificar gargalo
        print(f"\n🚨 GARGALO PRINCIPAL NO SCRAPER:")
        if self.scraper.erro_timeout > self.scraper.falha * 0.4:
            print(f"   ❌ TIMEOUT ({self.scraper.erro_timeout} casos)")
            print(f"   💡 SUGESTÃO: Aumentar session_timeout ou reduzir max_subpages")
        elif self.scraper.erro_empty_content > self.scraper.falha * 0.3:
            print(f"   ❌ CONTEÚDO VAZIO ({self.scraper.erro_empty_content} casos)")
            print(f"   💡 SUGESTÃO: Sites podem estar bloqueando; tentar estratégia 'aggressive'")
        elif self.scraper.erro_cloudflare + self.scraper.erro_waf > self.scraper.falha * 0.3:
            print(f"   ❌ PROTEÇÃO (Cloudflare/WAF: {self.scraper.erro_cloudflare + self.scraper.erro_waf} casos)")
            print(f"   💡 SUGESTÃO: Usar estratégia 'aggressive' por padrão")
        else:
            print(f"   ✅ Scraper funcionando adequadamente")
    
    def analyze_llm(self):
        """Analisa etapa de LLM em detalhes."""
        print("\n" + "="*70)
        print("🤖 ANÁLISE DE LLM")
        print("="*70)
        
        # Filtrar apenas empresas que passaram pelo scrape
        empresas_com_scrape = [r for r in self.raw_results if r.get('scrape_chars', 0) > 100]
        
        self.llm.total = len(empresas_com_scrape)
        
        for r in empresas_com_scrape:
            success = r.get('success', False)
            error = r.get('error', '')
            completeness = r.get('profile_completeness', 0)
            
            if success and completeness > 0:
                self.llm.sucesso += 1
            else:
                self.llm.falha += 1
                
                # Classificar erro
                error_lower = error.lower()
                if 'timeout' in error_lower:
                    self.llm.erro_timeout += 1
                elif 'rate' in error_lower or '429' in error:
                    self.llm.erro_rate_limit += 1
                elif 'parse' in error_lower or 'json' in error_lower:
                    self.llm.erro_parse += 1
                elif 'token' in error_lower:
                    self.llm.erro_token_limit += 1
                else:
                    self.llm.erro_outros += 1
        
        # Imprimir resultados
        if self.llm.total == 0:
            print("\n⚠️ Nenhuma empresa chegou na etapa de LLM")
            return
        
        print(f"\n📊 RESULTADO GERAL:")
        print(f"   Total que chegou no LLM: {self.llm.total}")
        print(f"   Sucesso: {self.llm.sucesso} ({self.llm.sucesso/self.llm.total*100:.1f}%)")
        print(f"   Falha: {self.llm.falha} ({self.llm.falha/self.llm.total*100:.1f}%)")
        
        if self.llm.falha > 0:
            print(f"\n❌ DISTRIBUIÇÃO DE ERROS:")
            erros = [
                ("Timeout", self.llm.erro_timeout),
                ("Rate Limit (429)", self.llm.erro_rate_limit),
                ("Erro de Parse", self.llm.erro_parse),
                ("Token Limit", self.llm.erro_token_limit),
                ("Outros", self.llm.erro_outros),
            ]
            
            for nome, qtd in sorted(erros, key=lambda x: -x[1]):
                if qtd > 0:
                    pct = qtd / self.llm.falha * 100
                    print(f"   {qtd:3d}x ({pct:5.1f}%) - {nome}")
        
        # Identificar gargalo
        print(f"\n🚨 GARGALO PRINCIPAL NO LLM:")
        if self.llm.erro_timeout > self.llm.falha * 0.4:
            print(f"   ❌ TIMEOUT ({self.llm.erro_timeout} casos)")
            print(f"   💡 SUGESTÃO: Aumentar default_timeout do LLM ou reduzir chunk_size")
        elif self.llm.erro_rate_limit > self.llm.falha * 0.3:
            print(f"   ❌ RATE LIMIT ({self.llm.erro_rate_limit} casos)")
            print(f"   💡 SUGESTÃO: Adicionar mais providers ou implementar backoff")
        elif self.llm.erro_parse > self.llm.falha * 0.2:
            print(f"   ❌ ERROS DE PARSE ({self.llm.erro_parse} casos)")
            print(f"   💡 SUGESTÃO: Melhorar prompt ou usar json_repair")
        else:
            print(f"   ✅ LLM funcionando adequadamente")
    
    def analyze_completeness(self):
        """Analisa completude dos perfis gerados."""
        print("\n" + "="*70)
        print("📋 ANÁLISE DE COMPLETUDE")
        print("="*70)
        
        sucessos = [r for r in self.raw_results if r.get('success')]
        
        if not sucessos:
            print("\n⚠️ Nenhum sucesso para analisar")
            return
        
        completudes = [r.get('profile_completeness', 0) for r in sucessos]
        campos_preenchidos = [r.get('profile_fields_filled', 0) for r in sucessos]
        
        print(f"\n📊 COMPLETUDE DOS PERFIS:")
        print(f"   Total de sucessos: {len(sucessos)}")
        print(f"   Completude média: {sum(completudes)/len(completudes):.1f}%")
        print(f"   Completude mínima: {min(completudes):.1f}%")
        print(f"   Completude máxima: {max(completudes):.1f}%")
        print(f"   Campos médios preenchidos: {sum(campos_preenchidos)/len(campos_preenchidos):.1f}")
        
        # Distribuição
        faixas = {
            "Excelente (>80%)": len([c for c in completudes if c > 80]),
            "Bom (60-80%)": len([c for c in completudes if 60 <= c <= 80]),
            "Regular (40-60%)": len([c for c in completudes if 40 <= c < 60]),
            "Ruim (<40%)": len([c for c in completudes if c < 40]),
        }
        
        print(f"\n📏 DISTRIBUIÇÃO POR FAIXA:")
        for faixa, qtd in faixas.items():
            pct = qtd / len(sucessos) * 100
            print(f"   {faixa}: {qtd} ({pct:.1f}%)")
    
    def analyze_timing(self):
        """Analisa tempos de processamento."""
        print("\n" + "="*70)
        print("⏱️ ANÁLISE DE TEMPO")
        print("="*70)
        
        sucessos = [r for r in self.raw_results if r.get('success')]
        falhas = [r for r in self.raw_results if not r.get('success')]
        
        if sucessos:
            tempos_sucesso = [r.get('duration_seconds', 0) for r in sucessos]
            print(f"\n✅ TEMPOS DOS SUCESSOS:")
            print(f"   Média: {sum(tempos_sucesso)/len(tempos_sucesso):.1f}s")
            print(f"   Mínimo: {min(tempos_sucesso):.1f}s")
            print(f"   Máximo: {max(tempos_sucesso):.1f}s")
            
            # Distribuição
            rapidos = len([t for t in tempos_sucesso if t < 30])
            medios = len([t for t in tempos_sucesso if 30 <= t < 60])
            lentos = len([t for t in tempos_sucesso if t >= 60])
            
            print(f"\n   Distribuição:")
            print(f"   Rápidos (<30s): {rapidos} ({rapidos/len(tempos_sucesso)*100:.1f}%)")
            print(f"   Médios (30-60s): {medios} ({medios/len(tempos_sucesso)*100:.1f}%)")
            print(f"   Lentos (>60s): {lentos} ({lentos/len(tempos_sucesso)*100:.1f}%)")
        
        if falhas:
            tempos_falha = [r.get('duration_seconds', 0) for r in falhas]
            print(f"\n❌ TEMPOS DAS FALHAS:")
            print(f"   Média: {sum(tempos_falha)/len(tempos_falha):.1f}s")
            print(f"   Mínimo: {min(tempos_falha):.1f}s")
            print(f"   Máximo: {max(tempos_falha):.1f}s")
            
            # Quantos bateram no timeout
            timeouts = len([t for t in tempos_falha if t >= 89])
            print(f"   Timeouts (>=89s): {timeouts} ({timeouts/len(tempos_falha)*100:.1f}%)")
    
    def generate_recommendations(self):
        """Gera recomendações baseadas na análise."""
        print("\n" + "="*70)
        print("💡 RECOMENDAÇÕES DE CONFIGURAÇÃO")
        print("="*70)
        
        recomendacoes = []
        
        # Discovery - Serper
        if self.discovery.serper_rate_limit > 5:
            recomendacoes.append({
                "modulo": "Serper",
                "parametro": "rate_limit",
                "atual": "sem limite",
                "sugerido": "implementar backoff exponencial",
                "razao": f"{self.discovery.serper_rate_limit} rate limits na API",
                "prioridade": 1
            })
        
        if self.discovery.serper_timeout > self.discovery.serper_necessario * 0.2:
            recomendacoes.append({
                "modulo": "Serper",
                "parametro": "timeout",
                "atual": "10s",
                "sugerido": "15s",
                "razao": f"{self.discovery.serper_timeout} timeouts no Serper",
                "prioridade": 1
            })
        
        if self.discovery.serper_falha > self.discovery.serper_necessario * 0.3:
            recomendacoes.append({
                "modulo": "Discovery",
                "parametro": "search_queries",
                "atual": "nome + cidade",
                "sugerido": "adicionar CNAE e razão social",
                "razao": f"{self.discovery.serper_falha} sites não encontrados",
                "prioridade": 2
            })
        
        # Discovery - URL Prober
        if self.discovery.prober_timeout > self.discovery.total * 0.2:
            recomendacoes.append({
                "modulo": "URLProber",
                "parametro": "timeout",
                "atual": "10.0s",
                "sugerido": "15.0s",
                "razao": f"{self.discovery.prober_timeout} timeouts no prober",
                "prioridade": 2
            })
        
        # Scraper
        if self.scraper.erro_timeout > self.scraper.falha * 0.3:
            recomendacoes.append({
                "modulo": "Scraper",
                "parametro": "session_timeout",
                "atual": "15s",
                "sugerido": "25s",
                "razao": f"{self.scraper.erro_timeout} timeouts no scrape",
                "prioridade": 2
            })
        
        if self.scraper.erro_empty_content > self.scraper.falha * 0.2:
            recomendacoes.append({
                "modulo": "Scraper",
                "parametro": "default_strategy",
                "atual": "standard",
                "sugerido": "robust",
                "razao": f"{self.scraper.erro_empty_content} casos de conteúdo vazio",
                "prioridade": 2
            })
        
        if self.scraper.erro_cloudflare + self.scraper.erro_waf > self.scraper.falha * 0.2:
            recomendacoes.append({
                "modulo": "Scraper",
                "parametro": "default_strategy",
                "atual": "standard",
                "sugerido": "aggressive",
                "razao": f"{self.scraper.erro_cloudflare + self.scraper.erro_waf} bloqueios por proteção",
                "prioridade": 1
            })
        
        # LLM
        if self.llm.erro_timeout > self.llm.falha * 0.3:
            recomendacoes.append({
                "modulo": "LLM",
                "parametro": "default_timeout",
                "atual": "60s",
                "sugerido": "90s",
                "razao": f"{self.llm.erro_timeout} timeouts no LLM",
                "prioridade": 2
            })
        
        if self.llm.erro_rate_limit > self.llm.falha * 0.2:
            recomendacoes.append({
                "modulo": "LLM",
                "parametro": "providers",
                "atual": "2 (OpenAI, Gemini)",
                "sugerido": "3+ (adicionar OpenRouter)",
                "razao": f"{self.llm.erro_rate_limit} rate limits",
                "prioridade": 1
            })
        
        # Imprimir recomendações
        if not recomendacoes:
            print("\n✅ Nenhuma recomendação crítica. Sistema bem configurado!")
            return
        
        print(f"\nEncontradas {len(recomendacoes)} recomendações:\n")
        
        for r in sorted(recomendacoes, key=lambda x: x['prioridade']):
            prioridade = "🔴 ALTA" if r['prioridade'] == 1 else "🟡 MÉDIA"
            print(f"{prioridade} | {r['modulo']}.{r['parametro']}")
            print(f"   Atual: {r['atual']} → Sugerido: {r['sugerido']}")
            print(f"   Razão: {r['razao']}")
            print()
    
    def full_analysis(self):
        """Executa análise completa."""
        print("\n" + "#"*70)
        print("#" + " "*20 + "ANÁLISE COMPLETA DO SISTEMA" + " "*20 + "#")
        print("#"*70)
        
        self.analyze_discovery()
        self.analyze_scraper()
        self.analyze_llm()
        self.analyze_completeness()
        self.analyze_timing()
        self.generate_recommendations()
        
        # Resumo final
        print("\n" + "="*70)
        print("📊 RESUMO EXECUTIVO")
        print("="*70)
        
        total = len(self.raw_results)
        discovery_ok = self.discovery.prober_sucesso
        scrape_ok = self.scraper.sucesso
        llm_ok = self.llm.sucesso
        
        print(f"\n🔢 FUNIL DE CONVERSÃO:")
        print(f"   Total empresas: {total}")
        print(f"   └─ Discovery OK: {discovery_ok} ({discovery_ok/total*100:.1f}%)")
        if discovery_ok > 0:
            print(f"      └─ Scrape OK: {scrape_ok} ({scrape_ok/discovery_ok*100:.1f}% do discovery)")
        if scrape_ok > 0:
            print(f"         └─ LLM OK: {llm_ok} ({llm_ok/scrape_ok*100:.1f}% do scrape)")
        
        # Taxa final
        taxa_final = llm_ok / total * 100 if total > 0 else 0
        print(f"\n🎯 TAXA FINAL DE SUCESSO: {taxa_final:.1f}%")
        
        if taxa_final >= 70:
            print("   ✅ APROVADO!")
        else:
            print(f"   ❌ REPROVADO (meta: 70%)")
            print(f"   Faltam: {int(total * 0.7) - llm_ok} sucessos para aprovar")


def main():
    """Executa análise do último teste."""
    analyzer = DetailedAnalyzer()
    analyzer.load_latest_log()
    analyzer.full_analysis()


if __name__ == "__main__":
    main()

