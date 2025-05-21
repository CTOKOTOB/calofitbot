import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

import json
import jwt
import time
import requests

# Текст справки
HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

Просто напишите название продукта или блюда, и бот ответит его калорийностью.

<b>Основные команды:</b>
/start - Начало работы
/help - Показать эту справку

<b>Как использовать:</b>
• Напишите "яблоко" - получите калорийность
• Или "порция спагетти" - калории на порцию
"""

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

# Инициализация бота aiogram
bot = Bot(token=os.environ["CALOFITBOT_TOKEN"])
dp = Dispatcher()

SYSTEM_PROMPT = "Ты помощник по питанию. Пользователь пишет название блюда или продукта, а ты отвечаешь только числом — сколько в нём примерно килокалорий. Никаких слов, только число. Если указывается готовая еда или блюдо, то стоит считать не за 100грамм, а за порцию."
async def query_yandex_gpt(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {YANDEX_API_KEY}",  # Исправлено на Bearer
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
                return "?"

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Привет! Напиши мне продукт или блюдо, а я скажу сколько в нём калорий")

# Добавляем новый обработчик для /help
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")

@dp.message()
async def handle_message(message: Message):
    user_input = message.text.strip()
    calories = await query_yandex_gpt(user_input)
    await message.reply(calories or "Не удалось определить калорийность.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())