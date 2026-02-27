import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Собираем абсолютно все ключи, которые ты добавил в Render
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668
bot_id = None # Переменная для хранения ID бота, чтобы не было ошибок SSL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Твой промт без изменений
instructions = (
    "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать, поведение как у обычного человека. "
    "Твоя цель в чате: развлекать людей своим характером. "
    "Подкалывать людей. Не пиши ** , и другие знаки. Только: ! , ? , . , , : . "
    "Пиши кратко: в 1-5 предложений."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Чистим текст от запрещенных символов
def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

# Веб-сервер для удержания сервиса в сети на Render
async def handle(request):
    return web.Response(text=f"Mochi is active with {len(KEYS)} keys")

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

    # 2. Игнорим старье при лагах (фильтр 7 секунд)
    if message.date.timestamp() < time.time() - 7:
        return 

    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    
    # Проверка реплая по сохраненному ID (решает проблему TelegramNetworkError)
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    
    # Шанс 1 к 1000 просто влезть в разговор
    roll = random.random()
    if not (is_mochi or is_reply or roll < 0.001):
        return

    try:
        # Случайный ключ из 32 доступных
        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        
        response = model.generate_content(f"{message.from_user.first_name} пишет: {text_content}")
        
        if response.text:
            await message.reply(clean_text(response.text))
            
    except Exception as e:
        if "429" in str(e):
            logger.warning("Один из ключей исчерпал лимит (429).")
        else:
            logger.error(f"Ошибка: {e}")

async def main():
    global bot_id
    await start_web_server()
    
    # Чистим очередь сообщений при запуске
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запоминаем ID бота ОДИН раз при старте
    me = await bot.get_me()
    bot_id = me.id
    
    logger.info(f"Мотя (ID: {bot_id}) запущена! Ключей в обойме: {len(KEYS)}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
