import os
import json
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === Конфігурація ===
TOKEN = "8308954991:AAHHxvfa7MNIenH9L3xPG4jE7D9k9k2n0QA"
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

def load_bells():
    global bells
    bells = load_json(BELLS_FILE)

def save_bells():
    save_json(BELLS_FILE, bells)

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
    builder.adjust(1, 1, 2, 1, 1)  # кожна кнопка в окремому рядку
    return builder.as_markup()

def class_buttons():
    builder = InlineKeyboardBuilder()
    for cls in range(5, 10):
        builder.button(text=f"{cls}", callback_data=f"class:{cls}")
    builder.adjust(1)
    return builder.as_markup()

# ======== Форматування розкладу (тиждень) ========
def format_schedule(cls: str, schedule_data: dict) -> str:
    text = f"📅 Розклад для {cls} класу:\n\n"
    for day, lessons in schedule_data.items():
        text += f"📌 {day}:\n"
        for i, lesson in enumerate(lessons, start=1):
            text += f"   {i}. {lesson}\n"
        text += "───────────────────────\n"
    return f"{text}"

# ======== НОВИЙ ВІЗУАЛ: формат для сьогоднішнього розкладу з годинами дзвінків ========
def format_today_schedule(cls: str, day: str, lessons: list) -> str:
    
    header = f"📅 Розклад для {cls} класу на {day}:\n"
    if not lessons:
        return header + "Сьогодні занять немає.\n"

    # Підготувати відсортований список дзвінків ([(num, "08:55 - 09:35"), ...])
    sorted_bells = sorted(bells.items(), key=lambda kv: int(kv[0])) if bells else []

    lines = [header]
    for idx, lesson in enumerate(lessons, start=1):
        # Отримати відповідний час дзвінка
        if idx <= len(sorted_bells):
            timestr = sorted_bells[idx - 1][1]  # наприклад "08:55 - 09:35"
            # Спробуємо розділити на початок/кінець по дефісу
            if "-" in timestr:
                parts = timestr.split("-")
                start = parts[0].strip()
                end = parts[1].strip()
            else:
                # Якщо формат інший — показати цілий рядок як "start - end"
                start = timestr.strip()
                end = ""
            # Формуємо декоративний рядок з часом
            if end:
                time_row = f"─── <code>{start}</code> ──────── <code>{end}</code> ───"
            else:
                time_row = f"─── <code>{start}</code> ───"
        else:
            time_row = "─── — ───"

	
        lines.append(time_row)
        lines.append(f"{idx}. <b>{lesson}</b>")


    lines.append("────────────────────────")
    # Об'єднати в текст
    return "\n".join(lines)



# ======== Формат дзвінків (як було) ========
def format_bells() -> str:
    if not bells:
        return "⏰ Розклад дзвінків ще не завантажено."
    text = "⏰ Розклад дзвінків:\n\n"
    # сортуємо за номером (ключі зберігаємо як рядки)
    for number, timestr in sorted(bells.items(), key=lambda kv: int(kv[0])):
        text += f"{number}. {timestr}\n"
    return text

# ======== Відправка/редагування розкладу ========
async def send_schedule(user_id: int, cls: str, message: types.Message = None):
    if cls not in schedule:
        if message:
            await message.edit_text("Розклад для твого класу ще не завантажений.", reply_markup=main_menu(int(user_id)))
        else:
            await bot.send_message(user_id, "Розклад для твого класу ще не завантажений.", reply_markup=main_menu(int(user_id)))
        return
    text = format_schedule(cls, schedule[cls])
    if message:
        await message.edit_text(text, reply_markup=main_menu(int(user_id)))
    else:
        await bot.send_message(user_id, text, reply_markup=main_menu(int(user_id)))

