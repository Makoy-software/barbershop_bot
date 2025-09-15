import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# 🔧 ЛОГИ
logging.basicConfig(level=logging.INFO)

# 🔑 ТОКЕН
BOT_TOKEN = "8356380714:AAERAYN3br9ZuKr6hSLvvckG77KEYUi3PFk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# 📊 GOOGLE SHEETS НАСТРОЙКА
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Запись клиентов").sheet1

# 📌 ТВОЙ TELEGRAM ID (для уведомлений)
MASTER_CHAT_ID = 696860302

# 📆 РАСПИСАНИЕ МАСТЕРОВ
MASTER_SCHEDULE = {
    "Алексей": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "Иван": ["Tue", "Thu", "Sat"],
    "Дмитрий": ["Mon", "Wed", "Fri", "Sun"],
    "Любой": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

# 🌍 Словари
MESSAGES = {
    "ru": {
        "start": "Привет! 👋 Я бот барбершопа.\nВыберите язык:",
        "menu": "Хочешь записаться на стрижку?",
        "order": "✂ Записаться",
        "ask_name": "Введите ваше полное имя:",
        "ask_service": "Выберите услугу:",
        "ask_master": "К какому мастеру хотите записаться?",
        "ask_phone": "Отправьте свой номер телефона:",
        "ask_date": "Введите дату записи (например: 10.09.2025):",
        "wrong_date": "❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ.",
        "master_dayoff": "❌ Мастер {master} не работает в этот день. Выберите другую дату или мастера.",
        "ask_time": "Введите желаемое время записи (например: 15:00):",
        "master_busy": "❌ В это время мастер {master} занят. Выберите другое время или мастера.",
        "success": "✅ Ваша заявка принята! Скоро мастер свяжется с вами.",
    },
    "uz": {
        "start": "Salom! 👋 Men barbershop botman.\nTilni tanlang:",
        "menu": "Soch oldirishni xohlaysizmi?",
        "order": "✂ Ro'yxatdan o'tish",
        "ask_name": "To‘liq ismingizni kiriting:",
        "ask_service": "Xizmat turini tanlang:",
        "ask_master": "Qaysi ustaga yozilmoqchisiz?",
        "ask_phone": "Telefon raqamingizni yuboring:",
        "ask_date": "Sanani kiriting (masalan: 10.09.2025):",
        "wrong_date": "❌ Noto‘g‘ri sana formati. DD.MM.YYYY formatida kiriting.",
        "master_dayoff": "❌ {master} bu kuni ishlamaydi. Boshqa sana yoki usta tanlang.",
        "ask_time": "Kerakli vaqtni kiriting (masalan: 15:00):",
        "master_busy": "❌ Bu vaqtda {master} band. Boshqa vaqt yoki usta tanlang.",
        "success": "✅ So‘rovingiz qabul qilindi! Tez orada usta siz bilan bog‘lanadi.",
    }
}

# 🌍 Имена мастеров
MASTER_NAMES = {
    "ru": ["Алексей", "Иван", "Дмитрий", "Любой"],
    "uz": ["Aleksey", "Ivan", "Dmitriy", "Istalgan"]
}

# 🔄 Маппинг узбекских имён → русских (для логики и Google Sheets)
UZ_TO_RU_MASTER = {
    "Aleksey": "Алексей",
    "Ivan": "Иван",
    "Dmitriy": "Дмитрий",
    "Istalgan": "Любой"
}


# 📌 Состояния
class OrderForm(StatesGroup):
    lang = State()
    name = State()
    service = State()
    master = State()
    phone = State()
    date = State()
    time = State()


# 📌 Функция сохранения заявки в Google Sheets
def save_to_sheets(data: dict):
    row = [
        data["name"],
        data["service"],
        data["master"],
        data["phone"],
        data["date"],
        data["time"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]
    sheet.append_row(row)


# 📌 Проверка занятости мастера
def is_master_busy(master: str, date: str, time: str) -> bool:
    records = sheet.get_all_records()
    for r in records:
        if r["Мастер"] == master and r["Дата"] == date and r["Время"] == time:
            return True
    return False


# 📍 /clear — очистка заявок за вчера
@dp.message_handler(commands=["clear"])
async def clear_yesterday(message: types.Message):
    if message.chat.id != MASTER_CHAT_ID:
        return

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
    records = sheet.get_all_records()
    rows_to_delete = []

    for i, r in enumerate(records, start=2):  # start=2 т.к. первая строка — заголовки
        if r["Дата"] == yesterday:
            rows_to_delete.append(i)

    for row in reversed(rows_to_delete):  # удаляем с конца
        sheet.delete_rows(row)

    await message.answer(f"🧹 Заявки за {yesterday} удалены! ({len(rows_to_delete)} шт.)")


# 📍 /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇺🇿 O‘zbek")
    await message.answer("Выберите язык / Tilni tanlang:", reply_markup=kb)
    await OrderForm.lang.set()


# 📍 выбор языка
@dp.message_handler(state=OrderForm.lang)
async def choose_lang(message: types.Message, state: FSMContext):
    if "O‘zbek" in message.text:
        lang = "uz"
    else:
        lang = "ru"
    await state.update_data(lang=lang)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add(MESSAGES[lang]["order"])
    await message.answer(MESSAGES[lang]["menu"], reply_markup=kb)
    await state.finish()


# 📍 запуск заявки
@dp.message_handler(lambda m: m.text in ["✂ Записаться", "✂ Ro'yxatdan o'tish"])
async def order_start(message: types.Message, state: FSMContext):
    lang = "uz" if "Ro'yxatdan" in message.text else "ru"
    await state.update_data(lang=lang)

    await message.answer(MESSAGES[lang]["ask_name"])
    await OrderForm.name.set()


# 📍 имя
@dp.message_handler(state=OrderForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    data = await state.get_data()
    lang = data["lang"]

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Стрижка" if lang == "ru" else "Soch olish",
           "Борода" if lang == "ru" else "Soqol",
           "Комплекс" if lang == "ru" else "Kompleks")
    await message.answer(MESSAGES[lang]["ask_service"], reply_markup=kb)
    await OrderForm.service.set()


# 📍 услуга
@dp.message_handler(state=OrderForm.service)
async def process_service(message: types.Message, state: FSMContext):
    await state.update_data(service=message.text)
    data = await state.get_data()
    lang = data["lang"]

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(*MASTER_NAMES[lang])
    await message.answer(MESSAGES[lang]["ask_master"], reply_markup=kb)
    await OrderForm.master.set()


# 📍 мастер
@dp.message_handler(state=OrderForm.master)
async def process_master(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]
    master = message.text

    if lang == "uz" and master in UZ_TO_RU_MASTER:
        master = UZ_TO_RU_MASTER[master]

    await state.update_data(master=master)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add(
        types.KeyboardButton("📱 Отправить номер" if lang == "ru" else "📱 Raqam yuborish", request_contact=True)
    )
    await message.answer(MESSAGES[lang]["ask_phone"], reply_markup=kb)
    await OrderForm.phone.set()


# 📍 телефон
@dp.message_handler(content_types=["contact", "text"], state=OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone)
    data = await state.get_data()
    lang = data["lang"]

    await message.answer(MESSAGES[lang]["ask_date"])
    await OrderForm.date.set()


# 📍 дата
@dp.message_handler(state=OrderForm.date)
async def process_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data["lang"]

    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        weekday = date_obj.strftime("%a")
        master = data.get("master")

        if master in MASTER_SCHEDULE and weekday not in MASTER_SCHEDULE[master]:
            await message.answer(
                MESSAGES[lang]["master_dayoff"].format(master=master),
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(MESSAGES[lang]["order"])
            )
            await state.finish()
            return

        await state.update_data(date=message.text)
        await message.answer(MESSAGES[lang]["ask_time"])
        await OrderForm.time.set()

    except ValueError:
        await message.answer(MESSAGES[lang]["wrong_date"])


# 📍 время
@dp.message_handler(state=OrderForm.time)
async def process_time(message: types.Message, state: FSMContext):
    await state.update_data(time=message.text)
    data = await state.get_data()
    lang = data["lang"]

    if data["master"] != "Любой" and is_master_busy(data["master"], data["date"], data["time"]):
        await message.answer(
            MESSAGES[lang]["master_busy"].format(master=data["master"]),
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(MESSAGES[lang]["order"])
        )
        await state.finish()
        return

    save_to_sheets(data)

    notify_text = (
        f"📌 Новая запись!\n\n"
        f"👤 {data['name']}\n"
        f"✂ Услуга: {data['service']}\n"
        f"💈 Мастер: {data['master']}\n"
        f"📱 Телефон: {data['phone']}\n"
        f"📅 Дата: {data['date']}\n"
        f"🕒 Время: {data['time']}"
    )
    await bot.send_message(MASTER_CHAT_ID, notify_text)

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add(MESSAGES[lang]["order"])
    await message.answer(MESSAGES[lang]["success"], reply_markup=kb)
    await state.finish()


# 🚀 Запуск
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
