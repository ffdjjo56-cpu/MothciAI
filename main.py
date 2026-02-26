import os, asyncio, logging, psycopg2, re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)

# 1. Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # ПРОВЕРКА АКТИВАЦИИ:
    # 1. Есть ли в тексте слово "Моти"
    is_called_by_name = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    # 2. Является ли это ответом на сообщение самого бота
    is_reply_to_bot = False
    if message.reply_to_message and message.reply_to_message.from_user:
        is_reply_to_bot = message.reply_to_message.from_user.id == bot.id

    # Если ни то, ни другое — игнорируем сообщение
    if not (is_called_by_name or is_reply_to_bot):
        return

    t_id = getattr(message, 'message_thread_id', None)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 5", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        prompt = "Ты Ева (но тебя называют Моти), ИИ SatanaClub. Отвечай кратко и с характером.\n"
        for r in rows: prompt += f"{r[0]}: {r[1]}\n"
        
        response = model.generate_content(prompt)
        answer = response.text

        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()

        try:
            await message.reply(answer, message_thread_id=t_id)
        except:
            await message.answer(answer)

    except Exception as e:
        logging.error(f"Error: {e}")
        try:
            res = model.generate_content(message.text)
            await message.reply(res.text, message_thread_id=t_id)
        except:
            pass
    finally:
        if conn: conn.close()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
