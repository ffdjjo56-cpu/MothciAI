import asyncio
from aiogram import Bot, Dispatcher, types
from groq import Groq
from motor.motor_asyncio import AsyncIOMotorClient
import config
import os


bot = Bot(token=config.TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=config.GROQ_API_KEY)


db_client = AsyncIOMotorClient(config.MONGO_URL)
db = db_client['SatanaclubDB']
collection = db['chat_history']

@dp.message()
async def talk_to_moti(message: types.Message):
    
    if not message.text or message.text.startswith('/'): return

  
    user_msg = {
        "chat_id": message.chat.id,
        "user_id": message.from_user.id,
        "username": message.from_user.username or "unknown",
        "content": message.text,
        "role": "user"
    }
    await collection.insert_one(user_msg)

    
    cursor = collection.find({"chat_id": message.chat.id}).sort("_id", -1).limit(10)
    history = await cursor.to_list(length=50)
    history.reverse()

    
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    try:
        
        completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages
        )
        answer = completion.choices[0].message.content
        
        
        await collection.insert_one({
            "chat_id": message.chat.id, 
            "role": "assistant", 
            "content": answer
        })
        
        
        await message.reply(answer)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        await message.reply("Что-то пошло не так, кожаный. Попробуй позже.")

async def main():
    print("Бот Моти запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