# ======== /start ========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)

    # Якщо користувач — адміністратор
    if message.from_user.id in ADMINS:
        await message.answer(
            f"<code>Вітаю, адміністраторе - {message.from_user.full_name}!</code>",
            reply_markup=main_menu(message.from_user.id),
            parse_mode="HTML"
        )
        return

    # Для звичайних користувачів
    if user_id in students:
        cls = students[user_id]["class"]
        await message.answer(
            f"Вітаю знову! Твій клас: {cls}",
            reply_markup=main_menu(message.from_user.id)
        )
    else:
        await message.answer(
            "Привіт! Оберіть свій клас:",
            reply_markup=class_buttons()
        )

# ======== Вибір класу ========
@dp.callback_query(lambda c: c.data and c.data.startswith("class:"))
async def class_choice(callback: types.CallbackQuery):
    cls = callback.data.split(":")[1]
    user_id = str(callback.from_user.id)
    students[user_id] = {
        "id": callback.from_user.id,
        "name": callback.from_user.full_name,
        "class": cls
    }
    save_data()
    await callback.message.edit_text(f"✅ Твій клас встановлено: {cls}", reply_markup=main_menu(callback.from_user.id))

# ======== Змінити клас ========
@dp.callback_query(lambda c: c.data == "change_class")
async def change_class(callback: types.CallbackQuery):
    await callback.message.edit_text("Оберіть новий клас:", reply_markup=class_buttons())

