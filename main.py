import asyncio
import logging
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
import config

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- МИНИ ВЕБ-СЕРВЕР ДЛЯ CRON-JOB ---
async def handle_ping(request):
    return web.Response(text="Mochi is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render сам подставит нужный PORT, если нет - берем 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")

# --- ОСНОВНОЙ БОТ МОТИ ---
async def main():
    logging.info("Mochi AI запускается на Render...")
    
    # Запускаем веб-сервер параллельно
    asyncio.create_task(start_web_server())
    
    # Исправление ссылки MongoDB для обработки спецсимволов и SSL
    raw_url = config.MONGO_URL
    try:
        if "@" in raw_url.split("://")[-1]:
            prefix, rest = raw_url.split("://")
            user_pass, host = rest.split("@", 1)
            if ":" in user_pass:
                user, password = user_pass.split(":", 1)
                encoded_pass = urllib.parse.quote_plus(password)
                raw_url = f"{prefix}://{user}:{encoded_pass}@{host}"
    except Exception as e:
        logging.error(f"Ошибка парсинга URL: {e}")

    # Подключение к MongoDB с защитой от ошибок SSL
    db_client = AsyncIOMotorClient(
        raw_url, 
        tls=True, 
        tlsAllowInvalidCertificates=True
    )
    db = db_client['SatanaclubDB']
    collection = db['chat_history']
    
    bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    groq_client = Groq(api_key=config.GROQ_API_KEY)

    @dp.message()
    async def handle_message(message: types.Message):
        # Проверка ID чата
        if message.chat.id != config.ALLOWED_CHAT_ID:
            return
        
        # Игнорируем команды и пустые сообщения
        if not message.text or message.text.startswith('/'):
            return

        try:
            # Сохраняем сообщение пользователя
            await collection.insert_one({
                "chat_id": message.chat.id, 
                "role": "user", 
                "content": message.text
            })

            # Загружаем историю (последние 15 сообщений)
            cursor = collection.find({"chat_id": message.chat.id}).sort("_id", -1).limit(15)
            history = await cursor.to_list(length=15)
            history.reverse()

            messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})

            # Запрос к нейросети
            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192", 
                messages=messages
            )
            answer = completion.choices[0].message.content

            # Сохраняем ответ бота и отправляем его
            await collection.insert_one({
                "chat_id": message.chat.id, 
                "role": "assistant", 
                "content": answer
            })
            await message.reply(answer)

        except Exception as e:
            logging.error(f"Ошибка при обработке сообщения: {e}")

    # Запуск
    me = await bot.get_me()
    logging.info(f"Бот @{me.username} ОНЛАЙН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
