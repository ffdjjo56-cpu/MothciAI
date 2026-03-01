import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiohttp import web
import google.generativeai as genai

# Инициализация
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

# Статистика ключей
key_stats = {i: {"used": 0, "status": "✅"} for i in range(len(KEYS))}
last_reset = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Твой пол: Женский. "
    "Характер: Строгая, подкалываешь людей. Не пиши **. "
    "Используй только: ! , ? , . , , : . Кратко: 1-5 предложений."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:]', '', text)

async def handle(request):
    return web.Response(text="Mochi System: Online")

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
    global bot_id, last_reset
    
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        return
    if message.date.timestamp() < time.time() - 2:
        return 

    text_lower = (message.text or message.caption or "").lower()

    # СБРОС ЛИМИТОВ РАЗ В МИНУТУ
    if time.time() - last_reset > 60:
        for i in range(len(KEYS)):
            key_stats[i]["used"] = 0
            if key_stats[i]["status"] == "🚫": key_stats[i]["status"] = "✅"
        last_reset = time.time()

    # КОМАНДА: МОТИ КЛЮЧИ (HTML blockquote)
    if "моти ключи" in text_lower:
        header = "📊 <b>Статус ключей (за минуту):</b>\n"
        body = "<blockquote>"
        total_left = 0
        for i in range(len(KEYS)):
            left = max(0, 20 - key_stats[i]["used"])
            body += f"{i+1} ключ = {left} зап. / {key_stats[i]['status']}\n"
            total_left += left
        body += "</blockquote>"
        footer = f"\n<b>Всего осталось: {total_left} запросов/мин</b>"
        await message.reply(header + body + footer, parse_mode="HTML")
        return

    # КОМАНДА: МОТИ ПИНГ
    if "моти пинг" in text_lower:
        ping_ms = int((time.time() - message.date.timestamp()) * 1000)
        await message.reply(f"<code>Пинг: {ping_ms}ms</code>\nЖивая я, че пристали.", parse_mode="HTML")
        return

    is_mochi = "моти" in text_lower
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    
    if not (is_mochi or is_reply_to_bot or random.random() < 0.001):
        return

    idx = random.randint(0, len(KEYS) - 1)
    try:
        genai.configure(api_key=KEYS[idx])
        # УСТАНОВЛЕНА МОДЕЛЬ GEMINI 3 FLASH
        model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
        
        sender = message.from_user.first_name
        if message.reply_to_message and message.reply_to_message.from_user.id != bot_id:
            target = message.reply_to_message.from_user.first_name
            prompt = f"Обратись к {sender} и к {target}. {sender} ответил на {target}. Текст: {message.text}"
        else:
            prompt = f"{sender}: {message.text}"

        response = model.generate_content(prompt)
        if response.text:
            key_stats[idx]["used"] += 1
            await message.reply(clean_text(response.text))
            
    except Exception as e:
        if "429" in str(e): 
            key_stats[idx]["status"] = "🚫"
        logger.error(f"Error: {e}")

async def main():
    global bot_id
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info(f"Мотя на Gemini 3 Flash запущена!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
