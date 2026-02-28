import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Автоматический сбор всех 32+ ключей из настроек Render
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Твоя инструкция (промпт) для Eva (Моти)
instructions = (
    "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать, поведение как у обычного человека. "
    "Твоя цель в чате: развлекать людей своим характером. "
    "Подкалывать людей. Не пиши ** , и другие знаки. Только: ! , ? , . , , : . "
    "Пиши кратко: в 1-5 предложений.можешь материться, оскроблять родителей и т.д"
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

# Веб-сервер для порта 10000, чтобы Render не усыплял бота
async def handle(request):    return web.Response(text=f"Mochi is live. Keys: {len(KEYS)}")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id
    
    # 1. Защита: только твой чат или личка
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        await message.answer("Что за нищий чат? Я не буду тут сидеть. Я выхожу, пишите @satanacIub если это ошибка")
        await bot.leave_chat(message.chat.id)
        return

    # 2. Жесткий фильтр: игнорим всё, что старше 2 секунд
    if message.date.timestamp() < time.time() - 2:
        return 

    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    
    # Шанс 0.1% просто вставить слово (рандом)
    if not (is_mochi or is_reply or random.random() < 0.001):
        return

    try:
        # Выбор случайного ключа для обхода лимита 429
        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        
        response = model.generate_content(f"{message.from_user.first_name}: {text_content}")
        
        if response.text:
            await message.reply(clean_text(response.text))
            
    except Exception as e:
        # Если ошибка 429 (лимит), просто молчим
        if "429" not in str(e):
            logger.error(f"Ошибка: {e}")

async def main():
    global bot_id
    await start_web_server()
    
    # Очищаем очередь старых сообщений при каждом запуске!
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запоминаем ID бота один раз (решает проблему с SSL)
    me = await bot.get_me()
    bot_id = me.id
    
    logger.info(f"Мотя запущена! В обойме {len(KEYS)} ключей.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
