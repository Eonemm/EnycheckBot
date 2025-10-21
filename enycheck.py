import os
import json
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# === Конфігурація ===
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не заданий у середовищі Render!")

ADMINS = [955218726]

STUDENTS_FILE = "students.json"
SCHEDULE_FILE = "schedule.json"
BELLS_FILE = "bells.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Глобальні змінні ===
students = {}
schedule = {}
bells = {}
dp_state = {
    "awaiting_file_for": None,   # "all" або клас як рядок
    "awaiting_bells_file": False
}

# ======== Завантаження / збереження JSON ========
def load_json(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data():
    global students, schedule, bells
    students = load_json(STUDENTS_FILE)
    schedule = load_json(SCHEDULE_FILE)
    bells = load_json(BELLS_FILE)
    print(f"✅ Дані завантажено: {len(students)} учнів, {len(schedule)} класів, {len(bells)} дзвінків")

def save_data():
    save_json(STUDENTS_FILE, students)
    save_json(SCHEDULE_FILE, schedule)
    save_json(BELLS_FILE, bells)

# ======== Кнопки ========
def main_menu(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Розклад на сьогодні", callback_data="today_schedule")
    builder.button(text="🗓 Розклад на тиждень", callback_data="week_schedule")
    builder.button(text="⏰ Дзвінки", callback_data="bells_schedule")
    builder.button(text="⚙️ Змінити клас", callback_data="change_class")
    if user_id in ADMINS:
        builder.button(text="📃 Внести зміни в розклад", callback_data="upload_schedule")
        builder.button(text="🔔 Змінити розклад дзвінків", callback_data="update_bells")
    builder.adjust(1)  # всі кнопки в окремому рядку
    return builder.as_markup()

def class_buttons():
    builder = InlineKeyboardBuilder()
    for cls in range(5, 10):
        builder.button(text=f"{cls}", callback_data=f"class:{cls}")
    builder.adjust(1)
    return builder.as_markup()

# ======== Форматування розкладу ========
def format_schedule(cls: str, schedule_data: dict) -> str:
    text = f"📅 Розклад для {cls} класу:\n\n"
    for day, lessons in schedule_data.items():
        text += f"📌 {day}:\n"
        for i, lesson in enumerate(lessons, start=1):
            text += f"   {i}. {lesson}\n"
        text += "───────────────────────\n"
    return text

def format_today_schedule(cls: str, day: str, lessons: list) -> str:
    header = f"📅 Розклад для {cls} класу на {day}:\n"
    if not lessons:
        return header + "Сьогодні занять немає.\n"

    sorted_bells = sorted(bells.items(), key=lambda kv: int(kv[0])) if bells else []
    lines = [header]
    for idx, lesson in enumerate(lessons, start=1):
        if idx <= len(sorted_bells):
            timestr = sorted_bells[idx - 1][1]
            if "-" in timestr:
                start, end = [p.strip() for p in timestr.split("-")]
            else:
                start, end = timestr.strip(), ""
            time_row = f"─── <code>{start}</code> ──────── <code>{end}</code> ───" if end else f"─── <code>{start}</code> ───"
        else:
            time_row = "─── — ───"
        lines.append(time_row)
        lines.append(f"{idx}. <b>{lesson}</b>")
    lines.append("────────────────────────")
    return "\n".join(lines)

def format_bells() -> str:
    if not bells:
        return "⏰ Розклад дзвінків ще не завантажено."
    text = "⏰ Розклад дзвінків:\n\n"
    for number, timestr in sorted(bells.items(), key=lambda kv: int(kv[0])):
        text += f"{number}. {timestr}\n"
    return text

# ======== /start ========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    if message.from_user.id in ADMINS:
        await message.answer(
            f"<code>Вітаю, адміністраторе - {message.from_user.full_name}!</code>",
            reply_markup=main_menu(message.from_user.id),
            parse_mode="HTML"
        )
        return
    if user_id in students:
        cls = students[user_id]["class"]
        await message.answer(f"Вітаю знову! Твій клас: {cls}", reply_markup=main_menu(message.from_user.id))
    else:
        await message.answer("Привіт! Оберіть свій клас:", reply_markup=class_buttons())

# ======== Вибір класу ========
@dp.callback_query(lambda c: c.data and c.data.startswith("class:"))
async def class_choice(callback: types.CallbackQuery):
    cls = callback.data.split(":")[1]
    user_id = str(callback.from_user.id)
    students[user_id] = {"id": callback.from_user.id, "name": callback.from_user.full_name, "class": cls}
    save_data()
    await callback.message.edit_text(f"✅ Твій клас встановлено: {cls}", reply_markup=main_menu(callback.from_user.id))

# ======== Webserver для Render ========
async def handle(request):
    return web.Response(text="OK - Bot is running!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Webserver running on port {port}")

# ======== Головна функція ========
async def main():
    load_data()
    # одночасно вебсервер і polling
    await asyncio.gather(
        dp.start_polling(bot),
        start_webserver()
    )

if __name__ == "__main__":
    asyncio.run(main())
