import asyncpg
from app.core.config import settings

# Global pools
db_pool = None

async def get_db_connection():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(settings.db_url)
    
    async with db_pool.acquire() as conn:
        yield conn
