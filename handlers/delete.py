from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.database import get_db_pool, get_or_create_user


router = Router()

@router.message(Command("del"))
async def handle_delete_last_entry(message: Message):
    user_id = await get_or_create_user(message.from_user)
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        deleted_entry = await conn.fetchrow(
            """DELETE FROM calories
               WHERE id = (
                   SELECT id FROM calories
                   WHERE user_id = $1
                   ORDER BY created_at DESC
                   LIMIT 1
               )
               RETURNING input, calories, created_at""",
            user_id
        )

    if deleted_entry:
        entry_info = (
            f"✅ Удалена запись:\n"
            f"🍽 {deleted_entry['input']}\n"
            f"🔥 {deleted_entry['calories'] or '?'} ккал\n"
            f"⏰ {deleted_entry['created_at'].strftime('%d.%m.%Y %H:%M')}"
        )
        await message.reply(entry_info)
    else:
        await message.reply("ℹ️ У вас нет записей для удаления.")

@router.message(Command("del_all"))
async def handle_delete_all_user_data(message: Message):
    db_pool = get_db_pool()
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить всё", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="cancel_delete")

    await message.reply(
        "⚠️ Вы уверены, что хотите удалить ВСЕ ваши данные?\n"
        "Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@router.callback_query(lambda c: c.data == "confirm_delete")
async def confirm_delete(callback: CallbackQuery):
    user_id = await get_or_create_user(callback.from_user)
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    await callback.message.edit_text("🗑️ Все ваши данные полностью удалены!")

@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("✅ Удаление отменено")
