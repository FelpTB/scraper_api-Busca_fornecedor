"""
Migração da tabela queue_profile no startup (idempotente).
Garante que a fila exista no Railway sem rodar script manual.
"""
import logging
from app.core.database import get_pool

logger = logging.getLogger(__name__)

SCHEMA = "busca_fornecedor"

# Função de trigger (reutilizada pelo schema_database; cria se não existir)
SQL_FUNCTION = f"""
CREATE OR REPLACE FUNCTION {SCHEMA}.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

SQL_TABLE_AND_INDEXES = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.queue_profile (
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
CREATE UNIQUE INDEX IF NOT EXISTS queue_profile_unique_active
ON {SCHEMA}.queue_profile (cnpj_basico) WHERE status IN ('queued', 'processing');
CREATE INDEX IF NOT EXISTS queue_profile_claim_idx
ON {SCHEMA}.queue_profile (status, available_at, id);
"""

# Trigger: drop antes de criar para evitar erro se já existir
SQL_TRIGGER = f"""
DROP TRIGGER IF EXISTS update_queue_profile_updated_at ON {SCHEMA}.queue_profile;
CREATE TRIGGER update_queue_profile_updated_at
    BEFORE UPDATE ON {SCHEMA}.queue_profile
    FOR EACH ROW
    EXECUTE PROCEDURE {SCHEMA}.update_updated_at_column();
"""

# Tabela e índices da fila de discovery (encontrar_site)
SQL_TABLE_DISCOVERY = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.queue_discovery (
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
CREATE UNIQUE INDEX IF NOT EXISTS queue_discovery_unique_active
ON {SCHEMA}.queue_discovery (cnpj_basico) WHERE status IN ('queued', 'processing');
CREATE INDEX IF NOT EXISTS queue_discovery_claim_idx
ON {SCHEMA}.queue_discovery (status, available_at, id);
"""

SQL_TRIGGER_DISCOVERY = f"""
DROP TRIGGER IF EXISTS update_queue_discovery_updated_at ON {SCHEMA}.queue_discovery;
CREATE TRIGGER update_queue_discovery_updated_at
    BEFORE UPDATE ON {SCHEMA}.queue_discovery
    FOR EACH ROW
    EXECUTE PROCEDURE {SCHEMA}.update_updated_at_column();
"""


async def run_queue_migration():
    """Cria schema (se não existir), tabelas queue_profile e queue_discovery, índices e triggers. Idempotente."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            await conn.execute(SQL_FUNCTION)
            await conn.execute(SQL_TABLE_AND_INDEXES)
            await conn.execute(SQL_TRIGGER)
            await conn.execute(SQL_TABLE_DISCOVERY)
            await conn.execute(SQL_TRIGGER_DISCOVERY)
        logger.info("Migração queue_profile e queue_discovery aplicada (ou já existente).")
    except Exception as e:
        logger.warning("Migração queue: %s (tabelas podem já existir)", e)
