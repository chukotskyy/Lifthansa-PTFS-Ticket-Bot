import os
import asyncio
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    LabeledPrice, PreCheckoutQuery, Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8393319624:AAFSScRfmtAI5IGy7drlkTmJEMSHJl7LN_g"
ADMIN_IDS = [7891334423]

DB_NAME = "airline.db"
BONUS_AMOUNT = 250
BONUS_COOLDOWN = 30 * 60
MILES_PERCENT = 20

DONATE_PACKAGES = {
    "small": {"stars": 10, "rub": 1000, "name": "10 Stars"},
    "medium": {"stars": 50, "rub": 5000, "name": "50 Stars"},
    "large": {"stars": 100, "rub": 10000, "name": "100 Stars"},
}
# ==============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 1000,
        miles INTEGER DEFAULT 0,
        last_bonus TIMESTAMP
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS flights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        airline TEXT,
        flight_number TEXT,
        route TEXT,
        price INTEGER,
        is_active INTEGER DEFAULT 1
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS tickets (
        ticket_id TEXT PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        airline TEXT,
        flight_number TEXT,
        route TEXT,
        price INTEGER,
        payment_method TEXT,
        miles_earned INTEGER,
        seat TEXT,
        gate TEXT,
        used INTEGER DEFAULT 0
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS staff (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('server_link', 'https://www.roblox.com/games/123456789/Private')")
    
    conn.commit()
    conn.close()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def update_balance(user_id, amount, miles_amount=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ?, miles = miles + ? WHERE user_id = ?", (amount, miles_amount, user_id))
    conn.commit()
    conn.close()

def get_server_link():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'server_link'")
    link = cur.fetchone()[0]
    conn.close()
    return link

def get_active_flights():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM flights WHERE is_active = 1")
    flights = cur.fetchall()
    conn.close()
    return flights

def add_flight(airline, flight_number, route, price):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO flights (airline, flight_number, route, price) VALUES (?, ?, ?, ?)", (airline, flight_number, route, price))
    conn.commit()
    conn.close()

def delete_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE flights SET is_active = 0 WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()

def get_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM flights WHERE id = ?", (flight_id,))
    flight = cur.fetchone()
    conn.close()
    return flight

def add_staff(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO staff VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def remove_staff(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_staff(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff WHERE user_id = ?", (user_id,))
    staff = cur.fetchone()
    conn.close()
    return staff is not None

# ================= КЛАВИАТУРЫ =================
def main_keyboard(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛫 Купить билет")
    builder.button(text="👤 Профиль")
    builder.button(text="💰 Бонус")
    builder.button(text="💎 Донат")
    
    if is_staff(user_id) or is_admin(user_id):
        builder.button(text="✅ Проверить билет")
    
    if is_admin(user_id):
        builder.button(text="🔐 Админ-панель")
    
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)

# ================= СОСТОЯНИЯ =================
class AdminStates(StatesGroup):
    waiting_airline = State()
    waiting_flight_number = State()
    waiting_route = State()
    waiting_price = State()
    waiting_link = State()
    waiting_staff_add = State()
    waiting_staff_del = State()
    waiting_give_id = State()
    waiting_give_amount = State()
    waiting_check = State()

# ================= КОМАНДА /start =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    add_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"✈️ <b>Добро пожаловать в Lufthansa!</b>\n\n"
        f"Покупайте билеты, получайте бонусы и мили!\n\n"
        f"Используйте кнопки внизу экрана.",
        reply_markup=main_keyboard(message.from_user.id),
        parse_mode="HTML"
    )

# ================= ПРОФИЛЬ =================
@dp.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        add_user(message.from_user.id, message.from_user.username)
        user = get_user(message.from_user.id)
    
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: @{user[1]}\n"
        f"💰 Баланс: {user[2]} RUB\n"
        f"🛩 Мили: {user[3]}",
        parse_mode="HTML"
    )

# ================= БОНУС =================
@dp.message(F.text == "💰 Бонус")
async def cmd_bonus(message: Message):
    add_user(message.from_user.id, message.from_user.username)
    user = get_user(message.from_user.id)
    now = datetime.now()
    
    if user[4]:
        last = datetime.fromisoformat(user[4])
        diff = (now - last).total_seconds()
        if diff < BONUS_COOLDOWN:
            remaining = int(BONUS_COOLDOWN - diff)
            await message.answer(f"⏳ Подождите {remaining // 60} мин {remaining % 60} сек")
            return
    
    update_balance(message.from_user.id, BONUS_AMOUNT)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ +{BONUS_AMOUNT} RUB!")

# ================= ПОКУПКА БИЛЕТА =================
@dp.message(F.text == "🛫 Купить билет")
async def cmd_buy(message: Message):
    flights = get_active_flights()
    
    if not flights:
        await message.answer("❌ Нет активных рейсов")
        return
    
    builder = InlineKeyboardBuilder()
    for f in flights:
        builder.button(text=f"{f[1]} | {f[3]} | {f[4]} RUB", callback_data=f"flight:{f[0]}")
    builder.adjust(1)
    
    await message.answer("✈️ Выберите рейс:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("flight:"))
async def cb_flight(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight(flight_id)
    
    if not flight:
        await call.answer("Рейс не найден")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 RUB", callback_data=f"payrub:{flight_id}")
    builder.button(text="🛩 Мили", callback_data=f"paymiles:{flight_id}")
    builder.adjust(2)
    
    await call.message.edit_text(
        f"✈️ {flight[1]}\n"
        f"Номер: {flight[2]}\n"
        f"Маршрут: {flight[3]}\n"
        f"Цена: {flight[4]} RUB\n\n"
        f"Способ оплаты:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("payrub:"))
async def cb_payrub(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight(flight_id)
    user = get_user(call.from_user.id)
    
    if not flight or not user:
        await call.answer("Ошибка")
        return
    
    price = flight[4]
    if user[2] < price:
        await call.answer("Недостаточно средств!")
        return
    
    ticket_id = f"LH-{random.randint(100000, 999999)}"
    seat = f"{random.randint(1, 30)}{random.choice('ABCDEF')}"
    gate = f"{random.choice('ABCD')}{random.randint(1, 20)}"
    miles = int(price * MILES_PERCENT / 100)
    
    update_balance(call.from_user.id, -price, miles)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], flight[3], price, "RUB", miles, seat, gate))
    conn.commit()
    conn.close()
    
    link = get_server_link()
    
    await call.message.edit_text(
        f"╔════════════════════════╗\n"
        f"║  LUFTHANSA BOARDING PASS  ║\n"
        f"╠════════════════════════╣\n"
        f"║ 🎫 {ticket_id}\n"
        f"║ 👤 @{call.from_user.username}\n"
        f"║ ✈️ {flight[2]}\n"
        f"║ 📍 {flight[3]}\n"
        f"║ 💺 {seat}  🚪 {gate}\n"
        f"║ 💳 {price} RUB\n"
        f"║ 🛩 +{miles} миль\n"
        f"╠════════════════════════╣\n"
        f"║ 🔗 {link}\n"
        f"╚════════════════════════╝",
        disable_web_page_preview=True
    )

@dp.callback_query(F.data.startswith("paymiles:"))
async def cb_paymiles(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight(flight_id)
    user = get_user(call.from_user.id)
    
    if not flight or not user:
        await call.answer("Ошибка")
        return
    
    price = flight[4]
    if user[3] < price:
        await call.answer("Недостаточно миль!")
        return
    
    ticket_id = f"LH-{random.randint(100000, 999999)}"
    seat = f"{random.randint(1, 30)}{random.choice('ABCDEF')}"
    gate = f"{random.choice('ABCD')}{random.randint(1, 20)}"
    miles = int(price * MILES_PERCENT / 100)
    
    update_balance(call.from_user.id, 0, -price + miles)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], flight[3], price, "MILES", miles, seat, gate))
    conn.commit()
    conn.close()
    
    link = get_server_link()
    
    await call.message.edit_text(
        f"╔════════════════════════╗\n"
        f"║  LUFTHANSA BOARDING PASS  ║\n"
        f"╠════════════════════════╣\n"
        f"║ 🎫 {ticket_id}\n"
        f"║ 👤 @{call.from_user.username}\n"
        f"║ ✈️ {flight[2]}\n"
        f"║ 📍 {flight[3]}\n"
        f"║ 💺 {seat}  🚪 {gate}\n"
        f"║ 💳 {price} миль\n"
        f"║ 🛩 +{miles} миль\n"
        f"╠════════════════════════╣\n"
        f"║ 🔗 {link}\n"
        f"╚════════════════════════╝",
        disable_web_page_preview=True
    )

# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(F.text == "🔐 Админ-панель")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="✈️ Создать рейс")
    builder.button(text="🗑 Удалить рейс")
    builder.button(text="🔗 Ссылка на сервер")
    builder.button(text="➕ Бортпроводник")
    builder.button(text="➖ Удалить бортпроводника")
    builder.button(text="💳 Выдать валюту")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    
    await message.answer("🔐 Админ-панель:", reply_markup=builder.as_markup(resize_keyboard=True))

# ================= СОЗДАНИЕ РЕЙСА =================
@dp.message(F.text == "✈️ Создать рейс")
async def cmd_create_flight(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Название авиакомпании:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_airline)

@dp.message(AdminStates.waiting_airline)
async def process_airline(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    await state.update_data(airline=message.text)
    await message.answer("Номер рейса:")
    await state.set_state(AdminStates.waiting_flight_number)

@dp.message(AdminStates.waiting_flight_number)
async def process_number(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    await state.update_data(number=message.text)
    await message.answer("Маршрут:")
    await state.set_state(AdminStates.waiting_route)

@dp.message(AdminStates.waiting_route)
async def process_route(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    await state.update_data(route=message.text)
    await message.answer("Цена в RUB:")
    await state.set_state(AdminStates.waiting_price)

@dp.message(AdminStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    try:
        price = int(message.text)
    except:
        await message.answer("Введите число!")
        return
    
    data = await state.get_data()
    add_flight(data['airline'], data['number'], data['route'], price)
    
    await message.answer(
        f"✅ Рейс создан!\n\n"
        f"✈️ {data['airline']} {data['number']}\n"
        f"📍 {data['route']}\n"
        f"💰 {price} RUB",
        reply_markup=main_keyboard(message.from_user.id)
    )
    await state.clear()

# ================= УДАЛЕНИЕ РЕЙСА =================
@dp.message(F.text == "🗑 Удалить рейс")
async def cmd_delete_flight(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    flights = get_active_flights()
    if not flights:
        await message.answer("Нет активных рейсов")
        return
    
    builder = InlineKeyboardBuilder()
    for f in flights:
        builder.button(text=f"🗑 {f[2]}", callback_data=f"del:{f[0]}")
    builder.adjust(1)
    
    await message.answer("Выберите рейс:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del:"))
async def cb_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    flight_id = int(call.data.split(":")[1])
    delete_flight(flight_id)
    await call.message.edit_text("✅ Рейс удален")
    await call.answer()

# ================= БОРТПРОВОДНИКИ =================
@dp.message(F.text == "➕ Бортпроводник")
async def cmd_add_staff(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите ID бортпроводника:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_staff_add)

@dp.message(AdminStates.waiting_staff_add)
async def process_add_staff(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    try:
        staff_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите число!")
        return
    add_staff(staff_id, "unknown")
    await message.answer(f"✅ Бортпроводник {staff_id} добавлен!", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

@dp.message(F.text == "➖ Удалить бортпроводника")
async def cmd_del_staff(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите ID бортпроводника:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_staff_del)

@dp.message(AdminStates.waiting_staff_del)
async def process_del_staff(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    try:
        staff_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите число!")
        return
    remove_staff(staff_id)
    await message.answer(f"✅ Бортпроводник {staff_id} удален!", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

# ================= ССЫЛКА НА СЕРВЕР =================
@dp.message(F.text == "🔗 Ссылка на сервер")
async def cmd_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите ссылку:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_link)

@dp.message(AdminStates.waiting_link)
async def process_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = ? WHERE key = 'server_link'", (message.text,))
    conn.commit()
    conn.close()
    await message.answer("✅ Ссылка обновлена!", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

# ================= ВЫДАЧА ВАЛЮТЫ =================
@dp.message(F.text == "💳 Выдать валюту")
async def cmd_give(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("ID пользователя:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_give_id)

@dp.message(AdminStates.waiting_give_id)
async def process_give_id(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    try:
        user_id = int(message.text.strip())
    except:
        await message.answer("❌ Введите число!")
        return
    await state.update_data(give_id=user_id)
    await message.answer("Сколько RUB?")
    await state.set_state(AdminStates.waiting_give_amount)

@dp.message(AdminStates.waiting_give_amount)
async def process_give_amount(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("❌ Введите число!")
        return
    data = await state.get_data()
    user_id = data['give_id']
    add_user(user_id, "unknown")
    update_balance(user_id, amount)
    await message.answer(f"✅ Баланс {user_id} изменен на {amount}", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

# ================= ПРОВЕРКА БИЛЕТА =================
@dp.message(F.text == "✅ Проверить билет")
async def cmd_check(message: Message, state: FSMContext):
    if not is_staff(message.from_user.id) and not is_admin(message.from_user.id):
        return
    await message.answer("Номер билета:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_check)

@dp.message(AdminStates.waiting_check)
async def process_check(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    ticket_id = message.text.upper().strip()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cur.fetchone()
    conn.close()
    
    if not ticket:
        await message.answer("❌ Билет не найден", reply_markup=main_keyboard(message.from_user.id))
        await state.clear()
        return
    
    if ticket[11] == 1:
        await message.answer("❌ Билет использован", reply_markup=main_keyboard(message.from_user.id))
        await state.clear()
        return
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET used = 1 WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ ПОСАДКА РАЗРЕШЕНА\n\n"
        f"👤 @{ticket[2]}\n"
        f"✈️ {ticket[4]}\n"
        f"📍 {ticket[5]}\n"
        f"💺 {ticket[9]}",
        reply_markup=main_keyboard(message.from_user.id)
    )
    await state.clear()

# ================= ДОНАТ =================
@dp.message(F.text == "💎 Донат")
async def cmd_donate(message: Message):
    builder = InlineKeyboardBuilder()
    for pid, pkg in DONATE_PACKAGES.items():
        builder.button(text=f"{pkg['name']} = {pkg['rub']} RUB", callback_data=f"donate:{pid}")
    builder.adjust(1)
    await message.answer("Выберите пакет:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("donate:"))
async def cb_donate(call: CallbackQuery):
    pid = call.data.split(":")[1]
    pkg = DONATE_PACKAGES.get(pid)
    if not pkg:
        return
    prices = [LabeledPrice(label=pkg['name'], amount=pkg['stars'])]
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="Пополнение",
        description=f"{pkg['rub']} RUB",
        payload=f"donate_{pid}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await call.answer()

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: Message):
    payment = message.successful_payment
    parts = payment.invoice_payload.split("_")
    if len(parts) >= 3 and parts[0] == "donate":
        pid = parts[1]
        pkg = DONATE_PACKAGES.get(pid)
        if pkg:
            add_user(message.from_user.id, message.from_user.username)
            update_balance(message.from_user.id, pkg['rub'])
            await message.answer(f"✅ +{pkg['rub']} RUB!")

# ================= НАЗАД =================
@dp.message(F.text == "🔙 Назад")
async def cmd_back(message: Message):
    await message.answer("Главное меню:", reply_markup=main_keyboard(message.from_user.id))

# ================= ЗАПУСК =================
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())