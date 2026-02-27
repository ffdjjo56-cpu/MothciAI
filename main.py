import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Собираем все 32 ключа
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за больное, но можешь ответить нормально. "
    "Цель: развлекать людей, подкалывать. Не пиши **. "
    "Используй только: ! , ? , . , , : . Кратко: 1-5 предложений. Можешь материться, ругаться как хочешь. Т больше говори про маму. если тебе пишет Ded melovchenco то иногда упоминай его маму в вк (типа: не хочешь написать своей маме в вк?) "
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

async def handle(request):
    return web.Response(text=f"Mochi status: Active with {len(KEYS)} keys")

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
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        await message.answer("Что за нищий чат? Я выхожу.")
        await bot.leave_chat(message.chat.id)
        return

    # Игнорируем всё, что старше 5 секунд (чтобы не копить очередь)
    if message.date.timestamp() < time.time() - 5:
        return 

    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    
    if not (is_mochi or is_reply or random.random() < 0.001):
        return

    try:
        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        response = model.generate_content(f"{message.from_user.first_name} пишет: {text_content}")
        
        if response.text:
            await message.reply(clean_text(response.text))
    except Exception as e:
        if "429" not in str(e): # Не спамим в логи ошибку квоты
            logger.error(f"Ошибка: {e}")

async def main():
    global bot_id
    await start_web_server()
    # ЭТА СТРОЧКА ОЧИЩАЕТ ОЧЕРЕДЬ СТАРЫХ СООБЩЕНИЙ
    await bot.delete_webhook(drop_pending_updates=True)
    
    me = await bot.get_me()
    bot_id = me.id
    
    logger.info(f"Мотя запущена с {len(KEYS)} ключами!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
