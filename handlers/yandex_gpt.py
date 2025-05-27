import aiohttp
import os
import time
import json
from cryptography.hazmat.primitives import serialization
from jwt import encode as jwt_encode

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ..\calofitbot
KEY_FILE_PATH = os.path.join(BASE_DIR, "key.json")

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
FOLDER_ID = "b1gjo1fm56glmpd0hs5r"
SYSTEM_PROMPT = (
    "Ты помощник по питанию. Пользователь пишет название блюда или продукта, а ты отвечаешь только числом — сколько в нём примерно килокалорий. Никаких слов, только число. Если указывается готовая еда или блюдо то стоит считать не за 100грамм, а за порцию.")

YANDEX_API_KEY = None

async def get_iam_token_from_keyfile(path_to_keyfile: str) -> str:
    try:
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
    except Exception as e:
        print(f"Ошибка при загрузке ключа или получении IAM токена: {e}")
        raise

async def query_yandex_gpt(prompt: str) -> str:
    global YANDEX_API_KEY
    if YANDEX_API_KEY is None:
        YANDEX_API_KEY = await get_iam_token_from_keyfile(KEY_FILE_PATH)

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
            print(f"Yandex GPT raw response: {result}")  # Лог для отладки
            try:
                return result["result"]["alternatives"][0]["message"]["text"].strip()
            except Exception as e:
                print(f"Ошибка при разборе ответа: {e}")
                return "0"

