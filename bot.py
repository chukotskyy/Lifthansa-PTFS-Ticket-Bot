# После установки импортируем
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F

import random
import sqlite3
from datetime import datetime, timedelta
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    LabeledPrice, PreCheckoutQuery, Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8393319624:AAFSScRfmtAI5IGy7drlkTmJEMSHJl7LN_g"
ADMIN_ID = 7891334423  # ID админа
DB_NAME = "airline.db"

BONUS_AMOUNT = 250
BONUS_COOLDOWN = 30 * 60  # 30 минут
MILES_PERCENT = 20  # Процент миль от стоимости билета

# Пакеты доната (цена в Telegram Stars)
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
            last_bonus TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_flight (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            flight_number TEXT,
            route TEXT,
            price INTEGER,
            created_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            flight_number TEXT,
            route TEXT,
            price INTEGER,
            payment_method TEXT,
            miles_earned INTEGER,
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
    
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_link', 'https://www.roblox.com/games/123456789/Private')")
    
    conn.commit()
    conn.close()

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

def get_active_flight():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM active_flight WHERE id = 1")
    flight = cur.fetchone()
    conn.close()
    return flight

def set_active_flight(flight_number, route, price):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO active_flight (id, flight_number, route, price, created_at) VALUES (1, ?, ?, ?, ?)",
        (flight_number, route, price, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def delete_active_flight():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM active_flight WHERE id = 1")
    conn.commit()
    conn.close()

def add_transaction(user_id, amount_stars, amount_rub, payment_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (user_id, amount_stars, amount_rub, telegram_payment_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount_stars, amount_rub, payment_id, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def is_staff(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff WHERE user_id = ?", (user_id,))
    staff = cur.fetchone()
    conn.close()
    return staff is not None

def add_staff(user_id, username, role='flight_attendant'):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO staff (user_id, username, role) VALUES (?, ?, ?)",
        (user_id, username, role)
    )
    conn.commit()
    conn.close()

def remove_staff(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_staff():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff")
    staff_list = cur.fetchall()
    conn.close()
    return staff_list

# ================= КЛАВИАТУРЫ =================
def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛫 Купить билет", callback_data="buy_ticket")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="💰 Бонус (каждые 30 мин)", callback_data="get_bonus")
    builder.button(text="💎 Донат", callback_data="donate_menu")
    
    # Добавляем кнопку для бортпроводников
    user_id = builder._markup.inline_keyboard  # Не используем это
    builder.adjust(2)
    return builder.as_markup()

def main_kb_for_user(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛫 Купить билет", callback_data="buy_ticket")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="💰 Бонус (каждые 30 мин)", callback_data="get_bonus")
    builder.button(text="💎 Донат", callback_data="donate_menu")
    
    # Если пользователь - бортпроводник или админ, добавляем кнопку проверки
    if is_staff(user_id) or user_id == ADMIN_ID:
        builder.button(text="✅ Проверить билет", callback_data="check_ticket")
    
    # Если админ, добавляем кнопку админ-панели
    if user_id == ADMIN_ID:
        builder.button(text="🔐 Админ-панель", callback_data="admin_panel")
    
    builder.adjust(2)
    return builder.as_markup()

def donate_kb():
    builder = InlineKeyboardBuilder()
    for package_id, package in DONATE_PACKAGES.items():
        builder.button(
            text=f"{package['name']} = {package['rub']} RUB", 
            callback_data=f"donate:{package_id}"
        )
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ])

def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✈️ Создать рейс", callback_data="admin_create_flight")
    builder.button(text="🗑 Удалить рейс", callback_data="admin_delete_flight")
    builder.button(text="🔗 Изменить ссылку на сервер", callback_data="admin_link")
    builder.button(text="➕ Добавить бортпроводника", callback_data="admin_add_staff")
    builder.button(text="📋 Список бортпроводников", callback_data="admin_list_staff")
    builder.button(text="➖ Удалить бортпроводника", callback_data="admin_del_staff")
    builder.button(text="💳 Выдать валюту", callback_data="admin_give")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def staff_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Проверить билет", callback_data="check_ticket")
    builder.button(text="🔙 В главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# ================= СОСТОЯНИЯ FSM =================
class AdminStates(StatesGroup):
    waiting_flight_number = State()
    waiting_flight_route = State()
    waiting_flight_price = State()
    waiting_link = State()
    waiting_staff_add = State()
    waiting_staff_del = State()
    waiting_give_id = State()
    waiting_give_amount = State()
    waiting_check_ticket = State()

# ================= ОБРАБОТЧИКИ КОМАНД =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    add_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"✈️ <b>Добро пожаловать на борт, {message.from_user.first_name}!</b>\n\n"
        "Здесь вы можете купить билет на рейс нашей авиакомпании в PTFS.\n\n"
        "🎮 <b>Как играть:</b>\n"
        "• Получайте бонус каждые 30 минут\n"
        "• Пополняйте баланс через Telegram Stars\n"
        "• Покупайте билеты на активный рейс\n"
        "• Показывайте номер билета бортпроводнику\n\n"
        "Используйте кнопки ниже для навигации.",
        reply_markup=main_kb_for_user(message.from_user.id),
        parse_mode="HTML"
    )

# ================= ОБРАБОТЧИКИ КНОПОК =================
@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery):
    add_user(call.from_user.id, call.from_user.username)
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_kb_for_user(call.from_user.id)
    )
    await call.answer()

@dp.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    if not user:
        add_user(call.from_user.id, call.from_user.username)
        user = get_user(call.from_user.id)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (call.from_user.id,))
    t_count = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(amount_rub), 0) FROM transactions WHERE user_id = ?", (call.from_user.id,))
    total_donated = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(miles_earned), 0) FROM tickets WHERE user_id = ?", (call.from_user.id,))
    total_miles_earned = cur.fetchone()[0]
    conn.close()

    await call.message.edit_text(
        f"👤 <b>Профиль пассажира</b>\n\n"
        f"Имя: @{user[1]}\n"
        f"💰 Баланс: <b>{user[2]} RUB</b>\n"
        f"🛩 Мили: <b>{user[3]} миль</b>\n\n"
        f"🎫 Куплено билетов: {t_count}\n"
        f"💎 Всего задоначено: {total_donated} RUB\n"
        f"🛩 Всего заработано миль: {total_miles_earned}\n\n"
        f"<i>Мили можно тратить на покупку билетов (1 миля = 1 RUB)</i>",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "get_bonus")
