import os
import asyncio
import logging
import psycopg2
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и Gemini
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Настройка Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Функция подключения к Neon (PostgreSQL)
def get_db_connection():
    # Используем переменную DATABASE_URL, где ты исправил 'p' на маленькую
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Создание таблицы при запуске
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@dp.message()
async def chat_handler(message: types.Message):
    # Игнорируем сообщения без текста
    if not message.text:
        return

    user_id = message.from_user.id
    user_text = message.text
    # Сохраняем thread_id для ответов в темах (topics)
    thread_id = message.message_thread_id

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Сохраняем сообщение пользователя в базу
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (user_id, "user", user_text))
        conn.commit()

        # 2. Получаем историю (последние 10 сообщений) для контекста
        cur.execute("""
            SELECT role, content FROM messages 
            WHERE user_id = %s 
            ORDER BY timestamp DESC LIMIT 10
        """, (user_id,))
        history_rows = cur.fetchall()[::-1]
        
        # Форматируем историю для Gemini
        history = []
        for row in history_rows:
            role = "user" if row[0] == "user" else "model"
            history.append({"role": role, "parts": [row[1]]})

        # 3. Запрос к Gemini
        # Мы заменили Groq, так как старая модель была отключена
        chat = model.start_chat(history=history)
        system_instruction = "Твоё имя Ева. Ты помощник проекта SatanaCIub Project. Отвечай дружелюбно и помогай пользователям."
        
        response = chat.send_message(f"{system_instruction}\nПользователь: {user_text}")
        answer = response.text

        # 4. Сохраняем ответ бота в базу
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (user_id, "model", answer))
        conn.commit()
        
        cur.close()
        conn.close()

        # Отправляем ответ (с учетом темы/топика, если он есть)
        await message.answer(answer, message_thread_id=thread_id)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        # Если база выдает ошибку, бот все равно ответит, но без истории
        chat = model.start_chat(history=[])
        response = chat.send_message(user_text)
        await message.answer(response.text, message_thread_id=thread_id)

async def main():
    # Удаляем вебхук перед запуском, чтобы не было конфликтов
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
