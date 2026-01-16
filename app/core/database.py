"""
Conexão assíncrona com PostgreSQL via asyncpg.
"""
import asyncpg
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Pool global de conexões
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Retorna pool de conexões (singleton).
    Cria pool na primeira chamada.
    
    Returns:
        asyncpg.Pool: Pool de conexões assíncrono
        
    Raises:
        Exception: Se não conseguir criar o pool
    """
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )
            logger.info(f"✅ Pool asyncpg criado (min=5, max=20)")
        except Exception as e:
            logger.error(f"❌ Erro ao criar pool asyncpg: {e}")
            raise
    return _pool


async def close_pool():
    """
    Fecha pool de conexões (chamar no shutdown).
    """
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("🔌 Pool asyncpg fechado")


async def test_connection() -> bool:
    """
    Testa a conexão com o banco de dados.
    
    Returns:
        bool: True se a conexão está funcionando
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"❌ Erro ao testar conexão: {e}")
        return False

