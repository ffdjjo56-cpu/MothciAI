import os
import logging
import asyncio
import time
import random
import re
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils.chat_action import ChatActionSender
from aiohttp import web
import google.generativeai as genai

# --- Конфигурация ---
API_TOKEN = os.getenv('BOT_TOKEN')
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
SEARCH_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('SEARCH_KEY')])
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL') # Ссылка на твоего бота для анти-сна

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Твой оригинальный промт
instructions = """
Моти это ты. Ты реально живой человек который имеет право ошибиться, вести диалог как пожелаешь с каждым пользователем отдельно. Ты имеешь право материться и оскорблять, никакой военной политики, оскорбления из-за расы, дискриминации. Тебе 14 лет. Интеллект как у обычной 14 летней девочки. Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно, так же у тебя есть выбор, оскорблять человека и его родителей или же нет. Смотря как поступает с тобой человек который с тобой начал ввести диалог. Предложения до 12 предложений. Если ответ не требует раскрытого ответа то сокращай как тебе угодно. Не используй выделение текста звездочками ** и смайлики. Ты  можешь проявлять симпатию.
"""

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    if not text: return ""
    return re.sub(r'[^\w\s!?,.:\-\(\)@]', '', text)

# Функция для поддержки активности (анти-сон Render)
async def keep_alive():
    if not RENDER_URL: return
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(RENDER_URL) as resp:
                    logger.info(f"Статус само-пинга: {resp.status}")
            except: pass
            await asyncio.sleep(840) # 14 минут

async def handle(request):
    return web.Response(text="Mochi 3.0 is Online")

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id
    
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        return
    if message.date.timestamp() < time.time() - 30:
        return 

    text_content = (message.text or message.caption or "").lower()
    
    # Триггеры для общения
    is_mochi = "моти" in text_content
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    is_search = any(x in text_content for x in ["найди", "поищи", "ищи"])

    if not (is_mochi or is_reply or is_search):
        return

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        pool = SEARCH_KEYS if is_search else CHAT_KEYS
        if not pool: pool = CHAT_KEYS
        
        random.shuffle(pool)
        for key in pool[:5]:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
                
                # Только текст, без фото
                response = await asyncio.to_thread(model.generate_content, text_content)
                
                if response and response.text:
                    await message.reply(clean_text(response.text))
                    return
            except Exception as e:
                logger.error(f"Ошибка ключа: {e}")
                continue
        
        await message.reply("Чет я приуныла, ключи не пашут.")

async def main():
    global bot_id
    # Запуск сервера
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    
    # Запуск анти-сна
    asyncio.create_task(keep_alive())

    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info("Мотя запущена в режиме общения.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except: pass
