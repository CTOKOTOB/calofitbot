import sys
sys.path.append(".")

import asyncio
import os
from aiogram import Bot, Dispatcher

from handlers import report, start_help, delete, log_calories, yandex_gpt
from db.database import init_db

bot = Bot(token=os.environ["CALOFITBOT_TOKEN"])
dp = Dispatcher()

async def main():
    await init_db()

    dp.include_router(start_help.router)
    dp.include_router(report.router)
    dp.include_router(delete.router)
    dp.include_router(log_calories.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
