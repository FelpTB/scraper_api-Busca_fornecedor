-- Migration: Criar tabela scraped_chunks
-- Descrição: Armazena chunks processados do conteúdo scrapado

CREATE TABLE IF NOT EXISTS scraped_chunks (
  id              BIGSERIAL PRIMARY KEY,
  cnpj_basico     VARCHAR(14) NOT NULL,
  discovery_id    BIGINT REFERENCES website_discovery(id),
  website_url     TEXT NOT NULL,
  chunk_index     INTEGER NOT NULL,
  total_chunks    INTEGER NOT NULL,
  chunk_content   TEXT NOT NULL,
  token_count     INTEGER,
  page_source     TEXT,  -- URL da página de origem
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_chunks_cnpj ON scraped_chunks (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_chunks_discovery ON scraped_chunks (discovery_id);