async def cb_bonus(call: CallbackQuery):
    add_user(call.from_user.id, call.from_user.username)
    user = get_user(call.from_user.id)
    now = datetime.now()

    if user[4]:  # last_bonus
        last_bonus = datetime.fromisoformat(user[4])
        diff = (now - last_bonus).total_seconds()
        if diff < BONUS_COOLDOWN:
            remaining = int(BONUS_COOLDOWN - diff)
            minutes = remaining // 60
            seconds = remaining % 60
            await call.answer(f"⏳ Рано! Возвращайтесь через {minutes} мин {seconds} сек.", show_alert=True)
            return

    update_balance(call.from_user.id, BONUS_AMOUNT)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now.isoformat(), call.from_user.id))
    conn.commit()
    conn.close()
    
    await call.answer(f"✅ Вы получили {BONUS_AMOUNT} RUB!", show_alert=True)
    await cb_profile(call)

# ================= ДОНАТ ЧЕРЕЗ TELEGRAM STARS =================
@dp.callback_query(F.data == "donate_menu")
async def cb_donate_menu(call: CallbackQuery):
    await call.message.edit_text(
        "💎 <b>Пополнение баланса через Telegram Stars</b>\n\n"
        "Выберите пакет:\n"
        "• 10 Stars = 1000 RUB\n"
        "• 50 Stars = 5000 RUB\n"
        "• 100 Stars = 10000 RUB\n"
        "• 250 Stars = 25000 RUB\n\n"
        "Оплата происходит через официальную систему Telegram.",
        reply_markup=donate_kb(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("donate:"))
async def cb_donate_package(call: CallbackQuery):
    package_id = call.data.split(":")[1]
    package = DONATE_PACKAGES.get(package_id)
    
    if not package:
        await call.answer("❌ Пакет не найден", show_alert=True)
        return
    
    prices = [LabeledPrice(label=f"{package['name']} = {package['rub']} RUB", amount=package['stars'])]
    
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="Пополнение баланса",
        description=f"Покупка {package['rub']} RUB для авиакомпании PTFS",
        payload=f"donate_{package_id}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="donate",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        is_flexible=False
    )
    await call.answer("💫 Создан счет для оплаты!", show_alert=True)

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    
    parts = payload.split("_")
    if len(parts) >= 3 and parts[0] == "donate":
        package_id = parts[1]
        package = DONATE_PACKAGES.get(package_id)
        
        if package:
            add_user(user_id, message.from_user.username)
            update_balance(user_id, package['rub'])
            add_transaction(
                user_id, 
                payment.total_amount,
                package['rub'], 
                payment.telegram_payment_charge_id
            )
            
            user = get_user(user_id)
            
            await message.answer(
                f"✅ <b>Оплата успешно получена!</b>\n\n"
                f"💎 Списано Stars: {payment.total_amount}\n"
                f"💰 Начислено: {package['rub']} RUB\n"
                f"💳 Новый баланс: {user[2]} RUB\n\n"
                f"Спасибо за поддержку авиакомпании! 🙏",
                parse_mode="HTML"
            )
            
            await bot.send_message(
                ADMIN_ID,
                f"💎 <b>Новый донат!</b>\n"
                f"👤 Пользователь: @{message.from_user.username}\n"
                f"💫 Stars: {payment.total_amount}\n"
                f"💰 RUB: {package['rub']}\n"
                f"🆔 Payment ID: {payment.telegram_payment_charge_id}",
                parse_mode="HTML"
            )

