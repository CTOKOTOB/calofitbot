from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types.input_file import BufferedInputFile
from db.database import get_db_pool
from io import BytesIO
import matplotlib.pyplot as plt

router = Router()

@router.message(Command("graph"))
async def send_graph(message: types.Message):
    user_tg_id = message.from_user.id
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        # Получение user_id
        user_row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            user_tg_id
        )
        if not user_row:
            await message.answer("Пользователь не найден в базе.")
            return
        user_id = user_row["id"]

        # Получение данных по калориям по датам
        calorie_rows = await conn.fetch("""
            SELECT DATE(created_at) AS date, SUM(calories) AS total
            FROM calories
            WHERE user_id = $1
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """, user_id)

        if not calorie_rows:
            await message.answer("Нет данных для построения графика.")
            return

        # Получение последнего профиля пользователя
        profile_row = await conn.fetchrow("""
            SELECT gender, age, height_cm, weight_kg
            FROM user_profiles
            WHERE user_id = $1
            ORDER BY recorded_at DESC
            LIMIT 1
        """, user_id)

        if not profile_row:
            await message.answer("Сначала введите данные с помощью команды /start.")
            return

        gender = profile_row["gender"]
        age = profile_row["age"]
        height = profile_row["height_cm"]
        weight = profile_row["weight_kg"]

    # Подготовка данных
    dates = [row["date"].strftime("%Y-%m-%d") for row in calorie_rows]
    totals = [row["total"] for row in calorie_rows]

    # Расчёт нормы по формуле Миффлина-Сан Жеора
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    elif gender == "female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age  # без корректировки

    norm_calories = [bmr for _ in dates]

    # Построение графика
    plt.figure(figsize=(10, 5))
    plt.plot(dates, totals, marker='o', color='blue', label='Факт. калории')
    plt.plot(dates, norm_calories, linestyle='--', color='red', label='Норма калорий')
    plt.title("Калории по дням")
    plt.xlabel("Дата")
    plt.ylabel("Калории")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    # Сохранение графика в буфер
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()

    await message.answer_photo(BufferedInputFile(buffer.read(), filename="calories_graph.png"))
