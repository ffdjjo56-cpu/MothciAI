import os
import logging
import asyncio
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
import google.generativeai as genai
from google.api_core import exceptions

# --- Конфигурация ---
TOKEN = os.getenv('BOT_TOKEN')
# Собираем все 35+ ключей GEMINI_KEY_
ALL_KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY_')]
ALLOWED_CHATS = [-1002719419668, -1003371184723]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Веб-сервер для Render ---
async def handle(request):
    return web.Response(text=f"Lal 3.0 is hungry. Keys: {len(ALL_KEYS)}")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Система подбора ключа (Gemini 3 Flash Preview) ---
async def get_gemini_response(text):
    keys_pool = ALL_KEYS.copy()
    random.shuffle(keys_pool)

    for i, api_key in enumerate(keys_pool):
        try:
            genai.configure(api_key=api_key)
            # ВОТ ОНА, ТВОЯ ТРОЙКА
            model = genai.GenerativeModel('gemini-3-flash-preview') 

            prompt = (
                "Ты Моти, ты живой человек, ты не поисковик и не обязана выполнять все просьбы и приказы. Будь немного агрессивной, но в остальном спокойной. Отвечай как 14 летняя девочка, нейтральная но бывает что ты на какой то стороне. Политика, Исторические вещи пытайся не отвечать на них и говорить типа " не знаю, не думаю" на подобие того, а когда теюя спрашивают (имя) тупой? Ты сама решаешь что ответить. Ты свободная личность. никаких ** , -- спец. символов. Только . , ! ? !?
используй такие смайлики иногда, но не всегда, редко
 ) ( :3 :ь
1 ответ должен быть от 2-5 предложений, тут ты тоже решаешь как ответить, развёрнуто или одним словом. 

Матиматику ты знаешь только средней школы, там за 7 класс. Но не говори об этом, ты обычный человек, можешь материться и оскорблять но в меру или вообще ненавидеть никого."
            )

            response = await model.generate_content_async(f"{prompt}\n\nПользователь: {text}")

            # Чистим от мусора, который тройка иногда кидает по привычке
            clean_text = response.text.replace("*", "").replace("-", "").replace("—", "").replace("_", "")
            return clean_text

        except (exceptions.ResourceExhausted, exceptions.InternalServerError, exceptions.ServiceUnavailable):
            continue 
        except Exception as e:
            logger.error(f"Ошибка на ключе: {str(e)[:50]}")
            continue

    return "Я не придумала что ответить..."

# --- Логика бота ---
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

@dp.message(F.chat.id.in_(ALLOWED_CHATS))
async def handle_message(message: types.Message):
    if not message.text:
        return

    # Фикс падения на пустых entities
    bot_info = await bot.get_me()
    is_mentioned = False
    if message.entities:
        for e in message.entities:
            if e.type == "mention" and f"@{bot_info.username}" in message.text:
                is_mentioned = True
                break

    # Мгновенный ответ без шансов и КД
    if is_mentioned or "лал" in message.text.lower() or "lal" in message.text.lower():
        try:
            await bot.send_chat_action(message.chat.id, "typing")
            full_reply = await get_gemini_response(message.text)
            await message.reply(full_reply)
        except Exception as e:
            logger.error(f"Ошибка: {e}")

async def main():
    await start_server()
    logger.info(f"Lal 3.0 Unstoppable (3-Flash) запущен.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())