# ======== Розклад на сьогодні ========
@dp.callback_query(lambda c: c.data == "today_schedule")
async def today_schedule(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id not in students and callback.from_user.id not in ADMINS:
        await callback.message.answer("Спочатку оберіть свій клас через /start")
        return

    cls = students[user_id]["class"] if user_id in students else None
    weekdays = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    today = weekdays[datetime.today().weekday()]

    if cls:
        if cls not in schedule:
            await callback.message.edit_text("Розклад для вашого класу ще не завантажено.", reply_markup=main_menu(callback.from_user.id))
            return
        if today not in schedule[cls]:
            await callback.message.edit_text(f"Сьогодні ({today}) занять немає або розклад не завантажений.", reply_markup=main_menu(callback.from_user.id))
            return
        lessons = schedule[cls][today]
        # Використовуємо новий візуал
        text = format_today_schedule(cls, today, lessons)
    else:
        text = "Адміністраторський перегляд: оберіть клас або перегляньте тиждень."
    await callback.message.edit_text(text, reply_markup=main_menu(callback.from_user.id), parse_mode="HTML")

# ======== Розклад на тиждень ========
@dp.callback_query(lambda c: c.data == "week_schedule")
async def week_schedule(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if user_id not in students and callback.from_user.id not in ADMINS:
        await callback.message.answer("Спочатку оберіть свій клас через /start")
        return

    cls = students[user_id]["class"] if user_id in students else None
    if cls:
        if cls not in schedule:
            await callback.message.edit_text("Розклад для вашого класу ще не завантажено.", reply_markup=main_menu(callback.from_user.id))
            return
        text = format_schedule(cls, schedule[cls])
    else:
        text = "Адміністраторський перегляд: оберіть клас, щоб побачити розклад."
    await callback.message.edit_text(text, reply_markup=main_menu(callback.from_user.id))

# ======== Розклад дзвінків ========
@dp.callback_query(lambda c: c.data == "bells_schedule")
async def bells_schedule_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(format_bells(), reply_markup=main_menu(callback.from_user.id))

# ======== Оновити розклад дзвінків (адмін) ========
@dp.callback_query(lambda c: c.data == "update_bells")
async def update_bells_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return
    await callback.message.edit_text(
        "📤 Надішліть файл з новим розкладом дзвінків у форматі .txt (рядок: номер;час)\n\nПриклад: 1;08:55 - 09:40",
        reply_markup=None
    )
    dp_state["awaiting_bells_file"] = True
    await callback.answer()

# ======== Кнопки оновлення розкладу (всі / клас) ========
def update_schedule_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛠 Оновити для всіх", callback_data="update_all")
    for cls in range(5, 10):
        builder.button(text=f"{cls}", callback_data=f"update_class:{cls}")
    builder.adjust(1)  # кожна кнопка в окремому рядку
    return builder.as_markup()

@dp.callback_query(lambda c: c.data == "upload_schedule")
async def upload_schedule_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMINS:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return
    await callback.message.edit_text("📤 Оберіть, як оновити розклад:", reply_markup=update_schedule_menu())

@dp.callback_query(lambda c: c.data == "update_all")
async def update_all_schedule(callback: types.CallbackQuery):
    await callback.message.edit_text("📤 Надішліть файл з розкладом у форматі .txt для оновлення всім.", reply_markup=None)
    dp_state["awaiting_file_for"] = "all"

@dp.callback_query(lambda c: c.data and c.data.startswith("update_class:"))
async def update_class_schedule(callback: types.CallbackQuery):
    cls = callback.data.split(":")[1]
    await callback.message.edit_text(f"📤 Надішліть файл з розкладом для {cls} класу у форматі .txt", reply_markup=None)
    dp_state["awaiting_file_for"] = cls

# ======== Обробка документів ========
@dp.message(lambda m: m.document)
async def handle_document(message: types.Message):
    # тільки адмін може відправляти файли для оновлення
    if message.from_user.id not in ADMINS:
        return

    if not message.document.file_name.endswith(".txt"):
        await message.answer("❌ Надішліть файл у форматі .txt")
        return

    file_info = await bot.get_file(message.document.file_id)
    file_path = "schedule_uploaded.txt"
    await bot.download_file(file_info.file_path, destination=file_path)

    # Якщо очікуємо файл дзвінків
    if dp_state.get("awaiting_bells_file"):
        new_bells = {}
        errors = []
        with open(file_path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(";")
                if len(parts) != 2:
                    errors.append(f"Рядок {lineno}: невірний формат 1;08:55 - 09:35")
                    continue
                number, timestr = parts[0].strip(), parts[1].strip()
                if not number.isdigit():
                    errors.append(f"рядок {lineno}: номер має бути числом")
                    continue
                new_bells[number] = timestr

        if errors:
            await message.answer("❌ Помилки при парсингу дзвінків:\n" + "\n".join(errors))
            dp_state["awaiting_bells_file"] = False
            return

        # Оновлюємо bells і зберігаємо
        bells.update(new_bells)
        save_bells()
        dp_state["awaiting_bells_file"] = False
        await message.answer("✅ Розклад дзвінків оновлено.", reply_markup=main_menu(message.from_user.id))
        return

    # ====== Інакше — це файл з розкладом (всі / клас) ======
    awaiting = dp_state.get("awaiting_file_for")
    if not awaiting:
        await message.answer("❌ Немає інформації, що цей файл очікувався.")
        return

    new_schedule = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) != 3:
                continue
            cls_file, day, lessons = parts
            lessons_list = [l.strip() for l in lessons.split(",") if l.strip()]
            if cls_file not in new_schedule:
                new_schedule[cls_file] = {}
            new_schedule[cls_file][day] = lessons_list

    if awaiting == "all":
        schedule.update(new_schedule)
    else:
        if awaiting in new_schedule:
            schedule[awaiting] = new_schedule[awaiting]

    save_data()
    await message.answer("✅ Розклад оновлено у базі даних.")

    # Відправка повідомлень тільки тим, кого стосується оновлення
    sent_count = 0
    for user_id, info in students.items():
        user_class = info.get("class")
        if awaiting == "all" or user_class == awaiting:
            try:
                await bot.send_message(
                    int(user_id),
                    "‼️🔔 Для вас оновлено розклад, перегляньте його!",
                    reply_markup=main_menu(int(user_id))
                )
                sent_count += 1
            except:
                pass

    await message.answer(f"📢 Повідомлення про оновлення розкладів надіслано {sent_count} учням.", reply_markup=main_menu(message.from_user.id))
    dp_state["awaiting_file_for"] = None

# ======== Запуск ========
async def main():
    load_data()
    await dp.start_polling(bot)

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8000"))

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - bot is running")

    def log_message(self, format, *args):
        return

def _run_http():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    try:
        server.serve_forever()
    except Exception:
        pass

threading.Thread(target=_run_http, daemon=True).start()


if __name__ == "__main__":
    asyncio.run(main())

