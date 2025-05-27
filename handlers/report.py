from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from db.database import get_db_pool, get_or_create_user

router = Router()
user_selected_dates = {}

@router.message(Command("report"))
async def report_command(message: Message):
    user_id = message.from_user.id
    db_pool = get_db_pool()

    async with db_pool.acquire() as conn:
        user_db_id = await get_or_create_user(message.from_user)
        rows = await conn.fetch(
            "SELECT DISTINCT DATE(created_at) as date FROM calories WHERE user_id = $1 ORDER BY date DESC",
            user_db_id
        )
        all_days = [row["date"] for row in rows]

    # Гарантированно минимум 4 дня
    if len(all_days) < 4:
        today = datetime.now().date()
        all_days = [today - timedelta(days=i) for i in range(4)]

    # Ограничим максимумом в 16
    days = all_days[:16]

    user_selected_dates[user_id] = set()
    await send_date_selection(message, user_id, days)

async def send_date_selection(message_or_callback, user_id, _ignored_days=None):
    today = datetime.now().date()
    days = [today - timedelta(days=i) for i in range(16)]  # всегда 16 последних дней

    builder = InlineKeyboardBuilder()
    selected = user_selected_dates.get(user_id, set())

    for day in days:
        iso = day.isoformat()
        text = day.strftime("%d.%m")
        if iso in selected:
            text = f"✅ {text}"
        builder.button(text=text, callback_data=f"select_{iso}")

    builder.adjust(4, 4, 4, 4)  # 4 ряда по 4 кнопки
    builder.row(types.InlineKeyboardButton(text="📥 Показать отчёт", callback_data="report_show"))

    await message_or_callback.answer(
        "📆 Выберите одну или несколько (максимум 4) дат:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("select_"))
async def date_select_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    date_iso = callback.data.split("_")[1]
    selected = user_selected_dates.setdefault(user_id, set())

    if date_iso in selected:
        selected.remove(date_iso)
    else:
        selected.add(date_iso)

    if len(selected) == 4:
        await report_show_callback(callback, auto_trigger=True)
    else:
        await update_date_selection(callback, user_id)

async def update_date_selection(callback: CallbackQuery, user_id: int):
    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        user_db_id = await get_or_create_user(callback.from_user)
        rows = await conn.fetch(
            "SELECT DISTINCT DATE(created_at) as date FROM calories WHERE user_id = $1 ORDER BY date DESC",
            user_db_id
        )
        all_days = [row["date"] for row in rows]

    if len(all_days) < 4:
        today = datetime.now().date()
        all_days = [today - timedelta(days=i) for i in range(4)]

    days = all_days[:16]
    await send_date_selection(callback.message, user_id, days)
    await callback.answer()

@router.callback_query(lambda c: c.data == "report_show")
async def report_show_callback(callback: CallbackQuery, auto_trigger: bool = False):
    user_id = callback.from_user.id
    selected_dates = sorted(user_selected_dates.get(user_id, []))

    if not selected_dates:
        await callback.answer("Выберите хотя бы одну дату")
        return

    db_pool = get_db_pool()
    final_report = []

    async with db_pool.acquire() as conn:
        user_db_id = await get_or_create_user(callback.from_user)

        for date_iso in selected_dates:
            date = datetime.fromisoformat(date_iso).date()
            rows = await conn.fetch(
                """
                SELECT input, calories, created_at
                FROM calories
                WHERE user_id = $1
                AND created_at >= $2
                AND created_at < $3
                ORDER BY created_at
                """,
                user_db_id, date, date + timedelta(days=1)
            )

            if not rows:
                final_report.append(f"📅 <b>{date.strftime('%d.%m.%Y')}</b>: записей нет.")
                continue

            total = 0
            lines = [f"📅 <b>{date.strftime('%d.%m.%Y')}</b>"]
            for r in rows:
                time_str = r['created_at'].strftime("%H:%M")
                cal = r['calories'] if r['calories'] is not None else '?'
                total += r['calories'] or 0
                lines.append(f"⏰ {time_str} | 🍽 {r['input']} | 🔥 {cal} ккал")
            lines.append(f"<i>Итого:</i> 🔥 {total} ккал\n")
            final_report.append("\n".join(lines))

    await callback.message.answer("\n\n".join(final_report), parse_mode="HTML")
    user_selected_dates.pop(user_id, None)
    if not auto_trigger:
        await callback.answer()
