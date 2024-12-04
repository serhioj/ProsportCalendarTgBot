import sqlite3
from datetime import datetime, timedelta
import requests
import json

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from aiogram.utils.keyboard import InlineKeyboardBuilder

from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Dictionary to track the last time the command was called
last_start_time = {}

# Rate limit in seconds
RATE_LIMIT_SECONDS = 60

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            phone_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

global events_data
events_data = []  # Инициализация как пустой список
global events_count
events_count = 0


@dp.message(Command("start"))
async def send_welcome(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Check if user phone number is in the database
    conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT phone_number FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result is None:
        # Send a welcome message with a button to share the phone number
        button = types.KeyboardButton(text="✉️ Отправить номер телефона", request_contact=True)
        keyboard = types.ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True, one_time_keyboard=True)
        await message.answer("Пожалуйста, отправьте номер вашего телефона, чтобы мы могли записать ваши данные", reply_markup=keyboard)
    else:
        await send_event_info(user_id, message)




async def check_and_notify_users():
    while True:
        # Ожидание до следующей проверки (например, каждые 30 минут)
        await asyncio.sleep(10000)
        # Подключение к базе данных
        conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, phone_number FROM users')
        users = cursor.fetchall()
        conn.close()

        for user_id, phone_number in users:
            # Отправляем запрос на получение мероприятий пользователя
            response = requests.get(f"https://dev-level.ru/api/v1/events-by-phone/{phone_number}")
            if response.status_code == 200:
                events = response.json()

                # Проверяем мероприятия на дату начала
                for event in events:
                    start_date = event['startTime']
                    current_date = datetime.now()

                    # Приводим к формату d.m.y
                    formatted_date = current_date.strftime("%d.%m.%y")

                    if start_date == formatted_date:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🕒 <b>НАПОМИНАНИЕ</b>\n\n"
                                 f"<b>Сегодня начинается мероприятие</b>: {event['name']}\n"
                                 f"<b>Спорт</b>: {event['sport']}\n"
                                 f"<b>Дисциплина:</b> {event['discipline']}\n"
                                 f"<b>Пол и возраст:</b> {event['genderAge']}\n"
                                 f"<b>Локация:</b> {event['country']}, {event['location']}\n"
                                 f"<b>Начало</b>: {start_date}\n"
                                 f"<b>Конец</b>: {event["endTime"]}",
                            parse_mode="HTML"
                        )

async def send_event_info(user_id, message: Message):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="О нас", callback_data="about_us")
    keyboard.button(text="Мои мероприятия", callback_data="repeat_request")
    await message.answer(
        "<b>Prosport Calendar</b> — ваш надёжный помощник в управлении спортивными событиями!",
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data == "about_us")
async def handle_about(callback_query: CallbackQuery):
    # Создаём клавиатуру с кнопками "Мои мероприятия"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Мои мероприятия", callback_data="repeat_request")
    
    # Текст сообщения
    text = (
        "<b>Prosport Calendar</b> — это ваш надёжный помощник для эффективного управления спортивными мероприятиями."
        "С нашим Telegram-ботом вы всегда будете в курсе всех важных событий!\n\n"

        "📅 <b>Уведомления о мероприятиях:</b> Получайте напоминания о предстоящих событиях, "
        "чтобы не пропустить важный матч или тренировку.\n"
        "🔔 <b>Обновления и изменения:</b> Будьте в курсе всех изменений в расписании. "
        "Узнавайте обо всех изменениях первыми.\n\n"
        "Не упустите ни одного важного момента с <b><a href='dev-level.ru'>Prosport Calendar!</a></b>"
    )
    
    # Редактируем предыдущее сообщение
    await callback_query.message.edit_text(
        text=text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"  # Для форматирования текста
    )
    
    # Подтверждаем callback-запрос
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "repeat_request")
async def handle_repeat_request(callback_query: CallbackQuery):
    global events_data
    global events_count
    user_id = callback_query.from_user.id

    # Получаем номер телефона пользователя из базы данных
    conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT phone_number FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()

    conn.close()
    if result is not None:
        phone_number = result[0]

        # Отправляем GET-запрос с user_id и номером телефона
        response = requests.get(f"https://dev-level.ru/api/v1/events-by-phone/{phone_number}")
        # Сохраняем данные в глобальной переменной events_data
        events_data = response.json()  # Обновляем глобальные данные
        print(events_data)
        events_count = len(events_data)  # Количество событий

        print(events_count)

        if response.status_code==200:
            # events_count = response.json().get("events_count", 0)
            keyboard = InlineKeyboardBuilder() 
            keyboard.button(text="Показать все", callback_data="show_all")
            keyboard.button(text="Изменить номер телефона", callback_data="change_phone")
            keyboard.button(text="О нас", callback_data="about_us")
            
            if isinstance(callback_query, CallbackQuery):
                await callback_query.message.edit_text(
                    f"Ваш номер телефона: +{phone_number}\n\n" 
                    f"Количество мероприятий, на которые вы подписаны: <b>{events_count}</b>.",
                    parse_mode="HTML",
                    reply_markup=keyboard.as_markup()
                )
            elif isinstance(callback_query, Message):
                await callback_query.answer(
                    f"Ваш номер телефона: +{phone_number}.\n\n" 
                    f"Количество мероприятий, на которые вы подписаны: <b>{events_count}</b>.",
                    parse_mode="HTML",
                    reply_markup=keyboard.as_markup()
                )
            await callback_query.answer()
        
        else:
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="Повторить", callback_data="repeat_request")
            keyboard.button(text="Изменить номер телефона", callback_data="change_phone")             #ПОМЕНЯЛ
            if callback_query.message.text != "Произошла ошибка при получении информации о мероприятиях. Пожалуйста, попробуйте позже.":
                await callback_query.message.edit_text("Произошла ошибка при получении информации о мероприятиях. Пожалуйста, попробуйте позже и проверьте введенный номер телефона", reply_markup=keyboard.as_markup())
    else:
        await callback_query.message.edit_text("Ваш номер телефона не найден в базе данных. Пожалуйста, отправьте его заново через /start.")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == "show_all")
