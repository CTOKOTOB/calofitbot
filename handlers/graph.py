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
        # Получение user_id из таблицы users
        user_row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1",
            user_tg_id
        )
        if not user_row:
            await message.answer("Пользователь не найден в базе.")
            return
        user_id = user_row["id"]

        # Получение данных по калориям по датам
        rows = await conn.fetch("""
            SELECT DATE(created_at) AS date, SUM(calories) AS total
            FROM calories
            WHERE user_id = $1
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
        """, user_id)

    if not rows:
        await message.answer("Нет данных для построения графика.")
        return

    # Подготовка данных
    dates = [row["date"].strftime("%Y-%m-%d") for row in rows]
    totals = [row["total"] for row in rows]

    # Построение графика
    plt.figure(figsize=(10, 5))
    plt.plot(dates, totals, marker='o', color='blue')
    plt.title("Калории по дням")
    plt.xlabel("Дата")
    plt.ylabel("Калории")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()

    # Сохранение графика в буфер
    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()

    # Отправка фото
    await message.answer_photo(BufferedInputFile(buffer.read(), filename="calories_graph.png"))

