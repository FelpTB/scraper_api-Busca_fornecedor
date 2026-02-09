"""
Conexão assíncrona com PostgreSQL via asyncpg.

Uso: SEMPRE usar `async with pool.acquire() as conn:` para operações.
Ao sair do bloco (fim do job ou exceção), a conexão é devolvida ao pool
e não fica aberta. Nunca guardar `conn` fora do bloco.
- min_size=0: não mantém conexões ociosas (evita "too many clients already").
- No shutdown do processo, chamar close_pool() para fechar todas as conexões.
"""
import asyncpg
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Pool global de conexões
_pool: Optional[asyncpg.Pool] = None

# Schema padrão do banco de dados
DB_SCHEMA = "busca_fornecedor"


async def get_pool() -> asyncpg.Pool:
    """
    Retorna pool de conexões (singleton).
    Cria pool na primeira chamada.
    Configura o search_path para garantir que o schema correto seja usado.
    Conexões são sempre devolvidas ao pool ao sair de `async with pool.acquire() as conn`.
    
    Returns:
        asyncpg.Pool: Pool de conexões assíncrono
        
    Raises:
        Exception: Se não conseguir criar o pool
    """
    global _pool
    if _pool is None:
        try:
            # Função para configurar search_path em cada conexão
            async def init_connection(conn):
                """
                Configura search_path para cada conexão do pool.
                Executado automaticamente pelo asyncpg quando uma nova conexão é criada.
                
                IMPORTANTE: Schema sem aspas no SET search_path (foi criado sem aspas).
                """
                try:
                    # Schema sem aspas no SET search_path (foi criado sem aspas)
                    await conn.execute(f'SET search_path TO {DB_SCHEMA}, public')
                    logger.debug(f"✅ Search path configurado: {DB_SCHEMA}")
                except Exception as e:
                    # Se falhar, a conexão não será adicionada ao pool
                    logger.error(f"❌ Erro crítico ao configurar search_path no init_connection: {e}")
                    raise
            
            # min_size=0: não mantém conexões abertas quando ocioso (reduz risco de "too many clients")
            _pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=settings.DATABASE_POOL_MIN_SIZE,
                max_size=settings.DATABASE_POOL_MAX_SIZE,
                command_timeout=60,
                init=init_connection,
            )
            logger.info(
                f"✅ Pool asyncpg criado (min={settings.DATABASE_POOL_MIN_SIZE}, "
                f"max={settings.DATABASE_POOL_MAX_SIZE}, schema={DB_SCHEMA})"
            )
        except Exception as e:
            logger.error(f"❌ Erro ao criar pool asyncpg: {e}")
            raise
    return _pool


async def close_pool():
    """
    Fecha o pool de conexões (chamar no shutdown do worker/processo).
    Todas as conexões são encerradas; não levanta exceção.
    """
    global _pool
    if _pool:
        try:
            await _pool.close()
            logger.info("🔌 Pool asyncpg fechado")
        except Exception as e:
            logger.warning("Erro ao fechar pool asyncpg: %s", e)
        finally:
            _pool = None


async def with_connection(operation):
    """
    Executa uma operação assíncrona com uma conexão do pool.
    A conexão é SEMPRE devolvida ao pool ao final (sucesso ou exceção).
    Uso: result = await with_connection(lambda conn: conn.fetchrow(...))
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            return await operation(conn)
        finally:
            # Garantir que não usamos conn após a operação; o async with já devolve ao pool
            pass


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

