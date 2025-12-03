from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from db.database import get_db_pool

router = Router()

# FSM состояния
class StartStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_height = State()
    waiting_for_weight = State()

# Кнопка назад
back_button = KeyboardButton(text="⬅️ Назад")

# Клавиатуры

gender_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👦"), KeyboardButton(text="👧"), KeyboardButton(text="🐓")],
        [back_button]
    ],
    resize_keyboard=True
)

back_kb = ReplyKeyboardMarkup(
    keyboard=[[back_button]],
    resize_keyboard=True
)

@router.message(Command(commands=["start"]))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! \nЯ бот помощник по питанию, буду фиксировать твои съеденные калории в течение дня, а если не знаешь точное число, просто вводи блюдо или продукт - я сам уточню у нейросети и запишу результат.\nДавай введем твои данные для более точного расчета.\nВыбери свой пол:",
        reply_markup=gender_kb
    )
    await state.set_state(StartStates.waiting_for_gender)

@router.message(StartStates.waiting_for_gender)
async def process_gender(message: Message, state: FSMContext):
    if message.text == back_button.text:
        await state.clear()
        await message.answer("Отменено.", reply_markup=ReplyKeyboardRemove())
        return

    gender_map = {
        "👦": "male",
        "👧": "female",
        "🐓": "other"
    }

    if message.text not in gender_map:
        await message.answer("Пожалуйста, выбери из кнопок.", reply_markup=gender_kb)
        return

    await state.update_data(gender=gender_map[message.text])
    await message.answer("Сколько тебе лет?", reply_markup=back_kb)
    await state.set_state(StartStates.waiting_for_age)

@router.message(StartStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if message.text == back_button.text:
        await message.answer("Вернулись к выбору пола.", reply_markup=gender_kb)
        await state.set_state(StartStates.waiting_for_gender)
        return

    if not message.text.isdigit() or not (5 <= int(message.text) <= 120):
        await message.answer("Введи возраст от 5 до 120.", reply_markup=back_kb)
        return

    await state.update_data(age=int(message.text))
    await message.answer("Теперь рост (см):", reply_markup=back_kb)
    await state.set_state(StartStates.waiting_for_height)

@router.message(StartStates.waiting_for_height)
async def process_height(message: Message, state: FSMContext):
    if message.text == back_button.text:
        await message.answer("Вернулись к возрасту.", reply_markup=back_kb)
        await state.set_state(StartStates.waiting_for_age)
        return

    try:
        height = int(message.text)
        if not (50 <= height <= 250):
            raise ValueError()
    except ValueError:
        await message.answer("Введи рост от 50 до 250 см.", reply_markup=back_kb)
        return

    await state.update_data(height_cm=height)
    await message.answer("И вес (кг):", reply_markup=back_kb)
    await state.set_state(StartStates.waiting_for_weight)

@router.message(StartStates.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    if message.text == back_button.text:
        await message.answer("Вернулись к росту.", reply_markup=back_kb)
        await state.set_state(StartStates.waiting_for_height)
        return

    try:
        weight = float(message.text.replace(",", "."))
        if not (20 <= weight <= 300):
            raise ValueError()
    except ValueError:
        await message.answer("Введи вес от 20 до 300 кг.", reply_markup=back_kb)
        return

    await state.update_data(weight_kg=weight)
    data = await state.get_data()

    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT id FROM users WHERE telegram_id = $1", message.from_user.id)

        if not user_id:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name,
            )

        await conn.execute(
            """
            INSERT INTO user_profiles (user_id, gender, age, height_cm, weight_kg)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            data["gender"],
            data["age"],
            data["height_cm"],
            data["weight_kg"]
        )

    await message.answer(
        "Спасибо! Данные сохранены. Теперь я смогу строить точные графики и считать норму!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
