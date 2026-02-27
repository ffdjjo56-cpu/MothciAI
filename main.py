import os
import logging
import psycopg2
from psycopg2.extras import DictCursor
import json
import asyncio
from aiogram import Bot, Dispatcher, types
import google.generativeai as genai

# Подтягиваем секреты из настроек Render
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
NEON_URL = os.getenv('NEON_URL') 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash-latest")

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

# Функция безопасного чтения из Neon
def get_neon_history(user_id):
    conn = None
    try:
        conn = psycopg2.connect(NEON_URL)
        cur = conn.cursor(cursor_factory=DictCursor)
        # Ищем историю, которую записал юзербот
        cur.execute("SELECT history FROM chat_history WHERE user_id = %s", (str(user_id),))
        row = cur.fetchone()
        cur.close()
        return json.loads(row['history']) if row else []
    except Exception as e:
        logger.error(f"Ошибка чтения Neon: {e}")
        return []
    finally:
        if conn: conn.close()

@dp.message()
async def talk_handler(message: types.Message):
    if not message.text or message.text.startswith('/') or not bot:
        return

    # 1. Читаем то, что подготовил юзербот-писатель в Neon
    history = get_neon_history(message.from_user.id)
    
    # 2. Формируем контекст (последние 100 сообщений)
    context = "\n".join(history[-100:])
    prompt = f"Ты Моти, ИИ SatanaClub. Твоя память из Neon:\n{context}\n\nUser: {message.text}\nМоти:"

    try:
        # 3. Генерируем ответ без записи (чтобы не дублировать юзербота)
        response = model.generate_content(prompt)
        await message.answer(response.text)
    except Exception as e:
        logger.error(f"Gemini error: {e}")

async def main():
    if not all([API_TOKEN, GEMINI_KEY, NEON_URL]):
        logger.error("ОШИБКА: Заполни BOT_TOKEN, GEMINI_KEY и NEON_URL в Environment Variables!")
        return
    logger.info("Моти-читатель успешно запущен на Render!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
