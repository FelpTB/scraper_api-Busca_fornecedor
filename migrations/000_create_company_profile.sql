-- Migration: Criar tabela company_profile (se não existir)
-- Descrição: Tabela principal para armazenar perfis completos de empresas

CREATE TABLE IF NOT EXISTS company_profile (
  id                BIGSERIAL PRIMARY KEY,
  company_name      TEXT,
  cnpj              TEXT UNIQUE,
  industry          TEXT,
  business_model    TEXT,
  target_audience   TEXT,
  geographic_coverage TEXT,
  founding_year     SMALLINT,
  employee_count_min INTEGER,
  employee_count_max INTEGER,
  headquarters_address TEXT,
  linkedin_url      TEXT,
  website_url       TEXT,
  profile_json      JSONB NOT NULL,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_company_profile_cnpj ON company_profile (cnpj);
CREATE INDEX IF NOT EXISTS idx_company_profile_created ON company_profile (created_at DESC);

