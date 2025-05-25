import asyncio
import os
import json
import time
import aiohttp
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from jwt import encode as jwt_encode
from cryptography.hazmat.primitives import serialization
from aiogram.utils.keyboard import InlineKeyboardBuilder


HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

Напиши, сколько калорий было в этом приёме пищи — я сохраню данные в базу.
Если не знаешь точное число, просто перечисли продукты или блюда, и я уточню калорийность с помощью нейросети, а потом добавлю в базу

/start - Начало работы
/help - Показать эту справку
/del - Удалить последнюю запись
/report - Отчет за сегодняшний день

<b>Лимиты:</b> Не более 40 записей в день

"""

SYSTEM_PROMPT = "Ты помощник по питанию. Пользователь пишет название блюда или продукта, а ты отвечаешь только числом — сколько в нём примерно килокалорий. Никаких слов, только число. Если указывается готовая еда или блюдо, то стоит считать не за 100грамм, а за порцию."

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
FOLDER_ID = "b1gjo1fm56glmpd0hs5r"

# Инициализация aiogram
bot = Bot(token=os.environ["CALOFITBOT_TOKEN"])
dp = Dispatcher()
db_pool = None
YANDEX_API_KEY = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"])

async def get_iam_token_from_keyfile(path_to_keyfile: str) -> str:
    with open(path_to_keyfile, 'r') as f:
        key_data = json.load(f)

    private_key = serialization.load_pem_private_key(
        key_data["private_key"].encode(),
        password=None
    )

    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": key_data["service_account_id"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 360
    }

    headers = {"kid": key_data["id"]}
    encoded_jwt = jwt_encode(payload, private_key, algorithm="PS256", headers=headers)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"jwt": encoded_jwt}
        ) as resp:
            resp.raise_for_status()
            result = await resp.json()
            return result["iamToken"]

async def query_yandex_gpt(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": 20},
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": prompt}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(YANDEX_GPT_URL, headers=headers, json=data) as resp:
            result = await resp.json()
            try:
                text = result["result"]["alternatives"][0]["message"]["text"]
                return ''.join(filter(str.isdigit, text))
            except Exception:
                return "?"


async def get_or_create_user(user_obj) -> int:
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", user_obj.id)
        if user:
            return user["id"]
        return await conn.fetchval(
            "INSERT INTO users (telegram_id, username, first_name, last_name) VALUES ($1, $2, $3, $4) RETURNING id",
            user_obj.id,
            user_obj.username,
            user_obj.first_name,
            user_obj.last_name,
        )


async def log_calories(user_id: int, input_text: str, calories: int | None, message: Message):
    async with db_pool.acquire() as conn:
        try:
            # Проверяем количество записей за сегодня
            today_count = await conn.fetchval(
                "SELECT COUNT(*) FROM calories "
                "WHERE user_id = $1 AND created_at >= current_date",
                user_id
            )

            # Предупреждение при 35+ записях
            if 35 <= today_count < 40:
                warning = f"⚠️ Внимание: осталось {40 - today_count} из 40 записей на сегодня"
                await message.reply(warning)

            # Блокировка при достижении лимита
            if today_count >= 40:
                raise ValueError("❌ Достигнут дневной лимит в 40 записей")

            # Добавляем новую запись
            await conn.execute(
                "INSERT INTO calories (user_id, input, calories) "
                "VALUES ($1, $2, $3)",
                user_id, input_text, calories
            )

        except asyncpg.exceptions.CheckViolationError:
            raise ValueError("❌ Достигнут дневной лимит в 40 записей")




@dp.message(CommandStart())
async def handle_start(message: Message):
    user_id = await get_or_create_user(message.from_user)
    #await message.answer("Приветствую, человек! Я - бот, сверхразумное существо из другого мира. Напиши, сколько калорий было в этом приёме пищи — я сохраню данные в базу. Если не знаешь точное число, просто перечисли продукты или блюда, и я уточню калорийность с помощью нейросети, а потом добавлю в базу")
    await message.answer("Привет! Я бот помощник по питанию. Напиши, сколько калорий ты съел — я сохраню это. Не знаешь точно? Просто перечисли продукты, я сам посчитаю и добавлю в базу.")


@dp.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


@dp.message(Command("del"))
async def handle_delete_last_entry(message: Message):
    user_id = await get_or_create_user(message.from_user)

    async with db_pool.acquire() as conn:
        try:
            # Получаем и удаляем запись за один запрос, возвращая данные удалённой записи
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
                # Форматируем сообщение с информацией об удалённой записи
                entry_info = (
                    f"✅ Удалена запись:\n"
                    f"🍽 {deleted_entry['input']}\n"
                    f"🔥 {deleted_entry['calories'] or '?'} ккал\n"
                    f"⏰ {deleted_entry['created_at'].strftime('%d.%m.%Y %H:%M')}"
                )
                await message.reply(entry_info)
            else:
                await message.reply("ℹ️ У вас нет записей для удаления.")

        except Exception as e:
            await message.reply(f"⚠️ Ошибка при удалении: {str(e)}")
            print(f"Delete error for user {user_id}: {str(e)}")


@dp.message(Command("del_all"))
async def handle_delete_all_user_data(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить всё", callback_data="confirm_delete")
    builder.button(text="❌ Отмена", callback_data="cancel_delete")

    await message.reply(
        "⚠️ Вы уверены что хотите удалить ВСЕ ваши данные?\n"
        "Это действие нельзя отменить!",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(lambda c: c.data == "confirm_delete")
async def confirm_delete(callback: types.CallbackQuery):
    user_id = await get_or_create_user(callback.from_user)

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        await callback.message.edit_text("🗑️ Все ваши данные полностью удалены!")

@dp.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery):
    await callback.message.edit_text("✅ Удаление отменено")


@dp.message(Command("report"))
async def handle_daily_report(message: Message):
    user_id = await get_or_create_user(message.from_user)

    async with db_pool.acquire() as conn:
        try:
            # Получаем записи за сегодня (начиная с полуночи)
            today_entries = await conn.fetch(
                """SELECT input, calories, created_at
                FROM calories
                WHERE user_id = $1
                AND created_at >= current_date
                ORDER BY created_at""",
                user_id
            )

            if not today_entries:
                await message.reply("📊 Сегодня у вас пока нет записей.")
                return

            # Формируем красивый отчет
            report_lines = ["📅 <b>Отчет за сегодня</b> 📅\n"]
            total_calories = 0

            for entry in today_entries:
                time_str = entry['created_at'].strftime('%H:%M')
                calories = entry['calories'] or 0
                total_calories += calories

                report_lines.append(
                    f"⏰ {time_str} | 🍽 {entry['input']} | 🔥 {calories if entry['calories'] else '?'} ккал"
                )

            # Добавляем итоговую строку
            report_lines.append(f"\n<b>Итого за день:</b> 🔥 {total_calories} ккал")

            # Разбиваем сообщение на части, если оно слишком длинное
            report_text = "\n".join(report_lines)
            if len(report_text) > 4000:  # Ограничение Telegram на длину сообщения
                parts = [report_text[i:i+4000] for i in range(0, len(report_text), 4000)]
                for part in parts:
                    await message.answer(part, parse_mode="HTML")
                    await asyncio.sleep(0.5)  # Чтобы избежать флуда
            else:
                await message.answer(report_text, parse_mode="HTML")

        except Exception as e:
            await message.reply(f"⚠️ Ошибка при формировании отчета: {str(e)}")
            print(f"Report error for user {user_id}: {str(e)}")



@dp.message()
async def handle_text(message: Message):
    user_id = await get_or_create_user(message.from_user)
    input_text = message.text.strip()

    try:
        if input_text.isdigit():
            await log_calories(user_id, input_text, int(input_text), message)
            await message.reply(f"✅ Записано: {input_text} ккал")
        else:
            calories_str = await query_yandex_gpt(input_text)
            calories = int(calories_str) if calories_str.isdigit() else None
            await log_calories(user_id, input_text, calories, message)
            await message.reply(f"✅ Записано: {calories or '?'} ккал" +
                              (" (примерно)" if calories else ""))

    except ValueError as e:
        await message.reply(str(e))
    except Exception as e:
        await message.reply("🔧 Произошла техническая ошибка")
        print(f"Error for user {user_id}: {str(e)}")


async def main():
    global YANDEX_API_KEY
    await init_db()
    YANDEX_API_KEY = await get_iam_token_from_keyfile("key.json")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
