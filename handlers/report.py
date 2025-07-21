from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from db.database import get_db_pool, get_or_create_user
import asyncio

router = Router()
user_selected_dates = {}
user_days_map = {}

MAX_BUTTONS = 16
MIN_BUTTONS = 4

@router.message(Command("report"))
async def report_command(message: Message):
    user_id = message.from_user.id
    today = datetime.now().date()

    db_pool = get_db_pool()
    async with db_pool.acquire() as conn:
        user_db_id = await get_or_create_user(message.from_user)
        rows = await conn.fetch(
            "SELECT DISTINCT DATE(created_at) as day FROM calories WHERE user_id = $1 ORDER BY day DESC",
            user_db_id
        )
        days_with_data = [r['day'] for r in rows]

    total_days = len(days_with_data)
    buttons_count = min(MAX_BUTTONS, max(MIN_BUTTONS, ((total_days + 3) // 4) * 4))
    all_days = [today - timedelta(days=i) for i in range(buttons_count)]

    user_selected_dates.pop(user_id, None)
    user_days_map.pop(user_id, None)

    user_selected_dates[user_id] = set()
    user_days_map[user_id] = all_days

    # Отправляем начальное сообщение с клавиатурой
    builder = build_date_keyboard(user_id, all_days)
    await message.answer("📆 Выберите одну или несколько дат:", reply_markup=builder.as_markup())

def build_date_keyboard(user_id: int, days: list[datetime.date]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    selected = user_selected_dates.get(user_id, set())

    for day in days:
        iso = day.isoformat()
        text = day.strftime("%d.%m")
        if iso in selected:
            text = f"✅ {text}"
        builder.button(text=text, callback_data=f"select_{iso}")

    builder.button(text="📥 Показать отчёт", callback_data="report_show")
    builder.adjust(4)
    return builder

@router.callback_query(lambda c: c.data and c.data.startswith("select_"))
async def date_select_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    date_iso = callback.data.split("_")[1]
    selected = user_selected_dates.setdefault(user_id, set())

    if date_iso in selected:
        selected.remove(date_iso)
    else:
        selected.add(date_iso)

    days = user_days_map.get(user_id)
    if not days:
        today = datetime.now().date()
        days = [today - timedelta(days=i) for i in range(MAX_BUTTONS)]

    builder = build_date_keyboard(user_id, days)
    await callback.message.edit_reply_markup(reply_markup=builder.as_markup())
    await callback.answer()

    if len(selected) == 4:
        await asyncio.sleep(0.1)
        await report_show(callback.message, user_id, sorted(selected))

@router.callback_query(lambda c: c.data == "report_show")
async def report_show_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    selected_dates = sorted(user_selected_dates.get(user_id, []))

    if not selected_dates:
        await callback.answer("Выберите хотя бы одну дату")
        return

    await report_show(callback.message, user_id, selected_dates)

async def report_show(original_msg_with_keyboard: Message, user_id: int, selected_dates: list[str]):
    db_pool = get_db_pool()
    final_report = []

    async with db_pool.acquire() as conn:
        row_user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", user_id)
        if not row_user:
            await original_msg_with_keyboard.answer("Пользователь не найден.")
            return
        user_db_id = row_user["id"]

        profile = await conn.fetchrow("""
            SELECT gender, age, height_cm, weight_kg
            FROM user_profiles
            WHERE user_id = $1
            ORDER BY recorded_at DESC
            LIMIT 1
        """, user_db_id)

        if not profile:
            await original_msg_with_keyboard.answer("Сначала введите данные с помощью команды /start.")
            return

        gender = profile["gender"]
        age = profile["age"]
        height = profile["height_cm"]
        weight = profile["weight_kg"]

        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        elif gender == "female":
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age

        for date_iso in selected_dates:
            try:
                date = datetime.fromisoformat(date_iso).date()
            except ValueError:
                continue

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
            lines.append(f"<i>Итого:</i> 🔥 {total} ккал")
            lines.append(f"<i>Норма:</i> 📊 ≈ {int(bmr)} ккал\n")
            final_report.append("\n".join(lines))

    await original_msg_with_keyboard.answer("\n\n".join(final_report), parse_mode="HTML")

    # Удаляем клавиатуру после отчёта
    try:
        await original_msg_with_keyboard.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    user_selected_dates.pop(user_id, None)
    user_days_map.pop(user_id, None)
