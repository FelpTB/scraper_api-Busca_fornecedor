-- Migration: Criar tabela website_discovery
-- Descrição: Armazena sites descobertos via LLM

CREATE TABLE IF NOT EXISTS website_discovery (
  id            BIGSERIAL PRIMARY KEY,
  cnpj_basico   VARCHAR(14) NOT NULL UNIQUE,
  serper_id     BIGINT REFERENCES serper_results(id),
  website_url   TEXT,
  discovery_status VARCHAR(20) NOT NULL, -- 'found', 'not_found', 'error'
  confidence_score FLOAT,
  llm_reasoning TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_discovery_cnpj ON website_discovery (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_discovery_status ON website_discovery (discovery_status);

