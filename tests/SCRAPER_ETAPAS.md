# Mapeamento Completo do Processo de Scraping

## Visão Geral

O processo de scraping é composto por **8 etapas principais**, cada uma com suas subetapas. Este documento mapeia todas as etapas, módulos dependentes e pontos de otimização.

---

## Arquitetura dos Módulos

```
app/services/scraper/
├── __init__.py              # Exports e configuração
├── scraper_service.py       # Orquestrador principal (scrape_url)
├── url_prober.py           # Probe de URLs e variações
├── site_analyzer.py        # Análise de tipo e proteção
├── protection_detector.py  # Detecção de proteções
├── strategy_selector.py    # Seleção de estratégias
├── http_client.py          # Cliente HTTP (cffi/curl)
├── html_parser.py          # Parser HTML e extração
├── link_selector.py        # Seleção de links com LLM
├── circuit_breaker.py      # Circuit breaker por domínio
├── constants.py            # Configurações e constantes
└── models.py               # Modelos de dados
```

---

## ETAPA 1: Consulta de Conhecimento Prévio

**Objetivo:** Verificar se já temos conhecimento sobre o site.

**Módulos:** `app/services/learning/site_knowledge.py`, `app/services/learning/adaptive_config.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 1.1 | Consultar site_knowledge | Busca perfil existente do site | ~0.1ms |
| 1.2 | Usar aprendizado global | Se site novo, usa padrões aprendidos | ~0.01ms |

### Dados Coletados:
- `known_strategy`: Estratégia que funcionou anteriormente
- `known_protection`: Tipo de proteção conhecida
- `total_attempts`: Número de tentativas anteriores

---

## ETAPA 2: Probe URL

**Objetivo:** Encontrar a melhor variação de URL acessível.

**Módulo:** `app/services/scraper/url_prober.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 2.1 | Verificar cache | Verifica se URL já foi validada | ~0.01ms |
| 2.2 | Testar URL original | Testa a URL fornecida primeiro | ~500-2000ms |
| 2.3 | Gerar variações | Gera http/https, www/non-www | ~0.1ms |
| 2.4 | Testar variações | Testa variações em paralelo | ~1000-5000ms |
| 2.5 | Selecionar melhor | Escolhe a mais rápida com status OK | ~0.1ms |

### Configurações:
- `timeout`: 10s por variação
- `max_concurrent`: 500 conexões simultâneas

### Pontos de Otimização:
- ⚡ Cache agressivo de URLs validadas
- ⚡ Paralelização das variações
- ⚡ Usar HEAD request ao invés de GET

---

## ETAPA 3: Análise do Site

**Objetivo:** Determinar tipo de site e proteções.

**Módulos:** `site_analyzer.py`, `protection_detector.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 3.1 | Probe inicial | GET completo para medir tempo de resposta | ~500-3000ms |
| 3.2 | Detectar proteção | Cloudflare, WAF, Captcha, Rate Limit, Bot | ~1ms |
| 3.3 | Detectar tipo site | Static, SPA, Hybrid, Unknown | ~10ms |
| 3.4 | Verificar robots.txt | GET em /robots.txt | ~200-1000ms |
| 3.5 | Selecionar estratégia | Determina melhor abordagem | ~0.1ms |

### Tipos de Site:
- **Static**: Site tradicional HTML
- **SPA**: Single Page Application (React, Vue, Angular)
- **Hybrid**: Parcialmente SPA
- **Unknown**: Não determinado

### Tipos de Proteção:
- **None**: Sem proteção
- **Cloudflare**: Challenge Cloudflare
- **WAF**: Web Application Firewall
- **Captcha**: reCAPTCHA, hCaptcha
- **Rate_limit**: Limitação de taxa
- **Bot_detection**: Detecção de bot genérica

### Pontos de Otimização:
- ⚡ Cache do resultado de análise
- ⚡ Paralelizar probe + robots.txt
- ⚠️ robots.txt é opcional - considerar remover

---

## ETAPA 4: Seleção de Estratégias

**Objetivo:** Definir ordem de estratégias a tentar.

**Módulo:** `strategy_selector.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 4.1 | Consultar por proteção | Lista estratégias para proteção detectada | ~0.01ms |
| 4.2 | Consultar por tipo | Lista estratégias para tipo de site | ~0.01ms |
| 4.3 | Priorizar conhecimento | Move estratégia conhecida para topo | ~0.01ms |
| 4.4 | Ordenar estratégias | Ordena por prioridade final | ~0.01ms |

