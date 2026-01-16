-- Migration: Criar tabela serper_results
-- Descrição: Armazena resultados da busca Google via Serper API

CREATE TABLE IF NOT EXISTS serper_results (
  id            BIGSERIAL PRIMARY KEY,
  cnpj_basico   VARCHAR(14) NOT NULL,
  company_name  TEXT,
  razao_social  TEXT,
  nome_fantasia TEXT,
  municipio     TEXT,
  query_used    TEXT,
  results_json  JSONB NOT NULL,  -- Array de {title, link, snippet}
  results_count INTEGER,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_serper_cnpj ON serper_results (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_serper_created ON serper_results (created_at DESC);

