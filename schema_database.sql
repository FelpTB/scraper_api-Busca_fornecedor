-- ============================================================================
-- Schema: busca_fornecedor
-- Descrição: Banco de dados para armazenar perfis de empresas extraídos
-- Baseado na estrutura CompanyProfile (schema em português)
-- 
-- Estrutura do Schema Pydantic:
-- - CompanyProfile
--   - identidade: Identidade (nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios)
--   - classificacao: Classificacao (industria, modelo_negocio, publico_alvo, cobertura_geografica)
--   - ofertas: Ofertas
--     - produtos: List[CategoriaProduto] (categoria, produtos: List[str])
--     - servicos: List[Servico] (nome, descricao)
--   - reputacao: Reputacao
--     - certificacoes: List[str]
--     - premios: List[str]
--     - parcerias: List[str]
--     - lista_clientes: List[str]
--     - estudos_caso: List[EstudoCaso] (titulo, nome_cliente, industria, desafio, solucao, resultado)
--   - contato: Contato (emails, telefones, url_linkedin, url_site, endereco_matriz, localizacoes)
--   - fontes: apenas em profile_json/full_profile (não há coluna dedicada)
-- ============================================================================

-- Criar schema se não existir
CREATE SCHEMA IF NOT EXISTS busca_fornecedor;

-- Definir schema padrão para esta sessão
SET search_path TO busca_fornecedor, public;

-- ============================================================================
-- TABELA PRINCIPAL: company_profile
-- Armazena o perfil completo da empresa
-- Baseado na estrutura CompanyProfile (schema em português)
-- ============================================================================

CREATE TABLE IF NOT EXISTS busca_fornecedor.company_profile (
    id SERIAL PRIMARY KEY,
    
    -- Identidade (campos principais) - baseado em Identidade
    nome_empresa VARCHAR(500), -- identidade.nome_empresa
    cnpj VARCHAR(20) UNIQUE NOT NULL, -- identidade.cnpj
    descricao TEXT, -- identidade.descricao
    ano_fundacao VARCHAR(10), -- identidade.ano_fundacao (formato YYYY como string)
    faixa_funcionarios VARCHAR(50), -- identidade.faixa_funcionarios (ex: "10-50", "100-500")
    
    -- Classificação - baseado em Classificacao
    industria VARCHAR(200), -- classificacao.industria
    modelo_negocio VARCHAR(100), -- classificacao.modelo_negocio
    publico_alvo VARCHAR(200), -- classificacao.publico_alvo
    cobertura_geografica VARCHAR(200), -- classificacao.cobertura_geografica
    
    -- Contato - baseado em Contato
    emails TEXT[], -- contato.emails (array de emails)
    telefones TEXT[], -- contato.telefones (array de telefones)
    url_linkedin VARCHAR(500), -- contato.url_linkedin
    url_site VARCHAR(500), -- contato.url_site
    endereco_matriz TEXT, -- contato.endereco_matriz
    
    -- Campos JSONB para armazenar estrutura completa (inclui fontes no JSON)
    profile_json JSONB, -- Perfil completo em formato JSON (estrutura CompanyProfile)
    full_profile JSONB, -- Cópia completa do perfil (backup)
    
    -- Campos auxiliares (para funcionalidades futuras)
    n_exibicoes INTEGER DEFAULT 0,
    recebe_email BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para company_profile
CREATE INDEX IF NOT EXISTS idx_company_profile_cnpj ON busca_fornecedor.company_profile(cnpj);
CREATE INDEX IF NOT EXISTS idx_company_profile_nome_empresa ON busca_fornecedor.company_profile(nome_empresa);
CREATE INDEX IF NOT EXISTS idx_company_profile_industria ON busca_fornecedor.company_profile(industria);
CREATE INDEX IF NOT EXISTS idx_company_profile_updated_at ON busca_fornecedor.company_profile(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_profile_profile_json ON busca_fornecedor.company_profile USING GIN(profile_json);

-- ============================================================================
-- TABELAS AUXILIARES
-- ============================================================================

-- Localizações adicionais (filiais, escritórios) - baseado em contato.localizacoes
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_location (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    localizacao TEXT NOT NULL, -- contato.localizacoes (lista de strings)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, localizacao)
);

CREATE INDEX IF NOT EXISTS idx_company_location_company_id ON busca_fornecedor.company_location(company_id);

-- Categorias de Produtos - baseado em ofertas.produtos (List[CategoriaProduto])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_product_category (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    categoria VARCHAR(200) NOT NULL, -- CategoriaProduto.categoria
    produtos JSONB NOT NULL DEFAULT '[]'::jsonb, -- CategoriaProduto.produtos (List[str])
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_product_category_company_id ON busca_fornecedor.company_product_category(company_id);
CREATE INDEX IF NOT EXISTS idx_company_product_category_categoria ON busca_fornecedor.company_product_category(categoria);

-- Serviços - baseado em ofertas.servicos (List[Servico])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_service (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    nome VARCHAR(500) NOT NULL, -- Servico.nome
    descricao TEXT, -- Servico.descricao
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_service_company_id ON busca_fornecedor.company_service(company_id);
CREATE INDEX IF NOT EXISTS idx_company_service_nome ON busca_fornecedor.company_service(nome);

-- Certificações - baseado em reputacao.certificacoes (List[str])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_certification (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    nome VARCHAR(500) NOT NULL, -- reputacao.certificacoes (string)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, nome)
);

CREATE INDEX IF NOT EXISTS idx_company_certification_company_id ON busca_fornecedor.company_certification(company_id);

-- Prêmios - baseado em reputacao.premios (List[str])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_award (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    nome VARCHAR(500) NOT NULL, -- reputacao.premios (string)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, nome)
);

CREATE INDEX IF NOT EXISTS idx_company_award_company_id ON busca_fornecedor.company_award(company_id);

-- Parcerias - baseado em reputacao.parcerias (List[str])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_partnership (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    nome VARCHAR(500) NOT NULL, -- reputacao.parcerias (string)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, nome)
);

