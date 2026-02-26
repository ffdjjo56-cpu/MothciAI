import os, asyncio, logging, re, redis
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# 1. Настройка Gemini (Фикс 404)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# 2. Настройка бота и Redis
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
r = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

@dp.message()
async def chat_handler(message: types.Message):
    # Игнорируем сообщения от ботов и пустой текст
    if not message.text or (message.from_user.is_bot and message.from_user.id != bot.id):
        return
    
    # Проверка вызова: слово "Моти" или ответ на её сообщение
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    is_reply = (message.reply_to_message and message.reply_to_message.from_user.id == bot.id) if message.reply_to_message else False

    if not (is_called or is_reply):
        return

    user_id = message.from_user.id
    t_id = getattr(message, 'message_thread_id', None)
    redis_key = f"moti_history:{user_id}"

    try:
        # Сохраняем сообщение пользователя в Redis
        r.rpush(redis_key, f"user: {message.text}")
        # Лимит 89 сообщений (Контекст 89)
        r.ltrim(redis_key, -89, -1)
        
        # Получаем историю для ИИ
        history = r.lrange(redis_key, 0, -1)
        prompt = "Ты Ева (Моти), ИИ проекта SatanaClub. Твоя история диалога:\n" + "\n".join(history) + "\nЕва:"
        
        # Генерация ответа (через стабильный метод)
        response = model.generate_content(prompt)
        answer = response.text

        # Сохраняем ответ бота
        r.rpush(redis_key, f"model: {answer}")
        r.ltrim(redis_key, -89, -1)

        await message.reply(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Ошибка Моти: {e}")
        # Аварийный ответ без истории
        try:
            res = model.generate_content(f"Ты Моти. Ответь: {message.text}")
            await message.reply(res.text, message_thread_id=t_id)
        except:
            pass

async def main():
    # Очистка очереди обновлений (фикс ConflictError)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Моти запущена на Redis с памятью 89!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
