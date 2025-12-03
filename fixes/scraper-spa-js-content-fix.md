# Correção: Scraper não extrai conteúdo de sites SPA e JS-heavy

**Data:** 2025-12-03  
**Arquivo:** `app/services/scraper.py`  
**Casos:** DELTA SOLUCOES (deltaaut.com), DAVI MECANICA (davimecanicadiesel.com.br)

## Problema

### Caso 1: DELTA SOLUCOES (deltaaut.com)
- Site foi identificado corretamente
- Scraper retornou apenas 163 caracteres e 0 links
- Site é uma SPA (Single Page Application) com todo conteúdo em uma única página
- `PruningContentFilter` estava removendo conteúdo válido

### Caso 2: DAVI MECANICA (davimecanicadiesel.com.br)
- Site usa JavaScript pesado para renderizar conteúdo
- Scraper retornava conteúdo vazio porque JS não carregava a tempo

## Causa Raiz

1. **PruningContentFilter muito agressivo:** 
   - `threshold=0.35` e `min_word_threshold=5` removiam conteúdo válido de sites com estrutura não-convencional

2. **Falta de espera pelo JavaScript:** 
   - O crawler não aguardava o carregamento completo do JS antes de extrair conteúdo

3. **Sem fallback para SPAs:** 
   - Sites sem links internos (SPAs) não eram tratados adequadamente

## Solução Implementada

### 1. Reduzir agressividade do PruningContentFilter

```python
# Antes:
md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.35, min_word_threshold=5))

# Depois:
md_generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.20, min_word_threshold=3))
```

### 2. Adicionar wait_for="networkidle"

```python
run_config = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS, 
    exclude_external_images=True, 
    markdown_generator=md_generator, 
    page_timeout=60000,
    wait_for="networkidle"  # NOVO: Aguardar rede ficar ociosa (JS carregado)
)
```

### 3. Retry automático para conteúdo muito pequeno

```python
# Se conteúdo muito pequeno, aguardar mais e tentar novamente
if result.success and result.markdown and len(result.markdown) < 500:
    logger.warning(f"⚠️ Conteúdo muito pequeno ({len(result.markdown)} chars), aguardando JS e tentando novamente...")
    await asyncio.sleep(3)  # Aguardar JS renderizar
    result = await crawler.arun(url=url, config=run_config, magic=True)
```

### 4. Fallback para SPAs sem links

```python
# Se não encontrou links mas o conteúdo da main page é substancial, usar apenas o conteúdo principal
if len(links) == 0 and main_content_size > 500:
    logger.warning(f"⚠️ [SPA DETECTADO] Site sem links internos mas com conteúdo substancial ({main_content_size} chars)")
    logger.info(f"📝 Usando apenas conteúdo da página principal (possível SPA ou site one-page)")
    return "\n".join(aggregated_markdown), list(all_pdf_links), visited_urls
```

## Logs Relacionados

Para identificar estes problemas no futuro, procurar nos logs:
- `[SPA DETECTADO]` - Indica que o fallback para SPA foi ativado
- `⚠️ Conteúdo muito pequeno` - Indica retry automático por JS lento
- `links=0` com `markdown_chars` baixo - Indica possível problema de extração

## Impacto

- Sites SPA como deltaaut.com agora terão todo o conteúdo extraído corretamente
- Sites com JS pesado como davimecanicadiesel.com.br carregarão completamente antes da extração
- Melhor cobertura de conteúdo em geral devido ao filtro menos agressivo