CREATE INDEX IF NOT EXISTS idx_company_partnership_company_id ON busca_fornecedor.company_partnership(company_id);

-- Lista de Clientes - baseado em reputacao.lista_clientes (List[str])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_client (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    nome_cliente VARCHAR(500) NOT NULL, -- reputacao.lista_clientes (string)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(company_id, nome_cliente)
);

CREATE INDEX IF NOT EXISTS idx_company_client_company_id ON busca_fornecedor.company_client(company_id);

-- Estudos de Caso - baseado em reputacao.estudos_caso (List[EstudoCaso])
CREATE TABLE IF NOT EXISTS busca_fornecedor.company_case_study (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES busca_fornecedor.company_profile(id) ON DELETE CASCADE,
    titulo VARCHAR(500), -- EstudoCaso.titulo
    nome_cliente VARCHAR(500), -- EstudoCaso.nome_cliente
    industria VARCHAR(200), -- EstudoCaso.industria
    desafio TEXT, -- EstudoCaso.desafio
    solucao TEXT, -- EstudoCaso.solucao
    resultado TEXT, -- EstudoCaso.resultado
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_company_case_study_company_id ON busca_fornecedor.company_case_study(company_id);
CREATE INDEX IF NOT EXISTS idx_company_case_study_nome_cliente ON busca_fornecedor.company_case_study(nome_cliente);

-- ============================================================================
-- TABELAS DE PROCESSAMENTO (já existentes, mantidas para referência)
-- ============================================================================

-- Serper Results (resultados de busca)
CREATE TABLE IF NOT EXISTS busca_fornecedor.serper_results (
    id SERIAL PRIMARY KEY,
    cnpj_basico VARCHAR(8) NOT NULL,
    company_name VARCHAR(500),
    razao_social VARCHAR(500),
    nome_fantasia VARCHAR(500),
    municipio VARCHAR(200),
    results_json JSONB,
    results_count INTEGER DEFAULT 0,
    query_used TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_serper_results_cnpj_basico ON busca_fornecedor.serper_results(cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_serper_results_created_at ON busca_fornecedor.serper_results(created_at DESC);

-- Website Discovery
CREATE TABLE IF NOT EXISTS busca_fornecedor.website_discovery (
    id SERIAL PRIMARY KEY,
    cnpj_basico VARCHAR(8) NOT NULL UNIQUE,
    serper_id INTEGER REFERENCES busca_fornecedor.serper_results(id),
    website_url VARCHAR(500),
    discovery_status VARCHAR(50) NOT NULL, -- 'found', 'not_found', 'error'
    confidence_score FLOAT,
    llm_reasoning TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_website_discovery_cnpj_basico ON busca_fornecedor.website_discovery(cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_website_discovery_status ON busca_fornecedor.website_discovery(discovery_status);

-- Scraped Chunks (chunks de conteúdo extraído)
CREATE TABLE IF NOT EXISTS busca_fornecedor.scraped_chunks (
    id SERIAL PRIMARY KEY,
    cnpj_basico VARCHAR(8) NOT NULL,
    discovery_id INTEGER REFERENCES busca_fornecedor.website_discovery(id),
    website_url VARCHAR(500),
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    chunk_content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    page_source TEXT, -- URLs das páginas incluídas neste chunk
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraped_chunks_cnpj_basico ON busca_fornecedor.scraped_chunks(cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_scraped_chunks_discovery_id ON busca_fornecedor.scraped_chunks(discovery_id);
CREATE INDEX IF NOT EXISTS idx_scraped_chunks_chunk_index ON busca_fornecedor.scraped_chunks(cnpj_basico, chunk_index);

-- Queue Profile (fila durável para processamento de perfil: 1 job = 1 empresa = todos os chunks)
CREATE TABLE IF NOT EXISTS busca_fornecedor.queue_profile (
    id BIGSERIAL PRIMARY KEY,
    cnpj_basico TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS queue_profile_unique_active ON busca_fornecedor.queue_profile (cnpj_basico) WHERE status IN ('queued', 'processing');
CREATE INDEX IF NOT EXISTS queue_profile_claim_idx ON busca_fornecedor.queue_profile (status, available_at, id);

-- Queue Discovery (fila durável para descoberta de site: 1 job = 1 empresa = LLM analisa serper_results)
CREATE TABLE IF NOT EXISTS busca_fornecedor.queue_discovery (
    id BIGSERIAL PRIMARY KEY,
    cnpj_basico TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS queue_discovery_unique_active ON busca_fornecedor.queue_discovery (cnpj_basico) WHERE status IN ('queued', 'processing');
CREATE INDEX IF NOT EXISTS queue_discovery_claim_idx ON busca_fornecedor.queue_discovery (status, available_at, id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION busca_fornecedor.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_company_profile_updated_at
    BEFORE UPDATE ON busca_fornecedor.company_profile
    FOR EACH ROW
    EXECUTE FUNCTION busca_fornecedor.update_updated_at_column();

CREATE TRIGGER update_website_discovery_updated_at
    BEFORE UPDATE ON busca_fornecedor.website_discovery
    FOR EACH ROW
    EXECUTE FUNCTION busca_fornecedor.update_updated_at_column();

CREATE TRIGGER update_queue_profile_updated_at
    BEFORE UPDATE ON busca_fornecedor.queue_profile
    FOR EACH ROW
    EXECUTE FUNCTION busca_fornecedor.update_updated_at_column();

CREATE TRIGGER update_queue_discovery_updated_at
    BEFORE UPDATE ON busca_fornecedor.queue_discovery
    FOR EACH ROW
    EXECUTE FUNCTION busca_fornecedor.update_updated_at_column();

-- ============================================================================
-- COMENTÁRIOS NAS TABELAS E COLUNAS
-- ============================================================================

COMMENT ON SCHEMA busca_fornecedor IS 'Schema para armazenar perfis de empresas extraídos via LLM';

COMMENT ON TABLE busca_fornecedor.company_profile IS 'Tabela principal com perfil completo da empresa';
COMMENT ON COLUMN busca_fornecedor.company_profile.profile_json IS 'Perfil completo em formato JSON (estrutura CompanyProfile)';
COMMENT ON COLUMN busca_fornecedor.company_profile.full_profile IS 'Cópia completa do perfil para backup';

COMMENT ON TABLE busca_fornecedor.company_location IS 'Localizações adicionais (filiais, escritórios)';
COMMENT ON TABLE busca_fornecedor.company_product_category IS 'Categorias de produtos com lista de produtos por categoria';
COMMENT ON TABLE busca_fornecedor.company_service IS 'Serviços oferecidos pela empresa';
COMMENT ON TABLE busca_fornecedor.company_certification IS 'Certificações da empresa';
COMMENT ON TABLE busca_fornecedor.company_award IS 'Prêmios e reconhecimentos';
COMMENT ON TABLE busca_fornecedor.company_partnership IS 'Parcerias comerciais e tecnológicas';
COMMENT ON TABLE busca_fornecedor.company_client IS 'Lista de clientes principais';
COMMENT ON TABLE busca_fornecedor.company_case_study IS 'Estudos de caso detalhados';

-- ============================================================================
-- PERMISSÕES (ajustar conforme necessário)
-- ============================================================================

-- Exemplo: conceder permissões para um usuário específico
-- GRANT USAGE ON SCHEMA busca_fornecedor TO seu_usuario;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA busca_fornecedor TO seu_usuario;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA busca_fornecedor TO seu_usuario;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
