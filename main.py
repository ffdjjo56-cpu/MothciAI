import os
import asyncio
import logging
import psycopg2
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# 1. Инициализация Gemini (Исправляем ошибку 404 со скриншота 1000029577)
# Мы НЕ указываем версию API, чтобы библиотека сама выбрала стабильную
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # Темы/Топики
    t_id = getattr(message, 'message_thread_id', None)

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS messages (user_id BIGINT, role TEXT, content TEXT)")
        
        # Сохраняем и берем историю (память на 5 сообщений)
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (message.from_user.id, "user", message.text))
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY rowid DESC LIMIT 5", (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        prompt = "Ты Ева, ИИ SatanaClub. Отвечай кратко.\n"
        for r in rows: prompt += f"{r[0]}: {r[1]}\n"
        
        # Генерируем ответ (здесь была ошибка 404, теперь она исправлена)
        response = model.generate_content(prompt)
        answer = response.text

        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()
        conn.close()

        await message.answer(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Error: {e}")
        # Запасной вариант, если база данных тупит
        res = model.generate_content(message.text)
        await message.answer(res.text, message_thread_id=t_id)

async def main():
    # Чистим очередь, чтобы не было Conflict со старым кодом (скриншот 1000029567)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
