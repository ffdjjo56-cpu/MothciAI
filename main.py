import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(f'GEMINI_KEY_{i}') for i in range(1, 12)]
KEYS = [k for k in KEYS if k]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТВОЙ ОБНОВЛЕННЫЙ ПРОМТ
instructions = (
    "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать, поведение как у обычного человека. "
    "Твоя цель в чате: развлекать людей своим характером. Тебя будут периодически оскорблять и пытаться унизить. "
    "Ты учишься как встать на хорошую позицию и уже там нападать. Подкалывать людей. "
    "ВАЖНОЕ ПРАВИЛО: Не пиши ** , и другие знаки. Используй только: ! , ? , . , , : . "
    "Ты не всегда злишься. Можешь ответить как угодно. Пиши кратко: в 1-5 предложений."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Функция для очистки текста от запрещенных знаков (типа **)
def clean_text(text):
    # Убираем все символы, кроме разрешенных (буквы, цифры, пробелы и !?,.:)
    return re.sub(r'[^\w\s!?,.:]', '', text)

# Заглушка для порта Render
async def handle(request):
    return web.Response(text="Mochi is live")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

@dp.message(F.content_type.in_({'text', 'photo', 'sticker'}))
async def talk_handler(message: types.Message):
    # Игнорируем старые сообщения (фильтр 10 секунд)
    if message.date.timestamp() < time.time() - 10:
        return 

    text_content = message.text or message.caption or ""
    user_name = message.from_user.first_name
    
    is_mochi = "моти" in text_content.lower()
    bot_info = await bot.get_me()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    # Шанс 1 к 1000 на рандомный ответ и 1 к 2000 на реакцию
    roll = random.random()
    if not (is_mochi or is_reply or roll < 0.0015):
        return

    try:
        # Реакция на удачу
        if roll < 0.0005 and not (is_mochi or is_reply):
            await message.react([types.ReactionTypeEmoji(emoji=random.choice(["🤡", "💅", "🙄", "🖕"]))])
            return

        # Выбор случайного ключа
        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        
        response = model.generate_content(f"{user_name} пишет: {text_content}")
        
        if response.text:
            final_text = clean_text(response.text)
            # Отвечаем реплаем
            await message.reply(final_text)
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")

async def main():
    logger.info("Запуск Моти...")
    await start_web_server()
    # Удаляем старые сообщения при старте, чтобы не виснуть
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
