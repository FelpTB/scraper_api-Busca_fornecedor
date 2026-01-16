"""
Script para executar migrations do banco de dados.
"""
import asyncio
import asyncpg
import logging
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migrations():
    """
    Executa todas as migrations na ordem correta.
    """
    migrations_dir = Path(__file__).parent
    migration_files = [
        "000_create_company_profile.sql",
        "001_create_serper_results.sql",
        "002_create_website_discovery.sql",
        "003_create_scraped_chunks.sql",
    ]
    
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        for migration_file in migration_files:
            migration_path = migrations_dir / migration_file
            if not migration_path.exists():
                logger.error(f"❌ Arquivo de migration não encontrado: {migration_path}")
                continue
            
            logger.info(f"📄 Executando migration: {migration_file}")
            with open(migration_path, 'r') as f:
                sql = f.read()
            
            try:
                await conn.execute(sql)
                logger.info(f"✅ Migration {migration_file} executada com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao executar {migration_file}: {e}")
                raise
        
        logger.info("✅ Todas as migrations foram executadas com sucesso")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())

