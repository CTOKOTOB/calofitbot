# db/database.py
import os
import asyncpg

_db_pool = None

async def init_db():
    global _db_pool
    _db_pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"])
    print("✅ DB pool initialized")

def get_db_pool():
    if _db_pool is None:
        raise RuntimeError("DB pool is not initialized. Call init_db() first.")
    return _db_pool

async def get_or_create_user(user_obj):
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            user_obj.id
        )
        if user:
            return user["id"]

        return await conn.fetchval(
            "INSERT INTO users (telegram_id, username, first_name, last_name) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            user_obj.id,
            user_obj.username,
            user_obj.first_name,
            user_obj.last_name,
        )
