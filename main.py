import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Настройки
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(f'GEMINI_KEY_{i}') for i in range(1, 12)]
KEYS = [k for k in KEYS if k]

# ID твоего основного чата
ALLOWED_CHAT_ID = -1002719419668

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Ты имеешь  право  материться  и оскорблять как угодно. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать, поведение как у обычного человека. "
    "Твоя цель в чате: развлекать людей своим характером. "
    "Подкалывать людей. Не пиши ** , и другие знаки. Только: ! , ? , . , , : . "
    "Пиши кратко: в 1-5 предложений."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

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

# --- ПРОВЕРКА ЧАТА ---
@dp.message()
async def check_chat_and_talk(message: types.Message):
    # 1. Если это не наш чат и не личка с админом
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        # Пишем фразу и выходим
        await message.answer("Что за нищий чат? Я не буду тут сидеть. Я выхожу, пишите @satanacIub если это ошибка")
        await bot.leave_chat(message.chat.id)
        return

    # 2. Фильтр старых сообщений
    if message.date.timestamp() < time.time() - 10:
        return 

    # 3. Логика ответов (текст, фото, стикеры)
    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    bot_info = await bot.get_me()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    roll = random.random()
    if not (is_mochi or is_reply or roll < 0.0015):
        return

    try:
        if roll < 0.0005 and not (is_mochi or is_reply):
            await message.react([types.ReactionTypeEmoji(emoji=random.choice(["🤡", "💅", "🙄", "🖕"]))])
            return

        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        response = model.generate_content(f"{message.from_user.first_name} пишет: {text_content}")
        
        if response.text:
            await message.reply(clean_text(response.text))
    except Exception as e:
        logger.error(f"Ошибка: {e}")

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True) # Чистим очередь
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
