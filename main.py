import os
import logging
import psycopg2
from psycopg2.extras import DictCursor
import json
import asyncio
from aiogram import Bot, Dispatcher, types
import google.generativeai as genai

# 1. Настройки (Берем из Config Vars на сайте Heroku)
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
NEON_URL = os.getenv('NEON_URL') # Ссылка postgresql://...

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация ИИ
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Функция ТОЛЬКО ЧТЕНИЯ из Neon
def fetch_history_from_neon(user_id):
    try:
        conn = psycopg2.connect(NEON_URL)
        cur = conn.cursor(cursor_factory=DictCursor)
        # Просто забираем то, что записал юзербот
        cur.execute("SELECT history FROM chat_history WHERE user_id = %s", (str(user_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return json.loads(row['history'])
        return []
    except Exception as e:
        logger.error(f"Ошибка чтения из Neon: {e}")
        return []

@dp.message()
async def reader_handler(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return

    # Достаем историю, которую подготовил "писатель" (модуль юзербота)
    history = fetch_history_from_neon(message.from_user.id)
    
    # Формируем промпт. Мы не добавляем текущее сообщение в базу здесь, 
    # так как это работа модуля-писателя.
    prompt = "Ты Моти. Используй историю из базы Neon:\n"
    prompt += "\n".join(history[-50:]) # Берем последние 50 сообщений для контекста
    prompt += f"\nUser: {message.text}\nМоти:"

    try:
        response = model.generate_content(prompt)
        await message.answer(response.text)
    except Exception as e:
        logger.error(f"Gemini error: {e}")

async def main():
    if not all([API_TOKEN, GEMINI_KEY, NEON_URL]):
        logger.error("Проверь секреты на сайте: BOT_TOKEN, GEMINI_KEY, NEON_URL")
        return
    logger.info("Моти-читатель запущена и подключена к Neon.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
