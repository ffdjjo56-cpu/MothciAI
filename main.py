import os
import asyncio
import logging
import psycopg2
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Настройка Gemini (Исправлено для устранения ошибки 404)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Используем стабильную модель без лишних параметров v1beta
model = genai.GenerativeModel("gemini-1.5-flash")

# Подключение к Neon
def get_db_connection():
    # Твоя ссылка уже работает (с маленькой буквы 'p')
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Инициализация таблицы
def init_db():
    try:
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
        logging.info("База данных Neon подключена успешно!")
    except Exception as e:
        logging.error(f"Ошибка базы: {e}")

init_db()

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text:
        return

    user_id = message.from_user.id
    user_text = message.text
    thread_id = message.message_thread_id

    try:
        # 1. Работа с базой Neon
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Сохраняем входящее
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (user_id, "user", user_text))
        conn.commit()

        # Получаем историю (последние 10 сообщений)
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY timestamp DESC LIMIT 100", (user_id,))
        history_rows = cur.fetchall()[::-1]
        
        # Собираем контекст для Евы
        context = "Твоё имя Ева. Ты помощник проекта SatanaCIub Project. Отвечай кратко и по делу.\n"
        for row in history_rows:
            context += f"{'Пользователь' if row[0] == 'user' else 'Ева'}: {row[1]}\n"

        # 2. Запрос к Gemini (упрощенный вызов для стабильности)
        response = model.generate_content(f"{context}\nПользователь: {user_text}\nЕва:")
        answer = response.text

        # 3. Сохраняем ответ в базу
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (user_id, "model", answer))
        conn.commit()
        cur.close()
        conn.close()

        # Отправляем ответ
        await message.answer(answer, message_thread_id=thread_id)

    except Exception as e:
        logging.error(f"Ошибка в обработчике: {e}")
        # Запасной вариант если база упадет
        response = model.generate_content(user_text)
        await message.answer(response.text, message_thread_id=thread_id)

async def main():
    # Очистка очереди (убирает Conflict Error)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
