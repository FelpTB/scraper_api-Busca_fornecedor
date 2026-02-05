-- Fila de processamento de perfil (1 job por empresa = todos os chunks = 1 perfil)
-- PRD: queue_profile

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

-- Prevenção de duplicidade: apenas um job ativo (queued ou processing) por cnpj_basico
CREATE UNIQUE INDEX IF NOT EXISTS queue_profile_unique_active
ON busca_fornecedor.queue_profile (cnpj_basico)
WHERE status IN ('queued', 'processing');

-- Otimização de claim (workers buscam próximo job)
CREATE INDEX IF NOT EXISTS queue_profile_claim_idx
ON busca_fornecedor.queue_profile (status, available_at, id);

CREATE TRIGGER update_queue_profile_updated_at
    BEFORE UPDATE ON busca_fornecedor.queue_profile
    FOR EACH ROW
    EXECUTE FUNCTION busca_fornecedor.update_updated_at_column();

COMMENT ON TABLE busca_fornecedor.queue_profile IS 'Fila durável para processamento de perfil (1 job = 1 empresa = todos os chunks)';