# ================= ПОКУПКА БИЛЕТА =================
@dp.callback_query(F.data == "buy_ticket")
async def cb_buy_ticket(call: CallbackQuery):
    flight = get_active_flight()
    
    if not flight:
        await call.message.edit_text(
            "❌ <b>Сейчас нет активных рейсов</b>\n\n"
            "Загляните позже или следите за обновлениями!",
            reply_markup=back_kb(),
            parse_mode="HTML"
        )
        await call.answer()
        return
    
    flight_number, route, price = flight[1], flight[2], flight[3]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить RUB", callback_data=f"pay_rub:{flight_number}")
    builder.button(text="🛩 Оплатить милями", callback_data=f"pay_miles:{flight_number}")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"✈️ <b>Активный рейс</b>\n\n"
        f"Номер рейса: <b>{flight_number}</b>\n"
        f"Маршрут: <b>{route}</b>\n"
        f"Стоимость: <b>{price} RUB</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("pay_rub:"))
async def cb_pay_rub(call: CallbackQuery):
    flight_number = call.data.split(":")[1]
    flight = get_active_flight()
    
    if not flight or flight[1] != flight_number:
        await call.answer("❌ Рейс уже неактивен", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    price = flight[3]
    
    if not user or user[2] < price:
        await call.answer("❌ Недостаточно средств! Получите бонус или пополните баланс.", show_alert=True)
        return
    
    # Создаем билет
    ticket_id = f"PTFS-{random.randint(100000, 999999)}"
    miles_earned = int(price * MILES_PERCENT / 100)
    
    # Списываем RUB и начисляем мили
    update_balance(call.from_user.id, -price, miles_earned)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (ticket_id, user_id, username, flight_number, route, price, payment_method, miles_earned, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], price, "RUB", miles_earned, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    link = get_server_link()
    user_after = get_user(call.from_user.id)
    
    text = (
        f"✅ <b>Билет успешно куплен!</b>\n\n"
        f"🎫 Номер посадочного талона: <code>{ticket_id}</code>\n"
        f"👤 Пассажир: @{call.from_user.username}\n"
        f"✈️ Рейс: {flight[1]} ({flight[2]})\n"
        f"💳 Оплачено: {price} RUB\n"
        f"🛩 Начислено миль: +{miles_earned}\n\n"
        f"🔗 <a href='{link}'>Приватный сервер</a>\n\n"
        f"💰 Остаток на балансе: {user_after[2]} RUB\n"
        f"🛩 Всего миль: {user_after[3]}\n\n"
        f"Покажите этот номер бортпроводнику при посадке."
    )
    
    await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer("✅ Билет успешно куплен!", show_alert=True)

@dp.callback_query(F.data.startswith("pay_miles:"))
async def cb_pay_miles(call: CallbackQuery):
    flight_number = call.data.split(":")[1]
    flight = get_active_flight()
    
    if not flight or flight[1] != flight_number:
        await call.answer("❌ Рейс уже неактивен", show_alert=True)
        return
    
    user = get_user(call.from_user.id)
    price = flight[3]
    
    if not user or user[3] < price:
        await call.answer(f"❌ Недостаточно миль! Нужно {price} миль, у вас {user[3] if user else 0}.", show_alert=True)
        return
    
    # Создаем билет
    ticket_id = f"PTFS-{random.randint(100000, 999999)}"
    miles_earned = int(price * MILES_PERCENT / 100)
    
    # Списываем мили и начисляем новые мили (20% от стоимости)
    update_balance(call.from_user.id, 0, -price + miles_earned)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (ticket_id, user_id, username, flight_number, route, price, payment_method, miles_earned, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, call.from_user.id, call.from_user.username, flight[1], flight[2], price, "MILES", miles_earned, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    link = get_server_link()
    user_after = get_user(call.from_user.id)
    
    text = (
        f"✅ <b>Билет успешно куплен за мили!</b>\n\n"
        f"🎫 Номер посадочного талона: <code>{ticket_id}</code>\n"
        f"👤 Пассажир: @{call.from_user.username}\n"
        f"✈️ Рейс: {flight[1]} ({flight[2]})\n"
        f"💳 Оплачено: {price} миль\n"
        f"🛩 Начислено миль: +{miles_earned}\n\n"
        f"🔗 <a href='{link}'>Приватный сервер</a>\n\n"
        f"💰 Баланс: {user_after[2]} RUB\n"
        f"🛩 Всего миль: {user_after[3]}\n\n"
        f"Покажите этот номер бортпроводнику при посадке."
    )
    
    await call.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer("✅ Билет успешно куплен за мили!", show_alert=True)

# ================= ПРОВЕРКА БИЛЕТОВ (ДЛЯ БОРТПРОВОДНИКОВ) =================
@dp.callback_query(F.data == "check_ticket")
async def cb_check_ticket(call: CallbackQuery, state: FSMContext):
    if not is_staff(call.from_user.id) and call.from_user.id != ADMIN_ID:
        await call.answer("⛔ У вас нет доступа", show_alert=True)
        return
    
    await call.message.edit_text(
        "🎫 <b>Проверка билета</b>\n\n"
        "Введите номер билета (например: PTFS-123456)\n"
        "Или нажмите кнопку ниже для отмены:",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_check_ticket)
    await call.answer()

@dp.message(AdminStates.waiting_check_ticket)
async def process_check_ticket(message: Message, state: FSMContext):
    ticket_number = message.text.upper().strip()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_number,))
    ticket = cur.fetchone()
    conn.close()

    if not ticket:
        await message.answer(
            f"❌ Билет <code>{ticket_number}</code> не найден.",
            reply_markup=staff_kb(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    if ticket[8] == 1:  # used
        await message.answer(
            f"❌ Билет <code>{ticket_number}</code> уже использован!",
            reply_markup=staff_kb(),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Отмечаем билет как использованный
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET used = 1 WHERE ticket_id = ?", (ticket_number,))
    conn.commit()
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Проверить еще", callback_data="check_ticket")
    builder.button(text="🔙 В главное меню", callback_data="main_menu")
    builder.adjust(1)

    await message.answer(
        f"✅ <b>ПОСАДКА РАЗРЕШЕНА</b>\n\n"
        f"👤 Пассажир: @{ticket[2]}\n"
        f"✈️ Рейс: {ticket[3]} ({ticket[4]})\n"
        f"🎫 Номер билета: <code>{ticket[0]}</code>\n"
        f"💳 Способ оплаты: {ticket[6]}\n\n"
        f"Приятного полета!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()

# ================= АДМИН-ПАНЕЛЬ =================
@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔ У вас нет доступа", show_alert=True)
        return
    await call.message.edit_text("🔐 Админ-панель:", reply_markup=admin_kb())
    await call.answer()

@dp.callback_query(F.data == "admin_create_flight")
async def cb_create_flight(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text(
        "✈️ <b>Создание рейса</b>\n\n"
        "Введите номер рейса (например: PT-505):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_flight_number)
    await call.answer()

@dp.message(AdminStates.waiting_flight_number)
async def process_flight_number(message: Message, state: FSMContext):
    await state.update_data(flight_number=message.text.upper())
    await message.answer("📍 Введите маршрут (например: Москва -> Лондон):")
    await state.set_state(AdminStates.waiting_flight_route)

@dp.message(AdminStates.waiting_flight_route)
async def process_flight_route(message: Message, state: FSMContext):
    await state.update_data(flight_route=message.text)
    await message.answer("💰 Введите стоимость билета в RUB:")
    await state.set_state(AdminStates.waiting_flight_price)

@dp.message(AdminStates.waiting_flight_price)
async def process_flight_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную цену (положительное число):")
        return
    
    data = await state.get_data()
    flight_number = data['flight_number']
    route = data['flight_route']
    
    set_active_flight(flight_number, route, price)
    
    await message.answer(
        f"✅ <b>Рейс создан!</b>\n\n"
        f"✈️ Номер: {flight_number}\n"
        f"📍 Маршрут: {route}\n"
        f"💰 Цена: {price} RUB\n\n"
        f"Теперь пользователи могут покупать билеты.",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "admin_delete_flight")
async def cb_delete_flight(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    flight = get_active_flight()
    
    if not flight:
        await call.answer("❌ Нет активного рейса", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, удалить рейс", callback_data="confirm_delete_flight")
    builder.button(text="🔙 Отмена", callback_data="admin_panel")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"⚠️ <b>Удалить активный рейс?</b>\n\n"
        f"✈️ Номер: {flight[1]}\n"
        f"📍 Маршрут: {flight[2]}\n"
        f"💰 Цена: {flight[3]} RUB",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "confirm_delete_flight")
async def cb_confirm_delete_flight(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    delete_active_flight()
    await call.message.edit_text("✅ Рейс удален. Теперь можно создать новый.", reply_markup=admin_kb())
    await call.answer("Рейс удален", show_alert=True)

@dp.callback_query(F.data == "admin_link")
async def cb_admin_link(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("🔗 Введите новую ссылку на приватный сервер:")
    await state.set_state(AdminStates.waiting_link)
    await call.answer()

@dp.message(AdminStates.waiting_link)
async def process_link(message: Message, state: FSMContext):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = ? WHERE key = 'server_link'", (message.text,))
    conn.commit()
    conn.close()
    await message.answer("✅ Ссылка обновлена!", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "admin_add_staff")
async def cb_add_staff(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text(
        "➕ <b>Добавление бортпроводника</b>\n\n"
        "Введите ID пользователя Telegram (можно узнать у @userinfobot)\n"
        "Или перешлите сообщение от него:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_staff_add)
    await call.answer()

@dp.message(AdminStates.waiting_staff_add)
async def process_add_staff(message: Message, state: FSMContext):
    try:
        staff_id = int(message.text)
    except ValueError:
        if message.forward_from:
            staff_id = message.forward_from.id
        else:
            await message.answer("❌ Неверный формат ID. Попробуйте еще раз:")
            return
    
    # Получаем username
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = ?", (staff_id,))
    user = cur.fetchone()
    conn.close()
    
    username = user[0] if user else "unknown"
    
    add_staff(staff_id, username)
    
    await message.answer(
        f"✅ Бортпроводник @{username} (ID: {staff_id}) добавлен!",
        reply_markup=admin_kb()
    )
    await state.clear()

@dp.callback_query(F.data == "admin_list_staff")
async def cb_list_staff(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    staff_list = get_all_staff()
    
    if not staff_list:
        await call.message.edit_text(
            "📋 <b>Список бортпроводников</b>\n\n"
            "Пока нет бортпроводников.",
            reply_markup=admin_kb(),
            parse_mode="HTML"
        )
        await call.answer()
        return
    
    text = "📋 <b>Список бортпроводников</b>\n\n"
    for staff in staff_list:
        text += f"• @{staff[1]} (ID: {staff[0]})\n"
    
    await call.message.edit_text(text, reply_markup=admin_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "admin_del_staff")
async def cb_del_staff(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    staff_list = get_all_staff()
    if not staff_list:
        await call.answer("❌ Нет бортпроводников для удаления", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for staff in staff_list:
        builder.button(
            text=f"🗑 @{staff[1]} (ID: {staff[0]})",
            callback_data=f"del_staff:{staff[0]}"
        )
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)
    
    await call.message.edit_text(
        "➖ <b>Выберите бортпроводника для удаления:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("del_staff:"))
async def cb_confirm_del_staff(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    staff_id = int(call.data.split(":")[1])
    remove_staff(staff_id)
    
    await call.answer(f"✅ Бортпроводник {staff_id} удален!", show_alert=True)
    await cb_admin_panel(call)

@dp.callback_query(F.data == "admin_give")
async def cb_give(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text(
        "💳 <b>Выдача валюты</b>\n\n"
        "Введите ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_give_id)
    await call.answer()

@dp.message(AdminStates.waiting_give_id)
async def process_give_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат ID. Попробуйте еще раз:")
        return
    
    await state.update_data(give_user_id=user_id)
    await message.answer("💰 Введите сумму RUB (можно отрицательное число):")
    await state.set_state(AdminStates.waiting_give_amount)

@dp.message(AdminStates.waiting_give_amount)
async def process_give_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Неверная сумма. Попробуйте еще раз:")
        return
    
    data = await state.get_data()
    user_id = data['give_user_id']
    add_user(user_id, "unknown")
    update_balance(user_id, amount)
    
    await message.answer(
        f"✅ Баланс пользователя {user_id} изменен на {amount} RUB.",
        reply_markup=admin_kb()
    )
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    total_balance = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(miles), 0) FROM users")
    total_miles = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM tickets WHERE used = 1")
    used_tickets = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(amount_rub), 0) FROM transactions")
    total_donated = cur.fetchone()[0]
    
    conn.close()
    
    active_flight = get_active_flight()
    flight_info = f"{active_flight[1]} ({active_flight[2]})" if active_flight else "Нет активного рейса"
    
    await call.message.edit_text(
        f"📊 <b>Статистика авиакомпании</b>\n\n"
        f"✈️ Активный рейс: {flight_info}\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Общий баланс: {total_balance} RUB\n"
        f"🛩 Общие мили: {total_miles}\n"
        f"🎫 Всего билетов: {total_tickets}\n"
        f"✅ Использовано билетов: {used_tickets}\n"
        f"💎 Всего задоначено: {total_donated} RUB",
        reply_markup=admin_kb(),
        parse_mode="HTML"
    )
    await call.answer()

# ================= ЗАПУСК =================
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())