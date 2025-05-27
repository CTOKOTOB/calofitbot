import re
from aiogram import Router
from aiogram.types import Message

from db.database import get_or_create_user, get_db_pool
from .yandex_gpt import query_yandex_gpt

router = Router()


@router.message()
async def handle_text(message: Message):
    user_id = await get_or_create_user(message.from_user)
    input_text = message.text.strip()

    try:
        if input_text.isdigit():
            calories = int(input_text)
            await log_calories(user_id, input_text, calories, message)
            await message.reply(f"✅ Записано: {calories} ккал")
        else:
            calories_str = await query_yandex_gpt(input_text)
            print(f"Yandex GPT response: '{calories_str}'")  # отладка

            match = re.search(r'\d+', calories_str)
            calories = int(match.group()) if match else None

            await log_calories(user_id, input_text, calories, message)
            await message.reply(
                f"✅ Записано: {calories or '?'} ккал" + (" (примерно)" if calories is None else "")
            )
    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply("🔧 Произошла техническая ошибка")
        print(f"Error for user {user_id}: {str(e)}")

async def log_calories(user_id: int, input_text: str, calories: int | None, message: Message):
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
