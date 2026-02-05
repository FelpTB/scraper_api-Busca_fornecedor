"""
Aplica a migração 001_queue_profile.sql no banco.
Uso: python run_migration_queue.py
Requer DATABASE_URL no ambiente ou em .env.
"""
import asyncio
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def main():
    try:
        import asyncpg
    except ImportError:
        print("Instale asyncpg: pip install asyncpg")
        return 1
    url = os.getenv("DATABASE_URL")
    if not url:
        print("Configure DATABASE_URL (ambiente ou .env)")
        return 1
    sql_path = Path(__file__).parent / "migrations" / "001_queue_profile.sql"
    sql = sql_path.read_text(encoding="utf-8")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(sql)
        print("Migração 001_queue_profile aplicada com sucesso.")
    finally:
        await conn.close()
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))
