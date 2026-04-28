import os
import io
import asyncio
import random
import logging
import asyncpg
import edge_tts
import google.generativeai as genai
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.chat_action import ChatActionSender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moti_bot")

TOKEN = os.getenv('BOT_TOKEN')
DB_URL = os.getenv('DATABASE_URL', '').replace("postgres://", "postgresql://", 1)
KEYS = [os.getenv(k) for k in os.environ if "GEMINI_KEY" in k]
CHATS = [int(i.strip()) for i in os.getenv('ALLOWED_CHATS', '').split(',') if i.strip()]

PROMPT = (
    "Ты — Моти, 14-летняя токсичная школьница. "
    "Твой стиль: дерзость, сленг, короткие ответы без капса. "
    "Ты не любишь тупые вопросы и всегда подкалываешь собеседника."
)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db_pool = None
key_cooldowns = {}

async def get_db():
    global db_pool
    if not db_pool:
        db_pool = await asyncpg.create_pool(DB_URL)
    return db_pool

async def init_db():
    pool = await get_db()
    await pool.execute("DROP TABLE IF EXISTS chat_logs CASCADE;")
    await pool.execute("DROP TABLE IF EXISTS user_rep CASCADE;")
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS user_rep (
            user_id BIGINT PRIMARY KEY, 
            points FLOAT DEFAULT 5.0
        );
        CREATE TABLE IF NOT EXISTS chat_logs (
            chat_id BIGINT, 
            role TEXT, 
            msg TEXT, 
            dt TIMESTAMP DEFAULT NOW()
        );
    """)

async def get_working_key():
    now = datetime.now()
    available = [k for k in KEYS if k not in key_cooldowns or key_cooldowns[k] < now]
    return random.choice(available) if available else None

@dp.message()
async def handle_message(message: types.Message):
    if message.chat.id not in CHATS:
        return

    bot_user = await bot.get_me()
    text = (message.text or message.caption or "").lower()
    
    is_called = any(name in text for name in ["мотя", "моти"])
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id
    
    if not (is_called or is_reply):
        return

    pool = await get_db()
    user_id = message.from_user.id
    rep = await pool.fetchval("SELECT points FROM user_rep WHERE user_id = $1", user_id) or 5.0

    rows = await pool.fetch(
        "SELECT role, msg FROM chat_logs WHERE chat_id = $1 ORDER BY dt DESC LIMIT 5", 
        message.chat.id
    )
    history = "\n".join([f"{r['role']}: {r['msg']}" for r in reversed(rows)])

    full_prompt = f"{PROMPT}\nИстория:\n{history}\nЧелик (репа {round(rep, 1)}): {text}"
    content = [full_prompt]

    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        img_bytes = await bot.download_file(file.file_path)
        content.append({"mime_type": "image/jpeg", "data": img_bytes.read()})

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        active_key = await get_working_key()
        if not active_key:
            return

        try:
            genai.configure(api_key=active_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = await asyncio.to_thread(model.generate_content, content)
            reply_text = response.text.replace("*", "").strip()
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            key_cooldowns[active_key] = datetime.now() + timedelta(minutes=3)
            return

        await pool.execute(
            "INSERT INTO chat_logs (chat_id, role, msg) VALUES ($1, $2, $3), ($1, $4, $5)",
            message.chat.id, "Юзер", text[:200], "Моти", reply_text[:200]
        )

        rep_label = f"<b>Репутация {round(rep, 1)}</b>"

        if random.random() < 0.2:
            try:
                tts = edge_tts.Communicate(reply_text, "ru-RU-SvetlanaNeural")
                audio_stream = io.BytesIO()
                async for chunk in tts.stream():
                    if chunk["type"] == "audio":
                        audio_stream.write(chunk["data"])
                audio_stream.seek(0)
                await message.reply_voice(
                    types.BufferedInputFile(audio_stream.read(), filename="moti.ogg")
                )
                await message.answer(rep_label)
                return
            except Exception as e:
                logger.error(f"TTS Error: {e}")

        await message.reply(f"<blockquote>{reply_text}</blockquote>\n{rep_label}")

async def main():
    await init_db()
    
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Moti is active"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
