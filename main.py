import os
import asyncio
import logging
import psycopg2
import re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramConflictError, TelegramBadRequest

# Настройка логирования для отслеживания статуса в Render
logging.basicConfig(level=logging.INFO)

# 1. Настройка Gemini (Исправляем 404/v1beta из логов)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# 2. Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    """Подключение к базе данных Neon (PostgreSQL)"""
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    # Игнорируем сообщения без текста
    if not message.text:
        return
    
    # ПРОВЕРКА АКТИВАЦИИ (Твое условие)
    # 1. Проверяем наличие имени "Моти" в тексте
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    # 2. Проверяем, является ли это ответом на сообщение бота
    is_reply = False
    if message.reply_to_message and message.reply_to_message.from_user:
        is_reply = message.reply_to_message.from_user.id == bot.id

    # Если бота не звали и это не ответ ему — просто молчим
    if not (is_called or is_reply):
        return

    # Получаем thread_id для групп с темами (исправляет KeyError из логов)
    t_id = getattr(message, 'message_thread_id', None)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # ИСПРАВЛЕНИЕ БАЗЫ: Принудительно создаем таблицу с колонкой 'id' 
        # (это лечит ошибку "column id does not exist" со скриншота 1000029592)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        # На всякий случай добавляем колонку, если таблица уже была создана старым кодом
        cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY")
        
        # Сохраняем сообщение пользователя
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # Загружаем краткую историю (последние 5 сообщений)
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 5", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        # Формируем промпт для Евы
        prompt = "Ты Ева (тебя зовут Моти), ИИ-ассистент проекта SatanaClub. Отвечай кратко и харизматично.\n"
        for r in rows:
            prompt += f"{r[0]}: {r[1]}\n"
        
        # Генерируем ответ
        response = model.generate_content(prompt)
        answer = response.text

        # Сохраняем ответ бота в базу
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()

        # Отвечаем пользователю (через reply, чтобы было красиво)
        try:
            await message.reply(answer, message_thread_id=t_id)
        except Exception:
            await message.answer(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Ошибка в chat_handler: {e}")
        # Резервный ответ, если база данных временно недоступна
        try:
            res = model.generate_content(message.text)
            await message.reply(res.text, message_thread_id=t_id)
        except:
            pass
    finally:
        if conn:
            conn.close()

async def main():
    # Очищаем очередь обновлений, чтобы избежать ConflictError (скриншот 1000029593)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Моти запущена и готова к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
