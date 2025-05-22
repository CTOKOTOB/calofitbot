import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
import json
import jwt
import time
import requests
from datetime import date

# Текст справки
HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

Просто напишите название продукта или блюда, и бот ответит его калорийностью.

<b>Основные команды:</b>
/start - Начало работы
/help - Показать эту справку
/set_weight - Обновить свой вес
/my_stats - Показать мою статистику

<b>Как использовать:</b>
• Напишите "яблоко" - получите калорийность
• Или "порция спагетти" - калории на порцию
• Или просто число - будет записано как калории
"""

# Конфигурация базы данных
DB_CONFIG = {
    "dbname": "calorie_tracker",
    "user": "calorie_bot",
    "password": "calorie_bot",
    "host": "localhost",
    "port": "5432"
}


class Database:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.conn.autocommit = False  # Отключаем авто-коммит для лучшего контроля

    async def get_user(self, telegram_id):
        with self.conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            return cursor.fetchone()

    async def create_user(self, telegram_id, username, first_name, last_name):
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO users (telegram_id, username, first_name, last_name, registration_date) "
                    "VALUES (%s, %s, %s, %s, NOW()) RETURNING user_id",
                    (telegram_id, username, first_name, last_name)
                )
                user_id = cursor.fetchone()[0]
                self.conn.commit()
                return user_id
            except Exception as e:
                self.conn.rollback()
                print(f"Error creating user: {e}")
                raise

    async def update_user_profile(self, user_id, gender, height, birth_date):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET gender = %s, height = %s, birth_date = %s WHERE user_id = %s",
                (gender, height, birth_date, user_id)
            )
            self.conn.commit()

    async def add_weight_record(self, user_id, weight):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO user_weight (user_id, weight, record_date) "
                "VALUES (%s, %s, CURRENT_DATE)",
                (user_id, weight)
            )
            self.conn.commit()

    async def add_calorie_record(self, user_id, food_name, calories):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO calorie_intake (user_id, food_name, calories, entry_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE)",
                (user_id, food_name, calories)
            )
            self.conn.commit()

    async def close(self):
        if self.conn:
            self.conn.close()


db = Database()


def get_iam_token_from_keyfile(path_to_keyfile: str) -> str:
    with open(path_to_keyfile, 'r') as f:
        key_data = json.load(f)

    service_account_id = key_data['service_account_id']
    key_id = key_data['id']
    private_key = key_data['private_key']

    now = int(time.time())
    payload = {
        'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        'iss': service_account_id,
        'iat': now,
        'exp': now + 360,
    }

    encoded_jwt = jwt.encode(payload, private_key, algorithm='PS256', headers={'kid': key_id})

    response = requests.post(
        'https://iam.api.cloud.yandex.net/iam/v1/tokens',
        json={'jwt': encoded_jwt}
    )

    response.raise_for_status()
    return response.json()['iamToken']


YANDEX_API_KEY = get_iam_token_from_keyfile("key.json")
FOLDER_ID = "b1gjo1fm56glmpd0hs5r"
YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

bot = Bot(token=os.environ["CALOFITBOT_TOKEN"])
dp = Dispatcher()

SYSTEM_PROMPT = "Ты помощник по питанию. Пользователь пишет название блюда или продукта, а ты отвечаешь только числом — сколько в нём примерно килокалорий. Никаких слов, только число. Если указывается готовая еда или блюдо, то стоит считать не за 100грамм, а за порцию."


async def query_yandex_gpt(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.3,
            "maxTokens": 20
        },
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": prompt}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(YANDEX_GPT_URL, headers=headers, json=data) as resp:
            result = await resp.json()
            try:
                answer = result["result"]["alternatives"][0]["message"]["text"]
                return ''.join(filter(str.isdigit, answer))
            except Exception as e:
                print("Ошибка при парсинге ответа:", result)
                return None


@dp.message(CommandStart())
async def start(message: Message):
    await db.connect()
    user = await db.get_user(message.from_user.id)

    if not user:
        # Создаем нового пользователя
        user_id = await db.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        # Запрашиваем дополнительные данные
        await message.answer(
            "Привет! Давай заполним твой профиль.\n"
            "Укажи свой пол (М/Ж):"
        )
        # Здесь можно добавить машину состояний для сбора данных
    else:
        await message.answer(
            "С возвращением! Ты можешь:\n"
            "- Ввести название продукта для определения калорий\n"
            "- Ввести просто число, чтобы записать калории\n"
            "- Использовать /set_weight для обновления веса"
        )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode=ParseMode.HTML)


@dp.message(Command("set_weight"))
async def set_weight_command(message: types.Message):
    await message.answer("Введите ваш текущий вес в кг (например: 68.5):")


@dp.message(F.text.regexp(r'^\d+([.,]\d+)?$').as_("weight"))
async def handle_weight_input(message: Message, weight: str):
    weight = float(weight.replace(',', '.'))
    user = await db.get_user(message.from_user.id)

    if user:
        await db.add_weight_record(user['user_id'], weight)
        await message.answer(f"✅ Вес {weight} кг успешно сохранён!")
    else:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")


@dp.message()
async def handle_message(message: Message):
    user_input = message.text.strip()
    user = await db.get_user(message.from_user.id)

    if not user:
        await message.answer("Пожалуйста, сначала зарегистрируйтесь с помощью /start")
        return

    # Если ввод - просто число, записываем как калории
    if user_input.replace('.', '').isdigit():
        calories = float(user_input)
        await db.add_calorie_record(user['user_id'], "Ручной ввод", calories)
        await message.answer(f"✅ Принято, записано {calories} ккал")
        return

    # Если это не число, спрашиваем у нейросети
    calories = await query_yandex_gpt(user_input)

    if calories:
        await db.add_calorie_record(user['user_id'], user_input, float(calories))
        await message.answer(f"✅ Принято, записано {calories} ккал за '{user_input}'")
    else:
        await message.reply("Не удалось определить калорийность. Попробуйте уточнить запрос.")


async def main():
    await db.connect()
    await dp.start_polling(bot)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())