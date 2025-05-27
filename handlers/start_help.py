from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

/start - Начало работы
/help - Показать эту справку
/report - Отчет за один или несколько дней
/del - Удалить последнюю запись
/del_all - Удалить все данные

<b>Лимиты:</b> Не более 40 записей в день
"""

@router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "Привет! Я бот помощник по питанию. "
        "Напиши, сколько калорий ты съел — я сохраню это. "
        "Если не знаешь точно, просто перечисли продукты, я посчитаю."
    )

@router.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")
