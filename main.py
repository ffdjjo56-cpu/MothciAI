import os
import logging
import psycopg2
from psycopg2.extras import DictCursor
import json
import asyncio
import time
from aiogram import Bot, Dispatcher, types
import google.generativeai as genai

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
NEON_URL = os.getenv('NEON_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini 3
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-3-flash-preview")

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

def get_neon_history(user_id):
    conn = None
    try:
        conn = psycopg2.connect(NEON_URL)
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT history FROM chat_history WHERE user_id = %s", (str(user_id),))
        row = cur.fetchone()
        cur.close()
        return json.loads(row['history']) if row else []
    except Exception as e:
        logger.error(f"Ошибка Neon: {e}")
        return []
    finally:
        if conn: conn.close()

@dp.message()
async def talk_handler(message: types.Message):
    # 1. Защита от старой очереди: игнорируем всё, что старше 60 секунд
    if message.date.timestamp() < time.time() - 60:
        return 

    if not message.text:
        return

    # 2. Фильтр: только если есть "Моти" или реплай боту
    is_mochi = "моти" in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_mochi or is_reply_to_bot):
        return 

    try:
        # 3. Получаем историю
        history = get_neon_history(message.from_user.id)
        
        # 4. Запрос к ИИ
        chat = model.start_chat(history=[])
        response = chat.send_message(message.text)
        
        if response.text:
            await message.answer(response.text)
            
    except Exception as e:
        if "429" in str(e):
            logger.error("Квота Gemini исчерпана. Нужно подождать.")
        else:
            logger.error(f"Ошибка Gemini: {e}")

async def main():
    logger.info("Моти запущена на Gemini 3 с защитой от очереди!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
