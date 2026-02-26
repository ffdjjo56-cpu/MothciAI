import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
import config

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Eva (Mothi AI) запускается на Render...")
    
    # Прямое подключение к Telegram без хаков
    bot = Bot(
        token=config.TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение к БД и ИИ
    db_client = AsyncIOMotorClient(config.MONGO_URL)
    db = db_client['SatanaclubDB']
    collection = db['chat_history']
    groq_client = Groq(api_key=config.GROQ_API_KEY)

    @dp.message()
    async def handle_message(message: types.Message):
        # Реагируем только в разрешенном чате
        if message.chat.id != config.ALLOWED_CHAT_ID:
            return

        if not message.text or message.text.startswith('/'):
            return

        # Сохраняем сообщение пользователя
        await collection.insert_one({"chat_id": message.chat.id, "role": "user", "content": message.text})

        # Берем последние 15 сообщений для контекста
        cursor = collection.find({"chat_id": message.chat.id}).sort("_id", -1).limit(15)
        history = await cursor.to_list(length=15)
        history.reverse()

        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        try:
            # Запрос к Groq Llama 3
            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192", 
                messages=messages
            )
            answer = completion.choices[0].message.content
            
            # Сохраняем ответ бота и отправляем его
            await collection.insert_one({"chat_id": message.chat.id, "role": "assistant", "content": answer})
            await message.reply(answer)
        except Exception as e:
            logging.error(f"Ошибка ИИ: {e}")

    try:
        me = await bot.get_me()
        logging.info(f"Бот @{me.username} ОНЛАЙН на Render!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
