# Migrations do Banco de Dados

Este diretório contém as migrations SQL para criar as tabelas necessárias para a API v2.

## Ordem de Execução

Execute as migrations na seguinte ordem:

1. `001_create_serper_results.sql` - Tabela de resultados Serper
2. `002_create_website_discovery.sql` - Tabela de descoberta de sites
3. `003_create_scraped_chunks.sql` - Tabela de chunks processados

## Como Executar

### Opção 1: Via psql (PostgreSQL CLI)

```bash
psql "postgresql://postgres:UQIXJbRUopTkZjjRbZZwORImhfpipQDg@trolley.proxy.rlwy.net:32994/railway" -f migrations/001_create_serper_results.sql
psql "postgresql://postgres:UQIXJbRUopTkZjjRbZZwORImhfpipQDg@trolley.proxy.rlwy.net:32994/railway" -f migrations/002_create_website_discovery.sql
psql "postgresql://postgres:UQIXJbRUopTkZjjRbZZwORImhfpipQDg@trolley.proxy.rlwy.net:32994/railway" -f migrations/003_create_scraped_chunks.sql
```

### Opção 2: Via Python Script

```python
import asyncio
import asyncpg
from app.core.config import settings

async def run_migrations():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        # Ler e executar cada migration
        with open('migrations/001_create_serper_results.sql') as f:
            await conn.execute(f.read())
        with open('migrations/002_create_website_discovery.sql') as f:
            await conn.execute(f.read())
        with open('migrations/003_create_scraped_chunks.sql') as f:
            await conn.execute(f.read())
        print("✅ Migrations executadas com sucesso")
    finally:
        await conn.close()

asyncio.run(run_migrations())
```

## Notas

- As migrations usam `CREATE TABLE IF NOT EXISTS` para serem idempotentes
- Os índices são criados com `CREATE INDEX IF NOT EXISTS`
- A tabela `company_profile` já existe no banco (não precisa de migration)

