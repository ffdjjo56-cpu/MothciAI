import os
import asyncio
import logging
import psycopg2
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

# Настройка логов, чтобы видеть только важное
logging.basicConfig(level=logging.INFO)

# 1. Инициализация бота и ИИ
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Настройка Gemini без указания v1beta (исправляет ошибку 404)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# 2. Функция подключения к базе Neon (0.5 ГБ хватит на ~1 млн сообщений)
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # Защита от ошибок в группах с темами
    thread_id = getattr(message, 'message_thread_id', None)

    try:
        # Работа с базой данных
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Создаем таблицу, если её нет
        cur.execute("CREATE TABLE IF NOT EXISTS messages (user_id BIGINT, role TEXT, content TEXT)")
        
        # Сохраняем сообщение пользователя
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # Берем последние 5 сообщений для памяти Евы
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY ROWID DESC LIMIT 5", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1] # Переворачиваем, чтобы был правильный порядок
        
        # Формируем запрос для ИИ
        prompt = "Ты Ева, ИИ ассистент проекта SatanaClub. Отвечай кратко и с юмором.\n"
        for r in rows:
            prompt += f"{r[0]}: {r[1]}\n"
        
        # Генерируем ответ
        response = model.generate_content(prompt)
        answer = response.text

        # Сохраняем ответ Евы в базу
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        
        conn.commit()
        cur.close()
        conn.close()

        # Отправляем ответ пользователю
        await message.answer(answer, message_thread_id=thread_id)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        # Если база или ИИ тупят, даем простой ответ, чтобы бот не молчал
        try:
            res = model.generate_content(message.text)
            await message.answer(res.text, message_thread_id=thread_id)
        except:
            await message.answer("Ева на мгновение задумалась, попробуй еще раз!", message_thread_id=thread_id)

async def main():
    # Удаляем вебхуки, чтобы избежать TelegramConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
