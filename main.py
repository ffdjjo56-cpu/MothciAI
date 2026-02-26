import os
import asyncio
import logging
import psycopg2
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Настройка Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

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
    if not message.text: return
    user_id = message.from_user.id
    thread_id = message.message_thread_id

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (user_id, "user", message.text))
        conn.commit()

        # Получаем историю
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY timestamp DESC LIMIT 10", (user_id,))
        rows = cur.fetchall()[::-1]
        
        # Собираем промпт (самый надежный способ для Gemini сейчас)
        prompt = "Ты — Ева, помощник проекта SatanaClub. Отвечай кратко.\n"
        for row in rows:
            prefix = "Пользователь: " if row[0] == "user" else "Ева: "
            prompt += f"{prefix}{row[1]}\n"
        prompt += "Ева:"

        # ВЫЗОВ МОДЕЛИ (Именно этот формат решает ошибку 404)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        answer = response.text

        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (user_id, "model", answer))
        conn.commit()
        cur.close()
        conn.close()

        await message.answer(answer, message_thread_id=thread_id)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("Ева на мгновение задумалась, попробуй еще раз!", message_thread_id=thread_id)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
