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
    # Используем 1.5 Flash для стабильности лимитов
    model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

# Функция безопасного чтения истории из Neon
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
        logger.error(f"Ошибка чтения Neon: {e}")
        return []
    finally:
        if conn: conn.close()

@dp.message()
async def talk_handler(message: types.Message):
    if not message.text:
        return

    # Логика фильтрации: отвечаем только на "Моти" или реплы боту
    is_mochi = "моти" in message.text.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_mochi or is_reply_to_bot):
        return # Просто игнорируем, не тратим квоту Google

    try:
        # Получаем историю из Neon
        history = get_neon_history(message.from_user.id)
        
        # Формируем запрос к ИИ
        chat = model.start_chat(history=[]) # Можно расширить до передачи истории
        response = chat.send_message(message.text)
        
        if response.text:
            await message.answer(response.text)
            
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            logger.error("Лимит запросов исчерпан (Quota Exceeded)")
        else:
            logger.error(f"Gemini error: {e}")

async def main():
    logger.info("Моти-читатель успешно запущен на Render!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