async def show_all(callback_query: CallbackQuery):
    global events_data
    global events_count

    # Отображаем первое событие из списка eventsData
    current_index = 0
    event = events_data[current_index]

    # Формируем сообщение для текущего события
    message_str = (
        f"<b>Название:</b> {event['name']}\n"
        f"<b>Спорт:</b> {event['sport']}\n"
        f"<b>Дисциплина:</b> {event['discipline']}\n"
        f"<b>Пол и возраст:</b> {event['genderAge']}\n"
        f"<b>Дата:</b> {event['startTime']} - {event['endTime']}\n"
        f"<b>Локация:</b> {event['country']}, {event['location']}\n"
        f"<b>Кол-во участников:</b> {event['participants']}\n"
    )

    # Создаем клавиатуру с кнопками "Следующее" и "Отписаться"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Главная", callback_data="repeat_request")
    if current_index + 1 < len(events_data):
        keyboard.button(text="Следующее", callback_data=f"show_event:{current_index + 1}")

    # Отправляем сообщение
    await callback_query.message.edit_text(message_str, reply_markup=keyboard.as_markup(), parse_mode="HTML")
    await callback_query.answer()


@dp.callback_query(lambda c: c.data.startswith("show_event:"))
async def show_event(callback_query: CallbackQuery):
    global events_data
    global events_count
    # Извлекаем индекс текущего события из callback data
    data = callback_query.data.split(":")
    current_index = int(data[1]) if len(data) > 1 else 0

    # Проверяем индекс и загружаем событие
    if 0 <= current_index < len(events_data):
        event = events_data[current_index]

        # Формируем сообщение для текущего события
        message_str = (
            f"<b>Название:</b> {event['name']}\n"
            f"<b>Спорт:</b> {event['sport']}\n"
            f"<b>Дисциплина:</b> {event['discipline']}\n"
            f"<b>Пол и возраст:</b> {event['genderAge']}\n"
            f"<b>Дата:</b> {event['startTime']} - {event['endTime']}\n"
            f"<b>Локация:</b> {event['country']}, {event['location']}\n"
            f"<b>Кол-во участников:</b> {event['participants']}\n"
        )

        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardBuilder()

        # Добавляем кнопки в зависимости от текущего индекса
        if current_index > 0:
            keyboard.button(text="Назад", callback_data=f"show_event:{current_index - 1}")
        keyboard.button(text="Главная", callback_data="repeat_request")
        if current_index + 1 < len(events_data):
            keyboard.button(text="Следующее", callback_data=f"show_event:{current_index + 1}")


        # Обновляем сообщение
        await callback_query.message.edit_text(message_str, reply_markup=keyboard.as_markup(), parse_mode="HTML")
        await callback_query.answer()
    else:
        # Обработка выхода за пределы массива (не должно происходить)
        await callback_query.answer("Ошибка: Неверный индекс события.", show_alert=True)

# Определяем группу состояний
class ChangePhoneState(StatesGroup):
    waiting_for_phone = State()

@dp.callback_query(lambda c: c.data == "change_phone")
async def change_phone(callback_query: CallbackQuery, state: FSMContext):
    # Отправляем сообщение пользователю
    await callback_query.message.answer("Пожалуйста, отправьте новый номер телефона в формате 7XXXXXXXXXX или 8XXXXXXXXXX.")
    # Устанавливаем состояние ожидания нового номера телефона
    await state.set_state(ChangePhoneState.waiting_for_phone)
    await callback_query.answer()

@dp.message(StateFilter(ChangePhoneState.waiting_for_phone))
async def handle_new_phone(message: Message, state: FSMContext):
    user_id = message.from_user.id
    new_phone = message.text.strip().replace("+", "")  # Удаляем "+" из номера телефона

    # Проверяем формат номера телефона
    if (new_phone.startswith("7") and len(new_phone) == 11 and new_phone.isdigit()) or \
       (new_phone.startswith("8") and len(new_phone) == 11 and new_phone.isdigit()):
        # Сохраняем новый номер телефона в базу данных
        conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET phone_number = ?
            WHERE user_id = ?
        ''', (new_phone, user_id))
        conn.commit()
        conn.close()

        await message.answer("Ваш номер телефона успешно обновлен!", reply_markup=types.ReplyKeyboardRemove())
        await send_event_info(user_id, message)

        # Сбрасываем состояние
        await state.clear()
    else:

        keyboard = InlineKeyboardBuilder() 
        keyboard.button(text="Назад", callback_data="repeat_request")
        await message.answer("Неверный формат номера. Попробуйте снова.", reply_markup=keyboard.as_markup())



@dp.message(F.contact)
async def handle_contact(message: Message):
    user_id = message.from_user.id
    contact = message.contact

    if contact.user_id == user_id:
        # Удаляем символ "+" из номера телефона
        phone_number = contact.phone_number.replace("+", "")
        
        # Save user phone number in the database
        conn = sqlite3.connect(os.path.join(ROOT_DIR, 'user_data.db'))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, phone_number) VALUES (?, ?)
        ''', (user_id, phone_number))
        conn.commit()
        conn.close()

        await message.answer("Ваш номер телефона успешно сохранен!", reply_markup=types.ReplyKeyboardRemove()) #Поменял
        await send_event_info(user_id, message)

    else:
        await message.answer("Пожалуйста, отправьте ваш собственный номер телефона.")



async def main():
    asyncio.create_task(check_and_notify_users())
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())