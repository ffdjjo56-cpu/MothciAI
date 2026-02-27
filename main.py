import os
import logging
import asyncio
import time
import random
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web  # Добавили для обхода ошибки портов
import google.generativeai as genai

# Инициализация
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(f'GEMINI_KEY_{i}') for i in range(1, 12)]
KEYS = [k for k in KEYS if k]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = "Ты – Моти. Стервозная, дерзкая. Отвечаешь коротко. Ты в чате, чтобы всех бесить."

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ЗАГЛУШКА ДЛЯ ПОРТА (Чтобы Free тариф не вылетал) ---
async def handle(request):
    return web.Response(text="Mochi is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render сам подставит порт в переменную PORT
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# --- ЛОГИКА БОТА ---
@dp.message(F.content_type.in_({'text', 'photo', 'sticker'}))
async def talk_handler(message: types.Message):
    if message.date.timestamp() < time.time() - 10:
        return 

    text_content = message.text or message.caption or ""
    is_mochi = "моти" in text_content.lower()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == (await bot.get_me()).id
    
    roll = random.random()
    if not (is_mochi or is_reply or roll < 0.0015):
        return

    try:
        genai.configure(api_key=random.choice(KEYS))
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        response = model.generate_content(f"{message.from_user.first_name}: {text_content}")
        if response.text:
            await message.reply(response.text)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

async def main():
    # Запускаем и сервер для порта, и бота одновременно
    await start_web_server()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
