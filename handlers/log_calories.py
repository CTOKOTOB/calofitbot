import re
import logging
from typing import Optional
from aiogram import Router
from aiogram.types import Message

from db.database import get_or_create_user, get_db_pool
from .yandex_gpt import query_yandex_gpt

router = Router()
logger = logging.getLogger(__name__)

@router.message()
async def handle_text(message: Message) -> None:
    user_id = await get_or_create_user(message.from_user)
    input_text = message.text.strip()

    try:
        if input_text.isdigit():
            calories = int(input_text)
        else:
            calories = await get_cached_calories(user_id, input_text)    # попытка получить из кэша
            if calories is None:
                # запрашиваем YandexGPT, если в кэше нет
                calories_str = await query_yandex_gpt(input_text)
                logger.debug(f"Yandex GPT response: '{calories_str}'")

                numbers = [int(m) for m in re.findall(r'\d+', calories_str)]
                calories = numbers[0] if numbers else None

                if calories is not None:
                    await cache_calories(input_text, calories)

        await log_calories(user_id, input_text, calories, message)
        response = f"✅ Записано: {calories if calories is not None else '?'} ккал"
        if calories is None:
            response += " (примерно)"
        await message.reply(response)

    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        logger.exception(f"Error for user {user_id}")  # Логируем с traceback
        await message.reply("🔧 Произошла техническая ошибка")

async def log_calories(user_id: int, input_text: str, calories: Optional[int], message: Message) -> None:
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        today_count = await conn.fetchval(
            "SELECT COUNT(*) FROM calories WHERE user_id = $1 AND created_at >= current_date",
            user_id
        )

        if 35 <= today_count < 40:
            await message.reply(f"⚠️ Внимание: осталось {40 - today_count} из 40 записей на сегодня")

        if today_count >= 40:
            raise ValueError("❌ Достигнут дневной лимит в 40 записей")

        await conn.execute(
            "INSERT INTO calories (user_id, input, calories) VALUES ($1, $2, $3)",
            user_id, input_text, calories
        )

async def get_cached_calories(user_id: int, input_text: str) -> Optional[int]:
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        # Сначала смотрим локальный кэш пользователя
        row = await conn.fetchrow(
           # "SELECT calories FROM user_calorie_cache WHERE user_id = $1 AND input = $2",
            "SELECT calories FROM user_calorie_cache WHERE user_id = $1 AND LOWER(input) = LOWER($2)",
            user_id, input_text
        )
        if row:
            return row["calories"]
        # Потом глобальный кэш
        row = await conn.fetchrow(
            #"SELECT calories FROM calorie_cache WHERE input = $1",
            "SELECT calories FROM calorie_cache WHERE LOWER(input) = LOWER($1)",
            input_text
        )
        return row["calories"] if row else None

async def cache_calories(input_text: str, calories: int) -> None:
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO calorie_cache (input, calories) VALUES ($1, $2)
               ON CONFLICT (input) DO UPDATE SET calories = EXCLUDED.calories""",
            input_text, calories
        )
