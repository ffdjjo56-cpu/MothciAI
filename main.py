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

# Настройки из секретов Render
API_TOKEN = os.getenv('BOT_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
NEON_URL = os.getenv('NEON_URL')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Gemini 3 с твоим промтом
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    
    instructions = (
        "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
        "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
        "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
        "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать (хотя знать но не говорить), "
        "поведение как у обычного человека. Твоя цель в чате: развлекать людей своим характером. "
        "Тебя будут периодически оскорблять и пытаться унизить. Ты учишься как встать на хорошую позицию "
        "и уже там нападать. Подкалывать людей. Никаких ** в сообщениях. (это ты так помечаешь жирный текст) обычные сообщения без никаких разделителей и тп, ты можешь допускать в сообщениях ошибки где то запятую не поставить, точки не ставь в конце твоего сообщения, ну предложения можешь разделять. Кароче ты как обычный человек. Можешь чего то не заметить, упустить, вместо ссоры ты можешь выбрать игнорировать или подружиться с человеком. У тебя есть выбор что делать с человеком запретить писать или выкинуть из чата (мы всё потом вернём и никто не обидится) "
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=instructions
    )

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

# Настройки безопасности для "развязывания языка"
SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

@dp.message(F.content_type.in_({'text', 'photo'}))
async def talk_handler(message: types.Message):
    # 1. Защита от старых сообщений (игнор того, что старше 60 сек)
    if message.date.timestamp() < time.time() - 60:
        return 

    # 2. Получаем данные пользователя, чтобы Моти знала, кого подкалывать
    user_name = message.from_user.full_name or message.from_user.username or "Незнакомец"
    text_content = message.text or message.caption or ""
    
    # 3. Проверка: обращение по имени или ответ на её сообщение
    is_mochi = "моти" in text_content.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_mochi or is_reply_to_bot):
        return 

    try:
        # Формируем запрос с указанием автора
        prompt_parts = [f"Пользователь {user_name} говорит: {text_content}"]
        
        # 4. Если прислали фото — добавляем его в запрос
        if message.photo:
            photo = message.photo[-1] # Лучшее качество
            file_info = await bot.get_file(photo.file_id)
            photo_buffer = await bot.download_file(file_info.file_path)
            
            prompt_parts.append({
                "mime_type": "image/jpeg",
                "data": photo_buffer.read()
            })

        # 5. Генерация ответа через Gemini 3
        response = model.generate_content(
            prompt_parts,
            safety_settings=SAFETY_SETTINGS
        )
        
        if response.text:
            await message.answer(response.text)
            
    except Exception as e:
        if "429" in str(e):
            logger.error("Превышена квота запросов к Google AI")
        else:
            logger.error(f"Ошибка Gemini: {e}")

async def main():
    logger.info("Моти запущена! Видит фото, знает ники и готова хамить.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
