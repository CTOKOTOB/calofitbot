from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()

HELP_TEXT = """
🍏 <b>CaloFitBot - помощник по подсчёту калорий</b>

/start - Начало работы
/help - Показать эту справку
/report - Отчет за один или несколько дней (максимум 4, иначе отчет не поместится ответным сообщением)
/del - Удалить последнюю запись
/del_all - Удалить все данные

<b>Лимиты:</b> Не более 40 записей в день
"""

@router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "Привет! Я буду тебе помогать вести дневник питания. Просто напиши, сколько калорий съедено — я сохраню это."
        "Если не знаешь точно, укажи блюдо или продукт, я уточню у нейросети и запишу результат."
    )

@router.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")