### Estratégias Disponíveis:
| Estratégia | Timeout | Proxy | UA Rotation | Uso |
|------------|---------|-------|-------------|-----|
| **FAST** | 10s | Não | Não | Sites rápidos sem proteção |
| **STANDARD** | 15s | Sim | Não | Sites normais |
| **ROBUST** | 20s | Sim | Sim | Sites com proteção leve |
| **AGGRESSIVE** | 25s | Sim | Sim + Rotation | Sites com proteção forte |

---

## ETAPA 5: Scrape da Main Page

**Objetivo:** Obter conteúdo da página principal.

**Módulos:** `http_client.py`, `html_parser.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 5.1 | Tentar estratégia | Executa scrape com estratégia atual | ~500-5000ms |
| 5.1.1 | Rotação de UA | Seleciona User-Agent se configurado | ~0.01ms |
| 5.1.2 | Obter proxy | Busca proxy do pool se configurado | ~0.1ms |
| 5.1.3 | HTTP Request | curl_cffi ou system curl | ~500-4000ms |
| 5.1.4 | Verificar qualidade | Valida >= 500 chars | ~0.1ms |
| 5.1.5 | Detectar proteção | Verifica Cloudflare/WAF no corpo | ~1ms |
| 5.1.6 | Fallback | Tenta próxima estratégia se falhou | - |
| 5.2 | Parsing HTML | BeautifulSoup extrai texto | ~10-100ms |
| 5.2.1 | Extrair texto | Remove scripts, extrai texto limpo | ~5-50ms |
| 5.2.2 | Extrair docs | Links de PDFs, DOCs | ~1-10ms |
| 5.2.3 | Extrair links | Links internos | ~1-10ms |
| 5.3 | Verificar qualidade | soft 404, Cloudflare challenge | ~1ms |

### Métodos de HTTP:
1. **curl_cffi**: Imita Chrome, bypass Cloudflare
2. **system_curl**: Fallback usando curl do sistema

### Pontos de Otimização:
- ⚡ Usar HEAD para verificar antes de GET
- ⚡ Streaming para páginas grandes
- ⚠️ Verificar necessidade de todas as estratégias

---

## ETAPA 6: Seleção de Links (LLM)

**Objetivo:** Priorizar links mais relevantes para perfil.

**Módulo:** `link_selector.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 6.1 | Filtrar não-HTML | Remove docs, imagens, assets | ~1-5ms |
| 6.2 | Short-circuit | Se <= max_links, retorna todos | ~0.1ms |
| 6.3 | Chamar LLM | GPT/Gemini para priorizar | ~500-3000ms |
| 6.4 | Parsear resposta | Extrai índices do JSON | ~1ms |
| 6.5 | Fallback heurísticas | Se LLM falhar, usa keywords | ~1ms |

### Keywords de Alta Prioridade:
- sobre, quem-somos, institucional
- produtos, serviços, soluções
- clientes, cases, projetos
- contato, equipe

### Keywords de Baixa Prioridade:
- blog, news, login, cart, policy

### Pontos de Otimização:
- ⚡ Cache de respostas LLM por padrão de site
- ⚡ Heurísticas mais agressivas para reduzir chamadas LLM
- ⚠️ Considerar remover LLM e usar só heurísticas

---

## ETAPA 7: Scrape das Subpáginas

**Objetivo:** Coletar conteúdo das páginas selecionadas.

