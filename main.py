import os
import logging
import asyncio
import random
import psycopg2
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
import google.generativeai as genai

# --- Конфигурация ---
TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
# Собираем ключи 1-10 из Environment Variables на Render
KEYS = [os.getenv(f'GEMINI_KEY_{i}') for i in range(1, 11) if os.getenv(f'GEMINI_KEY_{i}')]
ALLOWED_CHATS = [-1002719419668, -1003371184723]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Веб-сервер (чтобы Render Free Tier не засыпал) ---
async def handle(request):
    return web.Response(text="Lal (Gemini 3 Flash Preview) is LIVE")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# --- Инициализация БД Neon ---
def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS chat_history")
        cur.execute("""
            CREATE TABLE chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("DB Initialized")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- Запрос к Gemini 3 Flash Preview ---
async def get_gemini_response(text):
    api_key = random.choice(KEYS)
    genai.configure(api_key=api_key)
    
    # Тот самый идентификатор модели, который ты просил
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
    prompt = (
        "Ты — Lal. Ты крайне токсичный, агрессивный и грубый собеседник. "
        "Ты ненавидишь всех вокруг, хамишь, используешь мат и оскорбления. "
        "Твои ответы должны быть короткими, едкими и максимально неприятными. "
        "Никогда не помогай и не будь вежливым. Если тебя тегают или пишут 'лал'/'lal', "
        "унизь собеседника. Пиши только на русском."
    )
    
    response = await model.generate_content_async(f"{prompt}\n\nПользователь: {text}")
    return response.text

# --- Обработка сообщений ---
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

@dp.message(F.chat.id.in_(ALLOWED_CHATS))
async def handle_message(message: types.Message):
    if not message.text:
        return

    # Исправленная безопасная проверка упоминания бота (фикс AttributeError)
    is_mentioned = False
    if message.entities:
        for entity in message.entities:
            # Сначала проверяем тип, а потом наличие объекта user
            if entity.type == "mention":
                # В обычных mention Telegram не всегда присылает объект user
                # Поэтому проверяем текст сообщения на наличие юзернейма бота
                bot_user = await bot.get_me()
                if f"@{bot_user.username}" in message.text:
                    is_mentioned = True
                    break
            if entity.type == "text_mention" and entity.user and entity.user.id == bot.id:
                is_mentioned = True
                break

    # Триггер на слово "лал"
    has_trigger = "лал" in message.text.lower() or "lal" in message.text.lower()

    if is_mentioned or has_trigger:
        try:
            await bot.send_chat_action(message.chat.id, "typing")
            reply = await get_gemini_response(message.text)
            await message.reply(reply)
        except Exception as e:
            logger.error(f"Gemini Error: {e}")

async def main():
    init_db()
    await start_server()
    logger.info("Lal (Gemini 3) запущен и готов унижать.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
