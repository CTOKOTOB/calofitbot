from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.database import get_db_pool, get_or_create_user

router = Router()


@router.message(Command("edit_cache"))
async def edit_cache_command(message: Message):
    user_id = await get_or_create_user(message.from_user)
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT id, input, calories FROM user_calorie_cache WHERE user_id = $1 ORDER BY id",
            user_id
        )

    if not records:
        await message.answer("ℹ️ Ваш локальный кэш пуст.")
        return

    builder = InlineKeyboardBuilder()
    for r in records:
        btn_text = f"{r['input']} ({r['calories']} ккал)"
        builder.button(text=btn_text[:64], callback_data=f"delcache_{r['id']}")

    builder.button(text="⬅️ Назад", callback_data="cancel_cache_edit")
    builder.adjust(1)

    await message.answer("🧾 Ваши записи. Нажмите, чтобы удалить:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("delcache_"))
async def handle_cache_delete(callback: CallbackQuery):
    try:
        record_id = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Ошибка обработки кнопки.")
        return

    user_id = await get_or_create_user(callback.from_user)
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM user_calorie_cache WHERE id = $1 AND user_id = $2",
            record_id, user_id
        )

        if deleted == "DELETE 1":
            text = "✅ Запись удалена."
        else:
            text = "⚠️ Не удалось удалить запись. Возможно, она уже удалена."

        # Повторно отправим список
        records = await conn.fetch(
            "SELECT id, input, calories FROM user_calorie_cache WHERE user_id = $1 ORDER BY id",
            user_id
        )

    if not records:
        await callback.message.edit_text("🗑️ Все записи удалены.")
        await callback.answer(text)
        return

    builder = InlineKeyboardBuilder()
    for r in records:
        btn_text = f"{r['input']} ({r['calories']} ккал)"
        builder.button(text=btn_text[:64], callback_data=f"delcache_{r['id']}")
    builder.button(text="⬅️ Назад", callback_data="cancel_cache_edit")
    builder.adjust(1)

    await callback.message.edit_text("🧾 Ваши записи. Нажмите, чтобы удалить:", reply_markup=builder.as_markup())
    await callback.answer(text)


@router.callback_query(F.data == "cancel_cache_edit")
async def handle_cancel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("⬅️ Возврат назад.")
