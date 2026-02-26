import os, asyncio, logging, psycopg2, re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# Инициализация ИИ (фикс 404/v1beta)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Функция "Чистки" базы данных
def setup_database():
    conn = get_db_connection()
    cur = conn.cursor()
    # Мы НЕ удаляем таблицу каждый раз (чтобы не терять память), 
    # но гарантируем, что все нужные столбцы на месте
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            role TEXT,
            content TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    logging.info("База данных проверена и готова к работе.")

@dp.message()
async def chat_handler(message: types.Message):
    if not message.text: return
    
    # Реакция только на "Моти" или реплай
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    is_reply = (message.reply_to_message and message.reply_to_message.from_user.id == bot.id) if message.reply_to_message else False

    if not (is_called or is_reply): return

    t_id = getattr(message, 'message_thread_id', None)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Пишем сообщение пользователя
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # КОНТЕКСТ 89 сообщений
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 89", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        history = "\n".join([f"{r[0]}: {r[1]}" for r in rows])
        prompt = f"Ты Ева (Моти), ИИ SatanaClub. Твоя история диалога:\n{history}\nЕва:"
        
        response = model.generate_content(prompt)
        answer = response.text

        # Пишем ответ бота
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()
        conn.close()
        
        await message.reply(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        # Если база данных умерла (как на скрине 1000029592), отвечаем без неё
        res = model.generate_content(f"Ты Моти. Ответь: {message.text}")
        await message.reply(res.text, message_thread_id=t_id)

async def main():
    # 1. Сначала чиним базу
    setup_database()
    # 2. Сбрасываем старые сообщения (фикс ConflictError)
    await bot.delete_webhook(drop_pending_updates=True)
    # 3. Стартуем
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
