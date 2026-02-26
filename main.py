import asyncio
import logging
import socket
import urllib.parse
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
import config

# --- ЖЕСТКИЙ ХАК DNS №2 ---
class CustomResolver(aiohttp.abc.AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        if host == 'api.telegram.org':
            return [{'hostname': host, 'host': '149.154.167.220', 'port': port, 
                     'family': family, 'proto': 0, 'flags': 0}]
        return await aiohttp.DefaultResolver().resolve(host, port, family)
    async def close(self): pass

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Eva (Mothi AI) запускает план 'Прорыв' (Исправлено)...")
    
    # Создаем коннектор правильно
    connector = aiohttp.TCPConnector(resolver=CustomResolver(), ssl=False)
    
    # В aiogram 3.x коннектор передается ТАК:
    session = AiohttpSession()
    session._connector = connector 
    
    bot = Bot(
        token=config.TOKEN, 
        session=session, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()

    # Обработка MONGO_URL
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
        logging.error(f"Ошибка в MONGO_URL: {e}")
    
    db_client = AsyncIOMotorClient(raw_url)
    db = db_client['SatanaclubDB']
    collection = db['chat_history']
    groq_client = Groq(api_key=config.GROQ_API_KEY)

    @dp.message()
    async def handle_message(message: types.Message):
        if message.chat.type in ['group', 'supergroup'] and message.chat.id != config.ALLOWED_CHAT_ID:
            return
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

    try:
        me = await bot.get_me()
        logging.info(f"Бот @{me.username} ОНЛАЙН!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
