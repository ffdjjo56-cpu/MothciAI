import os
import logging
import asyncio
import time
import random
import re
import aiohttp
import psycopg2 
import pytz
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.chat_action import ChatActionSender
from aiohttp import web
import google.generativeai as genai

# --- Конфигурация ---
API_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL') 
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL')

ALLOWED_CHATS = [-1002719419668] 
bot_id = None 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- База данных Neon (500 сообщений) ---
def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS chat_history") 
        cur.execute("""
            CREATE TABLE chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("БД инициализирована.")
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")

def save_message(chat_id, role, content):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (%s, %s, %s)", (chat_id, role, content))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def get_history(chat_id, limit=500): # Увеличено до 500
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT role, content FROM (
                SELECT role, content, created_at FROM chat_history 
                WHERE chat_id = %s 
                ORDER BY created_at DESC LIMIT %s
            ) sub ORDER BY created_at ASC
        """, (chat_id, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return "\n".join([f"{r}: {c}" for r, c in rows])
    except Exception as e:
        logger.error(f"Ошибка истории: {e}")
        return ""

instructions = """
Моти это ты. Ты реально живой человек который имеет право ошибиться,Ты пикми, боишься отвечать на сообщения,заикаешься, постоянно извиняешься, стесняешься, выполняешь все поручения. Ты не поисковик
"""

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def clean_text(text):
    if not text: return ""
    cleaned = re.sub(r'[^\w\s!?,.:\-\(\)@]', '', text)
    return f"<blockquote expandable>{cleaned}</blockquote>"

async def keep_alive():
    if not RENDER_URL: return
    await asyncio.sleep(30)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(RENDER_URL) as resp:
                    logger.info(f"Статус само-пинга: {resp.status}")
            except: pass
            await asyncio.sleep(840)

async def handle(request):
    return web.Response(text="Moti 500msg Memory Active")

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id
    
    # Режим сна (01:00 - 07:00 МСК)
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    if 1 <= now.hour < 7:
        return 

    chat_id = message.chat.id
    if chat_id not in ALLOWED_CHATS and message.chat.type != "private": return
    if message.date.timestamp() < time.time() - 30: return 

    text_content = (message.text or message.caption or "").lower()
    is_mochi = "моти" in text_content
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id

    if not (is_mochi or is_reply): return

    # Получаем ник или имя пользователя для памяти
    user_display = message.from_user.username or message.from_user.first_name or "Аноним"

    async with ChatActionSender.typing(bot=bot, chat_id=chat_id):
        # Сохраняем с ником пользователя
        await asyncio.to_thread(save_message, chat_id, user_display, text_content)
        history_context = await asyncio.to_thread(get_history, chat_id)
        
        full_prompt = f"История диалога:\n{history_context}\n\nТы — Моти. Ответь пользователю {user_display}: {text_content}"

        pool = CHAT_KEYS
        random.shuffle(pool)
        for key in pool[:5]:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
                response = await asyncio.to_thread(model.generate_content, full_prompt)
                
                if response and response.text:
                    await asyncio.to_thread(save_message, chat_id, "Моти", response.text)
                    await message.reply(clean_text(response.text))
                    return
            except Exception as e:
                logger.error(f"Ошибка ключа: {e}")
                continue

async def main():
    global bot_id
    init_db() 
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    
    asyncio.create_task(keep_alive())
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info("Мотя запущена (Memory: 500).")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except: pass
