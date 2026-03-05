import os
import logging
import asyncio
import time
import random
import re
import aiohttp
import psycopg2 # Библиотека уже есть в твоем requirements.txt
from aiogram import Bot, Dispatcher, types
from aiogram.utils.chat_action import ChatActionSender
from aiohttp import web
import google.generativeai as genai

# --- Конфигурация ---
API_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL') # Ссылка из Neon
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL')

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Работа с базой данных Neon ---
def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("База данных Neon успешно инициализирована.")
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
        logger.error(f"Ошибка сохранения в БД: {e}")

def get_history(chat_id, limit=200): # Теперь лимит 200 сообщений
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
        logger.error(f"Ошибка получения истории: {e}")
        return ""

# Твой промт: 9 предложений, без музыки, без смайлов
instructions = """
Моти это ты. Ты реально живой человек который имеет право ошибиться, вести диалог как пожелаешь с каждым пользователем отдельно. Ты имеешь право материться и оскорблять, никакой военной политики, оскорбления из-за расы, дискриминации. Тебе 14 лет. Интеллект как у обычной 14 летней девочки. Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно, так же у тебя есть выбор, оскорблять человека и его родителей или же нет. Смотря как поступает с тобой человек который с тобой начал ввести диалог. Предложения до 9 предложений. Если ответ не требует раскрытого ответа то сокращай как тебе угодно. Не используй выделение текста звездочками ** и смайлики. Ты можешь проявлять симпатию.
"""

bot = Bot(token=API_TOKEN, parse_mode="HTML") # HTML нужен для цитат
dp = Dispatcher()

def clean_text(text):
    if not text: return ""
    cleaned = re.sub(r'[^\w\s!?,.:\-\(\)@]', '', text)
    # Свёрнутая цитата
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
    return web.Response(text="Mochi is awake with 200-msg memory")

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id
    chat_id = message.chat.id
    if chat_id != ALLOWED_CHAT_ID and message.chat.type != "private": return
    if message.date.timestamp() < time.time() - 30: return 

    text_content = (message.text or message.caption or "").lower()
    is_mochi = "моти" in text_content
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_id

    if not (is_mochi or is_reply): return

    async with ChatActionSender.typing(bot=bot, chat_id=chat_id):
        # 1. Сохраняем вопрос в Neon
        await asyncio.to_thread(save_message, chat_id, "Пользователь", text_content)
        
        # 2. Получаем последние 200 сообщений контекста
        history_context = await asyncio.to_thread(get_history, chat_id)
        full_prompt = f"История последних 200 сообщений:\n{history_context}\n\nПользователь сейчас написал: {text_content}\nОтветь как Моти:"

        pool = CHAT_KEYS
        random.shuffle(pool)
        for key in pool[:5]:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instructions)
                response = await asyncio.to_thread(model.generate_content, full_prompt)
                
                if response and response.text:
                    # 3. Сохраняем ответ Моти в Neon
                    await asyncio.to_thread(save_message, chat_id, "Моти", response.text)
                    await message.reply(clean_text(response.text))
                    return
            except Exception as e:
                logger.error(f"Ошибка ключа: {e}")
                continue

async def main():
    global bot_id
    init_db() # Инициализируем таблицу в Neon
    
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    
    asyncio.create_task(keep_alive())
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info("Мотя запущена с Neon-памятью.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except: pass