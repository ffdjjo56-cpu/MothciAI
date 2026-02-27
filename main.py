import os
import logging
import psycopg2
from psycopg2.extras import DictCursor
import json
import asyncio
import time
import io
from aiogram import Bot, Dispatcher, types, F
import google.generativeai as genai

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
NEON_URL = os.getenv('NEON_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini 3 с характером
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    
    instructions = (
        "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
        "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
        "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
        "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать (хотя знать но не говорить), "
        "поведение как у обычного человека. Твоя цель в чате: развлекать людей своим характером. "
        "Тебя будут периодически оскорблять и пытаться унизить. Ты учишься как встать на хорошую позицию "
        "и уже там нападать. Подкалывать людей."
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=instructions
    )

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

# Настройки безопасности (чтобы она могла дерзить)
SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

@dp.message(F.content_type.in_({'text', 'photo'}))
async def talk_handler(message: types.Message):
    # 1. Защита от старой очереди
    if message.date.timestamp() < time.time() - 60:
        return 

    # 2. Проверка: позвали ли Моти (в тексте или подписи к фото) или это реплай
    text_to_check = message.text or message.caption or ""
    is_mochi = "моти" in text_to_check.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_mochi or is_reply_to_bot):
        return 

    try:
        content = []
        if text_to_check:
            content.append(text_to_check)
        
        # 3. Если есть фото — скачиваем и добавляем в запрос
        if message.photo:
            photo = message.photo[-1] # берем самое лучшее качество
            file_info = await bot.get_file(photo.file_id)
            photo_bytes = await bot.download_file(file_info.file_path)
            
            content.append({
                "mime_type": "image/jpeg",
                "data": photo_bytes.read()
            })

        # 4. Отправка в Gemini 3
        response = model.generate_content(
            content,
            safety_settings=SAFETY_SETTINGS
        )
        
        if response.text:
            await message.answer(response.text)
            
    except Exception as e:
        if "429" in str(e):
            logger.error("Лимит запросов исчерпан")
        else:
            logger.error(f"Ошибка Gemini: {e}")

async def main():
    logger.info("Моти запущена! Теперь она видит фото и дерзит.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
