import os
import logging
import sqlite3
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai

# 1. Загрузка настроек из секретов (Config Vars)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')

# Настройка логирования для отслеживания работы
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Инициализация ИИ Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    logger.error("GEMINI_KEY не найден в секретах!")

# 3. Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# 4. Работа с локальной базой SQLite (используем твои 24GB диска)
DB_PATH = 'moti_memory.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS history 
                      (user_id INTEGER PRIMARY KEY, data TEXT)''')
    conn.commit()
    conn.close()

def get_history(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM history WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else []
    except Exception as e:
        logger.error(f"Ошибка чтения базы: {e}")
        return []

def save_history(user_id, history):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Лимит 150 сообщений — твои 24GB RAM это даже не заметят
        history = history[-150:] 
        cursor.execute("INSERT OR REPLACE INTO history (user_id, data) VALUES (?, ?)",
                       (user_id, json.dumps(history)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка записи в базу: {e}")

# 5. Обработчик сообщений
@dp.message()
async def chat_handler(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return

    user_id = message.from_user.id
    history = get_history(user_id)
    
    # Добавляем новое сообщение в историю
    history.append(f"user: {message.text}")
    
    try:
        # Формируем контекст для Gemini
        prompt = "Ты Моти, ИИ-помощник SatanaClub. Будь дружелюбной и остроумной. Твоя история:\n" 
        prompt += "\n".join(history) + "\nМоти:"
        
        # Генерация ответа через Google AI
        response = model.generate_content(prompt)
        answer = response.text
        
        # Сохраняем ответ в историю
        history.append(f"model: {answer}")
        save_history(user_id, history)
        
        await message.answer(answer)
        
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        # Не спамим ошибкой в чат, если API временно недоступно

# 6. Запуск бота
async def main():
    logger.info("Моти запускается на локальной базе SQLite...")
    init_db()
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
