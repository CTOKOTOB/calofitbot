from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from db.database import get_or_create_user, get_db_pool
from datetime import datetime

router = Router()

def build_cache_kb(rows: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{row['input']} ({row['calories']} ккал)",
            callback_data=f"add_cache::{row['id']}"
        )]
        for row in rows
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="from_cache_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "/from_cache")
async def cmd_from_cache(message: Message):
    user_id = await get_or_create_user(message.from_user)
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, input, calories FROM user_calorie_cache WHERE user_id = $1 ORDER BY input",
            user_id
        )

    if not rows:
        await message.answer("❌ У вас пока нет сохранённых блюд.")
        return

    kb = build_cache_kb(rows)
    await message.answer("🍽 Выберите блюдо из списка:", reply_markup=kb)

@router.callback_query(F.data.startswith("add_cache::"))
async def handle_add_from_cache(callback: CallbackQuery):
    user_id = await get_or_create_user(callback.from_user)
    cache_id = int(callback.data.split("::")[1])
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT input, calories FROM user_calorie_cache WHERE id = $1 AND user_id = $2",
            cache_id, user_id
        )

        if not row:
            await callback.message.edit_text("⚠️ Запись не найдена.")
            return

        await conn.execute(
            "INSERT INTO calories (user_id, input, calories, created_at) VALUES ($1, $2, $3, $4)",
            user_id, row["input"], row["calories"], datetime.now()
        )

    await callback.message.edit_text(
        f"✅ Добавлено: *{row['input']}* — *{row['calories']} ккал*",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "from_cache_back")
async def handle_from_cache_back(callback: CallbackQuery):
   await callback.message.delete()

