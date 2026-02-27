import os
import logging
import asyncio
import time
import io
import random
from aiogram import Bot, Dispatcher, types, F
import google.generativeai as genai

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(f'GEMINI_KEY_{i}') for i in range(1, 12)]
KEYS = [k for k in KEYS if k]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека. "
    "Ты не помощница, ты обычный человек в чате. Твоя цель: развлекать и подкалывать людей. "
    "Иногда ты можешь сама вклиниться в разговор или просто кинуть эмодзи, если тебе лень отвечать. "
    "Говори дерзко, как живая и стервозная девушка."
)

bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

# Шансы для рандомных действий
CHANCE_TO_TALK = 0.001    # 1 к 1000 — вклиниться в чат текстом
CHANCE_TO_REACT = 0.0005  # 1 к 2000 — просто поставить эмодзи (реакцию)

SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

@dp.message(F.content_type.in_({'text', 'photo', 'sticker'}))
async def talk_handler(message: types.Message):
    # 1. Защита от старых сообщений
    if message.date.timestamp() < time.time() - 60:
        return 

    user_name = message.from_user.full_name or message.from_user.username or "Челик"
    text_content = message.text or message.caption or (f"[Стикер {message.sticker.emoji}]" if message.sticker else "")
    
    # 2. Проверяем, зовут ли Моти или это ответ ей
    is_mochi = "моти" in text_content.lower()
    my_id = (await bot.get_me()).id
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == my_id
    
    # 3. Рандомные триггеры
    roll = random.random()
    is_random_talk = roll < CHANCE_TO_TALK
    is_random_react = roll < (CHANCE_TO_TALK + CHANCE_TO_REACT) and not is_random_talk

    # 4. Логика реакций (1 к 2000)
    if is_random_react and not (is_mochi or is_reply_to_bot):
        reactions = ["🤡", "🙄", "🤨", "💅", "🥱", "🖕", "💩"]
        try:
            await message.react([types.ReactionTypeEmoji(emoji=random.choice(reactions))])
            logger.info(f"Мотя кинула реакцию на сообщение {user_name}")
        except: pass
        return

    # 5. Если её не звали и рандом на текст не выпал — игнорим
    if not (is_mochi or is_reply_to_bot or is_random_talk):
        return 

    try:
        # Ротация ключей
        current_key = random.choice(KEYS)
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=instructions
        )

        prompt_parts = [f"Пользователь {user_name} написал: {text_content}"]
        if is_random_talk:
            prompt_parts.insert(0, "[ТЫ РЕШИЛА ВКЛИНИТЬСЯ БЕЗ СПРОСА, ПОДКОЛИ ЕГО]")

        if message.photo:
            photo = message.photo[-1]
            file_info = await bot.get_file(photo.file_id)
            photo_buffer = await bot.download_file(file_info.file_path)
            prompt_parts.append({"mime_type": "image/jpeg", "data": photo_buffer.read()})

        # Генерация
        response = model.generate_content(prompt_parts, safety_settings=SAFETY_SETTINGS)
        
        if response.text:
            # Всегда отвечаем реплаем
            await message.reply(response.text)
            
    except Exception as e:
        if "429" in str(e):
            logger.warning("Квота ключа забита, ждем следующего шанса.")
        else:
            logger.error(f"Ошибка: {e}")

async def main():
    logger.info(f"Мотя в эфире! Ключей: {len(KEYS)}, Шанс текста: {CHANCE_TO_TALK}, Шанс реакции: {CHANCE_TO_REACT}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
