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

HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

Просто напишите название продукта или блюда, и бот ответит его калорийностью.

/start - Начало работы
/help - Показать эту справку
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


async def log_calories(user_id: int, input_text: str, calories: int | None):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO calories (user_id, input, calories) VALUES ($1, $2, $3)",
            user_id, input_text, calories
        )

@dp.message(CommandStart())
async def handle_start(message: Message):
    user_id = await get_or_create_user(message.from_user)
    await message.answer("Привет! Напиши продукт или блюдо, а я скажу сколько в нём калорий.")

@dp.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")

@dp.message()
async def handle_text(message: Message):
    user_id = await get_or_create_user(message.from_user)
    input_text = message.text.strip()

    if input_text.isdigit():
        await log_calories(user_id, input_text, int(input_text))
        await message.reply(f"Записано: {input_text} ккал.")
    else:
        calories_str = await query_yandex_gpt(input_text)
        calories = int(calories_str) if calories_str.isdigit() else None
        await log_calories(user_id, input_text, calories)
        if calories:
            await message.reply(f"Записал {calories} ккал.")
        else:
            await message.reply("Не удалось определить калорийность.")

async def main():
    global YANDEX_API_KEY
    await init_db()
    YANDEX_API_KEY = await get_iam_token_from_keyfile("key.json")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
