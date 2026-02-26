import os
import asyncio
import logging
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from groq import Groq

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Подключение к Neon (PostgreSQL)
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Создание таблицы (если её нет)
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
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
    user_id = message.from_user.id
    user_text = message.text

    # Сохраняем сообщение пользователя
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (user_id, "user", user_text))
    
    # Получаем историю (последние 10 сообщений)
    cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY timestamp DESC LIMIT 10", (user_id,))
    history = [{"role": row[0], "content": row[1]} for row in cur.fetchall()][::-1]
    
    # Запрос к Groq (Eva)
    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": "Твоё имя Ева. Ты помощник проекта SatanaCIub Project."}] + history
    )
    answer = response.choices[0].message.content

    # Сохраняем ответ бота
    cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (user_id, "assistant", answer))
    conn.commit()
    cur.close()
    conn.close()

    await message.answer(answer)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
