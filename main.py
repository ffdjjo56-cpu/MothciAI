import os, asyncio, logging, psycopg2, re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# Инициализация модели (исправляем ошибку v1beta со скриншота 1000029595)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # Активация на "Моти" или Reply (как ты просил)
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot.id if message.reply_to_message else False

    if not (is_called or is_reply): return

    t_id = getattr(message, 'message_thread_id', None)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Исправляем структуру базы (скриншоты 1000029581, 1000029592)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY")
        
        # Записываем сообщение
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # КОНТЕКСТ 89: Берем последние 89 сообщений из истории
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 89", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        prompt = "Ты Ева (Моти), ИИ SatanaClub. Ты помнишь длинную историю диалога.\n"
        for r in rows:
            prompt += f"{r[0]}: {r[1]}\n"
        
        # Генерация ответа
        response = model.generate_content(prompt)
        answer = response.text

        # Записываем ответ бота
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()

        # Красивый ответ реплаем
        await message.reply(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Error: {e}")
        # Если база тупит (как на скрине 1000029592), отвечаем без истории
        try:
            res = model.generate_content(message.text)
            await message.reply(res.text, message_thread_id=t_id)
        except: pass
    finally:
        if conn: conn.close()

async def main():
    # Сброс ConflictError (скриншоты 1000029585, 1000029593)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())