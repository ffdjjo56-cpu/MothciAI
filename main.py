import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Автоматический сбор всех ключей из Environment Variables
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать, поведение как у обычного человека. "
    "Твоя цель в чате: развлекать людей своим характером. "
    "Подкалывать людей. Не пиши ** , и другие знаки. Только: ! , ? , . , , : . "
    "Пиши кратко: в 1-5 предложений. Ты можешь материться. Так же ты можешь выбрать для каждого человека какой быть, если тебе сначала ответили спокойно без оскорблений и стёбов то ты можешь так же ответить, так же спокойно но это твой выбор. Я твоя создательница #2 | mrk && stnc. "
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

# Веб-сервер для порта 10000
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
    # Защита от чужих чатов
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        await message.answer("Что за нищий чат? Я выхожу, пишите @satanacIub если это ошибка")
        await bot.leave_chat(message.chat.id)
        return

    # Фильтр времени: игнорируем старое при лагах
    if message.date.timestamp() < time.time() - 7:
        return 

    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    bot_info = await bot.get_me()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    # Шанс рандомного ответа
    roll = random.random()
    if not (is_mochi or is_reply or roll < 0.001):
        return

    try:
        # Берем случайный ключ из твоих 32
        current_key = random.choice(KEYS)
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        
        response = model.generate_content(f"{message.from_user.first_name} пишет: {text_content}")
        
        if response.text:
            await message.reply(clean_text(response.text))
            
    except Exception as e:
        if "429" in str(e):
            logger.warning("Один из ключей исчерпал лимит, пробую выжить...")
        else:
            logger.error(f"Ошибка: {e}")

async def main():
    await start_web_server()
    # Очистка очереди при старте
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"Мотя запущена! Ключей в обойме: {len(KEYS)}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
