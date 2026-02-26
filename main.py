import os, asyncio, logging, psycopg2, re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# 1. Gemini (Исправлено под актуальную библиотеку)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # КРИТЕРИИ АКТИВАЦИИ
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    is_reply = False
    if message.reply_to_message and message.reply_to_message.from_user:
        is_reply = message.reply_to_message.from_user.id == bot.id

    # Если не позвали по имени и не ответили на сообщение бота — игнорируем
    if not (is_called or is_reply):
        return

    t_id = getattr(message, 'message_thread_id', None)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Создаем таблицу, если её нет (исправляет UndefinedColumn со скриншота 1000029581)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        
        # Сохраняем запрос
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # Берем историю (память на 5 сообщений)
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 5", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        prompt = "Ты Ева (тебя зовут Моти), ИИ SatanaClub. Отвечай кратко.\n"
        for r in rows: prompt += f"{r[0]}: {r[1]}\n"
        
        # Генерация ответа через Gemini
        response = model.generate_content(prompt)
        answer = response.text

        # Сохраняем ответ бота
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()

        # Отправляем ответ (реплаем)
        try:
            await message.reply(answer, message_thread_id=t_id)
        except TelegramBadRequest:
            await message.answer(answer)

    except Exception as e:
        logging.error(f"Error in chat_handler: {e}")
        # Резервный ответ при ошибке базы
        try:
            res = model.generate_content(message.text)
            await message.reply(res.text, message_thread_id=t_id)
        except: pass
    finally:
        if conn: conn.close()

async def main():
    # Удаляем вебхук и сбрасываем очереди, чтобы избежать ConflictError (скриншот 1000029586)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
