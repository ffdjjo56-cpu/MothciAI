import os
import asyncio
import random
import logging
import io
import asyncpg
import edge_tts
import pytesseract
import PIL.Image
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.chat_action import ChatActionSender
from aiogram.types import BufferedInputFile
import google.generativeai as genai

API_TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL')
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

CHAT_KEYS = [os.getenv(k) for k in os.environ if "GEMINI_KEY" in k]
raw_chats = os.getenv('ALLOWED_CHATS', '')
ALLOWED_CHATS = [int(i.strip()) for i in raw_chats.split(',') if i.strip()]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db_pool = None
failed_keys = {}

INSTRUCTIONS = "Ты — Моти, 14-летняя токсичная школьница. Дерзкая, используешь сленг. Отвечай коротко, без капса."

async def get_best_key():
    now = datetime.now()
    available = [k for k in CHAT_KEYS if k not in failed_keys or failed_keys[k]['blocked_until'] < now]
    return random.choice(available) if available else None

def mark_key_failed(key):
    now = datetime.now()
    if key not in failed_keys:
        failed_keys[key] = {'fails': 1, 'blocked_until': now}
    else:
        failed_keys[key]['fails'] += 1
        if failed_keys[key]['fails'] >= 3:
            failed_keys[key]['blocked_until'] = now + timedelta(minutes=3)

def mark_key_success(key):
    if key in failed_keys: failed_keys[key]['fails'] = 0

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DB_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (chat_id BIGINT, role TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS user_rep (user_id BIGINT PRIMARY KEY, points FLOAT DEFAULT 5.0);
        """)

async def get_voice(text):
    communicate = edge_tts.Communicate(text, "ru-RU-SvetlanaNeural")
    fp = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio": fp.write(chunk["data"])
    fp.seek(0)
    return BufferedInputFile(fp.read(), filename="moti.ogg")

@dp.message()
async def talk_handler(message: types.Message):
    if message.chat.id not in ALLOWED_CHATS:
        return

    user_id = message.from_user.id
    text = (message.text or message.caption or "").lower()
    bot_info = await bot.get_me()

    is_moti = "моти" in text or "мотя" in text
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    ocr_text = ""
    if message.photo and is_moti:
        try:
            file = await bot.get_file(message.photo[-1].file_id)
            img_data = await bot.download_file(file.file_path)
            ocr_text = await asyncio.to_thread(pytesseract.image_to_string, PIL.Image.open(io.BytesIO(img_data.read())), lang='rus+eng')
        except: pass

    if not (is_moti or is_reply): return

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        async with db_pool.acquire() as conn:
            rep = await conn.fetchval("SELECT points FROM user_rep WHERE user_id = $1", user_id) or 5.0

        prompt = f"{INSTRUCTIONS}\nРепа: {rep}/5\n"
        if ocr_text: prompt += f"(Текст на фото: {ocr_text})\n"
        prompt += f"Юзер: {text}"

        reply_text = None
        for _ in range(5):
            key = await get_best_key()
            if not key: break
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = await asyncio.to_thread(model.generate_content, prompt)
                reply_text = response.text.replace("*", "")
                mark_key_success(key)
                break
            except:
                mark_key_failed(key)

        if not reply_text: return

        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO chat_history (chat_id, role, content) VALUES ($1, $2, $3)", message.chat.id, message.from_user.first_name, text)

        if random.random() < 0.2:
            await message.reply_voice(await get_voice(reply_text))
            await message.answer(f"<b>Репутация {round(rep, 1)}</b>")
        else:
            await message.reply(f"<blockquote>{reply_text}</blockquote>\n<b>Репутация {round(rep, 1)}</b>")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())