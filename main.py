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
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Создаем таблицу
try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS messages (id SERIAL PRIMARY KEY, user_id BIGINT, role TEXT, content TEXT)")
    conn.commit()
    cur.close()
    conn.close()
except Exception as e:
    logging.error(f"DB Error: {e}")

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # Исправляем работу с темами (topics)
    t_id = message.message_thread_id if message.chat.type in ['group', 'supergroup'] else None

    try:
        # Сохраняем в Neon
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (message.from_user.id, "user", message.text))
        conn.commit()

        # История (последние 5 для скорости)
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 5", (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        prompt = "Ты Ева, помощник SatanaClub. Отвечай кратко.\n"
        for r in rows: prompt += f"{r[0]}: {r[1]}\n"
        
        # Запрос к Gemini
        response = model.generate_content(prompt)
        answer = response.text

        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()
        conn.close()

        await message.answer(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Final Error: {e}")
        res = model.generate_content(message.text)
        await message.answer(res.text, message_thread_id=t_id)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
