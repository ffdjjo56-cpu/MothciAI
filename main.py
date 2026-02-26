import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
import config

logging.basicConfig(level=logging.INFO)

# --- МИНИ ВЕБ-СЕРВЕР ДЛЯ CRON-JOB ---
async def handle_ping(request):
    return web.Response(text="Eva is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render сам подставит нужный PORT
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")

# --- ОСНОВНОЙ БОТ ---
async def main():
    logging.info("Eva (Mothi AI) запускается на Render...")
    
    # Запускаем веб-сервер параллельно с ботом
    asyncio.create_task(start_web_server())
    
    bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    db_client = AsyncIOMotorClient(config.MONGO_URL)
    db = db_client['SatanaclubDB']
    collection = db['chat_history']
    groq_client = Groq(api_key=config.GROQ_API_KEY)

    @dp.message()
    async def handle_message(message: types.Message):
        if message.chat.id != config.ALLOWED_CHAT_ID: return
        if not message.text or message.text.startswith('/'): return

        await collection.insert_one({"chat_id": message.chat.id, "role": "user", "content": message.text})
        cursor = collection.find({"chat_id": message.chat.id}).sort("_id", -1).limit(15)
        history = await cursor.to_list(length=15)
        history.reverse()

        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        try:
            completion = groq_client.chat.completions.create(model="llama3-70b-8192", messages=messages)
            answer = completion.choices[0].message.content
            await collection.insert_one({"chat_id": message.chat.id, "role": "assistant", "content": answer})
            await message.reply(answer)
        except Exception as e:
            logging.error(f"Ошибка ИИ: {e}")

    me = await bot.get_me()
    logging.info(f"Бот @{me.username} ОНЛАЙН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