**Módulos:** `http_client.py`, `circuit_breaker.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 7.1 | Dividir em chunks | Agrupa URLs em lotes de 20 | ~0.1ms |
| 7.2 | Processar chunk | Para cada chunk: | - |
| 7.2.1 | Obter proxy | Proxy compartilhado para chunk | ~0.1ms |
| 7.2.2 | Criar sessão | Sessão curl_cffi compartilhada | ~10ms |
| 7.2.3 | Scrape URLs | Para cada URL no chunk | ~100-2000ms/URL |
| 7.2.4 | Circuit breaker | Pula domínios com muitas falhas | ~0.1ms |
| 7.2.5 | Normalizar URL | Remove caracteres problemáticos | ~0.1ms |
| 7.2.6 | Fallback | system_curl se cffi falhar | - |
| 7.3 | Consolidar | Agrupa todos os resultados | ~0.1ms |

### Configurações:
- `chunk_size`: 20 URLs por chunk
- `chunk_semaphore_limit`: 100 chunks paralelos
- `circuit_breaker_threshold`: 5 falhas para abrir

### Pontos de Otimização:
- ⚡ **PRINCIPAL GARGALO** - Otimizar paralelismo
- ⚡ Aumentar chunk_size para sites estáveis
- ⚡ Reutilizar sessões HTTP entre chunks
- ⚡ Pipelining de requests

---

## ETAPA 8: Consolidação e Aprendizado

**Objetivo:** Agregar resultados e registrar aprendizado.

**Módulos:** `models.py`, `site_knowledge.py`

### Subetapas:
| # | Subetapa | Descrição | Tempo Típico |
|---|----------|-----------|--------------|
| 8.1 | Criar ScrapedContent | Objeto com todos os dados | ~0.1ms |
| 8.2 | Calcular métricas | success_rate, visited_urls | ~0.1ms |
| 8.3 | Registrar aprendizado | Atualiza site_knowledge | ~1ms |
| 8.4 | Retornar | Retorna conteúdo agregado | ~0.1ms |

---

## Fluxo de Dados

```
URL Input
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 1: Conhecimento Prévio                                  │
│   site_knowledge.get_profile() → known_strategy, protection   │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 2: Probe URL                                            │
│   url_prober.probe() → best_url, response_time                │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 3: Análise do Site                                      │
│   site_analyzer.analyze() → SiteProfile                       │
│   (site_type, protection_type, requires_js, best_strategy)    │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 4: Seleção de Estratégias                              │
│   strategy_selector.select() → [strategies ordered]           │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 5: Scrape Main Page                                     │
│   _scrape_main_page() → ScrapedPage                           │
│   (content, links, documents, strategy_used)                  │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 6: Seleção de Links                                     │
│   select_links_with_llm() → [target_subpages]                 │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 7: Scrape Subpáginas     ⚠️ PRINCIPAL GARGALO           │
│   _scrape_subpages_adaptive() → [ScrapedPage]                 │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│ ETAPA 8: Consolidação                                         │
│   ScrapedContent + site_knowledge.record_success()            │
└───────────────────────────────────────────────────────────────┘
    │
    ▼
Output: (aggregated_content, document_links, visited_urls)
```

---

## Distribuição de Tempo Típica

| Etapa | % do Tempo | Prioridade Otimização |
|-------|------------|----------------------|
| Subpáginas (7) | 70-80% | 🔴 ALTA |
| Análise (3) | 10-15% | 🟡 MÉDIA |
| Main Page (5) | 5-10% | 🟡 MÉDIA |
| Links LLM (6) | 3-8% | 🟡 MÉDIA |
| Probe (2) | 2-5% | 🟢 BAIXA |
| Outros (1,4,8) | <1% | 🟢 BAIXA |

---

## Testes Disponíveis

```bash
# Teste detalhado com métricas de cada etapa
python tests/suites/test_scraper_detailed.py [n_urls] [concurrent] [timeout] [max_subpages]

# Analisar relatório gerado
python tests/suites/analyze_scraper_report.py [report_path]
```

### Exemplos:
```bash
# Teste rápido com 10 URLs
python tests/suites/test_scraper_detailed.py 10 5 60 10

# Teste completo com 100 URLs
python tests/suites/test_scraper_detailed.py 100 20 120 30

# Analisar último relatório
python tests/suites/analyze_scraper_report.py
```

