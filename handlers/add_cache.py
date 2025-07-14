from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.database import get_or_create_user, get_db_pool
from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton

router = Router()

class AddCacheStates(StatesGroup):
    waiting_for_input = State()
    waiting_for_calories = State()

back_button = KeyboardButton(text="⬅️ Назад")
back_kb = ReplyKeyboardMarkup(keyboard=[[back_button]], resize_keyboard=True)

@router.message(F.text == "/add_cache")
async def cmd_add_cache(message: Message, state: FSMContext):
    await state.set_state(AddCacheStates.waiting_for_input)
    await message.answer(
        "📝 *Добавление блюда в ваш личный список (локальный кэш)*\n\n"
        "Этот список уникален только для вас — никто другой не увидит и не сможет изменить его.\n"
        "Это поможет быстро получать калорийность часто употребляемых блюд без лишних запросов к GPT.\n"
        "Например, если вы часто едите «Салат Нисуаз» или «Обед в столовой», "
        "вы можете сохранить их здесь.\n\n"
        "👉 Введите название блюда или описание (регистр не важен):",
        parse_mode="Markdown",
        reply_markup=back_kb
    )

@router.message(AddCacheStates.waiting_for_input)
async def input_name(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("🚫 Отменено.", reply_markup=ReplyKeyboardRemove())
        return

    await state.update_data(input_text=message.text.strip())
    await state.set_state(AddCacheStates.waiting_for_calories)
    await message.answer("🔥 Введите калорийность:", reply_markup=back_kb)

@router.message(AddCacheStates.waiting_for_calories)
async def input_calories(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.set_state(AddCacheStates.waiting_for_input)
        await message.answer("🔁 Введите название блюда снова:", reply_markup=back_kb)
        return

    try:
        calories = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Введите калорийность числом.")
        return

    data = await state.get_data()
    user_id = await get_or_create_user(message.from_user)
    input_text = data["input_text"]

    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM user_calorie_cache WHERE user_id = $1 AND LOWER(input) = LOWER($2)",
            user_id, input_text
        )
        if exists:
            await message.answer("⚠️ Такая запись уже есть.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return

        # Добавляем новую запись
        await conn.execute(
            "INSERT INTO user_calorie_cache (user_id, input, calories) VALUES ($1, $2, $3)",
            user_id, input_text, calories
        )

    await state.clear()
    await message.answer("✅ Запись добавлена в локальный кэш.", reply_markup=ReplyKeyboardRemove())
