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
    LabeledPrice, PreCheckoutQuery, Message, ReplyKeyboardMarkup,
    KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("8393319624:AAFSScRfmtAI5IGy7drlkTmJEMSHJl7LN_g")
DB_NAME = "airline.db"

BONUS_AMOUNT = 250
BONUS_COOLDOWN = 30 * 60
MILES_PERCENT = 20

# Список админов (можно добавить несколько)
ADMIN_IDS = [7891334423]  # Замените на реальные ID

# Пакеты доната
DONATE_PACKAGES = {
    "small": {"stars": 10, "rub": 1000, "name": "💫 10 Stars"},
    "medium": {"stars": 50, "rub": 5000, "name": "🌟 50 Stars"},
    "large": {"stars": 100, "rub": 10000, "name": "💎 100 Stars"},
    "mega": {"stars": 250, "rub": 25000, "name": "👑 250 Stars"},
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
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            miles INTEGER DEFAULT 0,
            last_bonus TIMESTAMP,
            notifications INTEGER DEFAULT 1
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airline TEXT,
            flight_number TEXT,
            route TEXT,
            price INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
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
            boarding_time TEXT,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'flight_attendant'
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount_stars INTEGER,
            amount_rub INTEGER,
            telegram_payment_id TEXT,
            created_at TIMESTAMP
        )
    """)
    
    # Добавляем админов
    for admin_id in ADMIN_IDS:
        cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_link', 'https://www.roblox.com/games/123456789/Private')")
    
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    admin = cur.fetchone()
    conn.close()
    return admin is not None

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
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, balance, miles) VALUES (?, ?, 1000, 0)", (user_id, username))
    conn.commit()
    conn.close()

def update_balance(user_id, amount, miles_amount=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance = balance + ?, miles = miles + ? WHERE user_id = ?",
        (amount, miles_amount, user_id)
    )
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
    cur.execute("SELECT * FROM flights WHERE is_active = 1 ORDER BY created_at DESC")
    flights = cur.fetchall()
    conn.close()
    return flights

def add_flight(airline, flight_number, route, price):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO flights (airline, flight_number, route, price, created_at) VALUES (?, ?, ?, ?, ?)",
        (airline, flight_number, route, price, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def delete_flight(flight_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE flights SET is_active = 0 WHERE id = ?", (flight_id,))
    conn.commit()
    conn.close()

def get_flight_by_id(flight_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM flights WHERE id = ? AND is_active = 1", (flight_id,))
    flight = cur.fetchone()
    conn.close()
    return flight

def add_staff(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO staff (user_id, username) VALUES (?, ?)", (user_id, username))
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

def get_all_users_for_notification():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE notifications = 1")
    users = cur.fetchall()
    conn.close()
    return [user[0] for user in users]

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

# ================= СОСТОЯНИЯ FSM =================
class AdminStates(StatesGroup):
    waiting_airline = State()
    waiting_flight_number = State()
    waiting_flight_route = State()
    waiting_flight_price = State()
    waiting_link = State()
    waiting_staff_add = State()
    waiting_give_id = State()
    waiting_give_amount = State()
    waiting_check_ticket = State()
    waiting_announcement = State()

# ================= ОБРАБОТЧИКИ КОМАНД =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    add_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"✈️ <b>Добро пожаловать в Lufthansa Bot!</b>\n\n"
        f"Здесь вы можете купить билеты на рейсы нашей авиакомпании.\n\n"
        f"🎮 <b>Возможности:</b>\n"
        f"• Покупка билетов\n"
        f"• Бонус каждые 30 минут\n"
        f"• Оплата через Telegram Stars\n"
        f"• Накопление миль\n\n"
        f"Используйте кнопки внизу экрана.",
        reply_markup=main_keyboard(message.from_user.id),
        parse_mode="HTML"
    )

@dp.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        add_user(message.from_user.id, message.from_user.username)
        user = get_user(message.from_user.id)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (message.from_user.id,))
    t_count = cur.fetchone()[0]
    conn.close()
    
    await message.answer(
        f"👤 <b>Профиль пассажира</b>\n\n"
        f"Имя: @{user[1]}\n"
        f"💰 Баланс: <b>{user[2]} RUB</b>\n"
        f"🛩 Мили: <b>{user[3]} миль</b>\n"
        f"🎫 Куплено билетов: {t_count}\n\n"
        f"<i>Мили можно тратить на билеты (1 миля = 1 RUB)</i>",
        parse_mode="HTML"
    )

@dp.message(F.text == "💰 Бонус")
async def cmd_bonus(message: Message):
    add_user(message.from_user.id, message.from_user.username)
    user = get_user(message.from_user.id)
    now = datetime.now()
    
    if user[4]:
        last_bonus = datetime.fromisoformat(user[4])
        diff = (now - last_bonus).total_seconds()
        if diff < BONUS_COOLDOWN:
            remaining = int(BONUS_COOLDOWN - diff)
            minutes = remaining // 60
            seconds = remaining % 60
            await message.answer(f"⏳ Рано! Возвращайтесь через {minutes} мин {seconds} сек.")
            return
    
    update_balance(message.from_user.id, BONUS_AMOUNT)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Вы получили {BONUS_AMOUNT} RUB!")

@dp.message(F.text == "💎 Донат")
async def cmd_donate(message: Message):
    builder = InlineKeyboardBuilder()
    for package_id, package in DONATE_PACKAGES.items():
        builder.button(
            text=f"{package['name']} = {package['rub']} RUB",
            callback_data=f"donate:{package_id}"
        )
    builder.adjust(1)
    
    await message.answer(
        "💎 <b>Пополнение через Telegram Stars</b>\n\n"
        "Выберите пакет:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.message(F.text == "🛫 Купить билет")
async def cmd_buy_ticket(message: Message):
    flights = get_active_flights()
    
    if not flights:
        await message.answer("❌ Сейчас нет активных рейсов.")
        return
    
    builder = InlineKeyboardBuilder()
    for flight in flights:
        builder.button(
            text=f"✈️ {flight[1]} | {flight[3]} | {flight[4]} RUB",
            callback_data=f"select_flight:{flight[0]}"
        )
    builder.adjust(1)
    
    await message.answer(
        "✈️ <b>Доступные рейсы:</b>\n\n"
        "Выберите рейс:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("select_flight:"))
async def cb_select_flight(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight_by_id(flight_id)
    
    if not flight:
        await call.answer("❌ Рейс не найден", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить RUB", callback_data=f"pay_rub:{flight_id}")
    builder.button(text="🛩 Оплатить милями", callback_data=f"pay_miles:{flight_id}")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"✈️ <b>{flight[1]}</b>\n\n"
        f"Номер рейса: <b>{flight[2]}</b>\n"
        f"Маршрут: <b>{flight[3]}</b>\n"
        f"Стоимость: <b>{flight[4]} RUB</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("pay_rub:"))
async def cb_pay_rub(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight_by_id(flight_id)
    
    if not flight:
        await call.answer("❌ Рейс уже неактивен", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    price = flight[4]
    
    if not user or user[2] < price:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Генерируем данные билета
    ticket_id = f"LH-{random.randint(100000, 999999)}"
    seat = f"{random.randint(1, 30)}{random.choice('ABCDEF')}"
    gate = f"{random.choice('ABCD')}{random.randint(1, 20)}"
    boarding_time = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
    miles_earned = int(price * MILES_PERCENT / 100)
    
    update_balance(call.from_user.id, -price, miles_earned)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (ticket_id, user_id, username, airline, flight_number, route, price, payment_method, miles_earned, seat, gate, boarding_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], flight[3], price, "RUB", miles_earned, seat, gate, boarding_time, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    link = get_server_link()
    
    # Красивый посадочный талон
    ticket_text = (
        f"╔══════════════════════════════╗\n"
        f"║     ✈️ LUFTHANSA BOARDING PASS    ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 🎫 Номер: <code>{ticket_id}</code>\n"
        f"║ 👤 Пассажир: @{call.from_user.username}\n"
        f"║ ✈️ Рейс: {flight[2]}\n"
        f"║ 📍 Маршрут: {flight[3]}\n"
        f"║ 💺 Место: {seat}\n"
        f"║ 🚪 Выход: {gate}\n"
        f"║ ⏰ Посадка: {boarding_time}\n"
        f"║ 💳 Оплата: {price} RUB\n"
        f"║ 🛩 Мили: +{miles_earned}\n"
        f"╠══════════════════════════════╣\n"
        f"║ 🔗 <a href='{link}'>Приватный сервер</a>\n"
        f"╚══════════════════════════════╝"
    )
    
    await call.message.edit_text(ticket_text, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer("✅ Билет куплен!", show_alert=True)

@dp.callback_query(F.data.startswith("pay_miles:"))
async def cb_pay_miles(call: CallbackQuery):
    flight_id = int(call.data.split(":")[1])
    flight = get_flight_by_id(flight_id)
    
    if not flight:
        await call.answer("❌ Рейс уже неактивен", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    price = flight[4]
    
    if not user or user[3] < price:
        await call.answer(f"❌ Недостаточно миль! Нужно {price}, у вас {user[3] if user else 0}", show_alert=True)
        return
    
    ticket_id = f"LH-{random.randint(100000, 999999)}"
    seat = f"{random.randint(1, 30)}{random.choice('ABCDEF')}"
    gate = f"{random.choice('ABCD')}{random.randint(1, 20)}"
    boarding_time = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
    miles_earned = int(price * MILES_PERCENT / 100)
    
    update_balance(call.from_user.id, 0, -price + miles_earned)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (ticket_id, user_id, username, airline, flight_number, route, price, payment_method, miles_earned, seat, gate, boarding_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], flight[3], price, "MILES", miles_earned, seat, gate, boarding_time, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    link = get_server_link()
    
    ticket_text = (
        f"╔══════════════════════════════╗\n"
        f"║     ✈️ LUFTHANSA BOARDING PASS    ║\n"
        f"╠══════════════════════════════╣\n"
        f"║ 🎫 Номер: <code>{ticket_id}</code>\n"
        f"║ 👤 Пассажир: @{call.from_user.username}\n"
        f"║ ✈️ Рейс: {flight[2]}\n"
        f"║ 📍 Маршрут: {flight[3]}\n"
        f"║ 💺 Место: {seat}\n"
        f"║ 🚪 Выход: {gate}\n"
        f"║ ⏰ Посадка: {boarding_time}\n"
        f"║ 💳 Оплата: {price} миль\n"
        f"║ 🛩 Мили: +{miles_earned}\n"
        f"╠══════════════════════════════╣\n"
        f"║ 🔗 <a href='{link}'>Приватный сервер</a>\n"
        f"╚══════════════════════════════╝"
    )
    
    await call.message.edit_text(ticket_text, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer("✅ Билет куплен за мили!", show_alert=True)

# ================= ДОНАТ =================
@dp.callback_query(F.data.startswith("donate:"))
async def cb_donate(call: CallbackQuery):
    package_id = call.data.split(":")[1]
    package = DONATE_PACKAGES.get(package_id)
    
    if not package:
        await call.answer("❌ Пакет не найден", show_alert=True)
        return
    
    prices = [LabeledPrice(label=f"{package['name']}", amount=package['stars'])]
    
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="Пополнение баланса",
        description=f"{package['rub']} RUB для Lufthansa",
        payload=f"donate_{package_id}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="donate"
    )
    await call.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_payment(message: Message):
    payment = message.successful_payment
    parts = payment.invoice_payload.split("_")
    
    if len(parts) >= 3 and parts[0] == "donate":
        package_id = parts[1]
        package = DONATE_PACKAGES.get(package_id)
        
        if package:
            add_user(message.from_user.id, message.from_user.username)
            update_balance(message.from_user.id, package['rub'])
            
            await message.answer(
                f"✅ Оплата получена!\n"
                f"💰 Начислено: {package['rub']} RUB"
            )

# ================= ПРОВЕРКА БИЛЕТОВ =================
@dp.message(F.text == "✅ Проверить билет")
async def cmd_check_ticket(message: Message, state: FSMContext):
    if not is_staff(message.from_user.id) and not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    
    await message.answer(
        "🎫 Введите номер билета:",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_check_ticket)

@dp.message(AdminStates.waiting_check_ticket)
async def process_check_ticket(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    ticket_number = message.text.upper().strip()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_number,))
    ticket = cur.fetchone()
    conn.close()
    
    if not ticket:
        await message.answer(f"❌ Билет {ticket_number} не найден")
        await state.clear()
        return
    
    if ticket[12] == 1:
        await message.answer(f"❌ Билет уже использован!")
        await state.clear()
        return
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET used = 1 WHERE ticket_id = ?", (ticket_number,))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ <b>ПОСАДКА РАЗРЕШЕНА</b>\n\n"
        f"👤 Пассажир: @{ticket[2]}\n"
        f"✈️ Рейс: {ticket[4]} ({ticket[5]})\n"
        f"💺 Место: {ticket[9]}\n"
        f"🎫 Билет: <code>{ticket[0]}</code>",
        parse_mode="HTML",
        reply_markup=main_keyboard(message.from_user.id)
    )
    await state.clear()

# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(F.text == "🔐 Админ-панель")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="✈️ Создать рейс")
    builder.button(text="🗑 Удалить рейс")
    builder.button(text="📢 Рассылка")
    builder.button(text="🔗 Ссылка на сервер")
    builder.button(text="➕ Бортпроводник")
    builder.button(text="➖ Удалить бортпроводника")
    builder.button(text="💳 Выдать валюту")
    builder.button(text="📊 Статистика")
    builder.button(text="🔙 Назад")
    builder.adjust(2)
    
    await message.answer("🔐 Админ-панель:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text == "✈️ Создать рейс")
async def cmd_create_flight(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("Введите название авиакомпании:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_airline)

@dp.message(AdminStates.waiting_airline)
async def process_airline(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    await state.update_data(airline=message.text)
    await message.answer("Введите номер рейса (например LH-123):")
    await state.set_state(AdminStates.waiting_flight_number)

@dp.message(AdminStates.waiting_flight_number)
async def process_flight_number(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    await state.update_data(flight_number=message.text.upper())
    await message.answer("Введите маршрут (например: Москва -> Берлин):")
    await state.set_state(AdminStates.waiting_flight_route)

@dp.message(AdminStates.waiting_flight_route)
async def process_flight_route(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    await state.update_data(flight_route=message.text)
    await message.answer("Введите стоимость билета в RUB:")
    await state.set_state(AdminStates.waiting_flight_price)

@dp.message(AdminStates.waiting_flight_price)
async def process_flight_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    add_flight(data['airline'], data['flight_number'], data['flight_route'], price)
    
    # Отправляем уведомление всем пользователям
    users = get_all_users_for_notification()
    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                f"🆕 <b>Новый рейс!</b>\n\n"
                f"✈️ Авиакомпания: {data['airline']}\n"
                f"Номер: {data['flight_number']}\n"
                f"Маршрут: {data['flight_route']}\n"
                f"Цена: {price} RUB\n\n"
                f"Успейте купить билет!",
                parse_mode="HTML"
            )
        except:
            pass
    
    await message.answer(
        f"✅ Рейс создан!\n\n"
        f"✈️ {data['airline']} {data['flight_number']}\n"
        f"📍 {data['flight_route']}\n"
        f"💰 {price} RUB\n\n"
        f"Уведомления отправлены!",
        reply_markup=main_keyboard(message.from_user.id)
    )
    await state.clear()

@dp.message(F.text == "🗑 Удалить рейс")
async def cmd_delete_flight(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    flights = get_active_flights()
    if not flights:
        await message.answer("Нет активных рейсов")
        return
    
    builder = InlineKeyboardBuilder()
    for flight in flights:
        builder.button(
            text=f"🗑 {flight[1]} {flight[2]}",
            callback_data=f"delete_flight:{flight[0]}"
        )
    builder.adjust(1)
    
    await message.answer("Выберите рейс для удаления:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("delete_flight:"))
async def cb_delete_flight(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    
    flight_id = int(call.data.split(":")[1])
    delete_flight(flight_id)
    await call.message.edit_text("✅ Рейс удален")
    await call.answer()

@dp.message(F.text == "📢 Рассылка")
async def cmd_announcement(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("Введите текст рассылки:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_announcement)

@dp.message(AdminStates.waiting_announcement)
async def process_announcement(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    users = get_all_users_for_notification()
    sent = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 <b>Объявление:</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
        except:
            pass
    
    await message.answer(f"✅ Рассылка отправлена {sent} пользователям", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

@dp.message(F.text == "🔗 Ссылка на сервер")
async def cmd_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("Введите новую ссылку:", reply_markup=cancel_keyboard())
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
        staff_id = int(message.text)
    except ValueError:
        await message.answer("❌ Неверный ID!")
        return
    
    add_staff(staff_id, "unknown")
    await message.answer(f"✅ Бортпроводник {staff_id} добавлен!", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

@dp.message(F.text == "➖ Удалить бортпроводника")
async def cmd_remove_staff(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("Введите ID бортпроводника для удаления:", reply_markup=cancel_keyboard())
    await state.set_state(AdminStates.waiting_staff_del)

@dp.message(AdminStates.waiting_staff_del)
async def process_remove_staff(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=main_keyboard(message.from_user.id))
        return
    
    try:
        staff_id = int(message.text)
    except ValueError:
        await message.answer("❌ Неверный ID!")
        return
    
    remove_staff(staff_id)
    await message.answer(f"✅ Бортпроводник {staff_id} удален!", reply_markup=main_keyboard(message.from_user.id))
    await state.clear()

@dp.message(F.text == "💳 Выдать валюту")
async def cmd_give(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
