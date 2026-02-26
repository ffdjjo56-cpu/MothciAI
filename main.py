import os, asyncio, logging, psycopg2, re
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# Инициализация ИИ
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@dp.message()
async def chat_handler(message: types.Message):
    # ПРОВЕРКА НА БОТА: Если сообщение пришло от бота — полностью игнорируем
    if not message.text or message.from_user.is_bot:
        return
    
    # Реакция только на имя "Моти" или реплай на её сообщение
    is_called = re.search(r'\bМоти\b', message.text, re.IGNORECASE)
    is_reply = (message.reply_to_message and message.reply_to_message.from_user.id == bot.id) if message.reply_to_message else False

    if not (is_called or is_reply):
        return

    t_id = getattr(message, 'message_thread_id', None)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Гарантируем правильную структуру таблицы (фикс ошибки id does not exist)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                role TEXT,
                content TEXT
            )
        """)
        cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY")
        conn.commit()
        
        # Сохраняем сообщение пользователя
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "user", message.text))
        
        # Загружаем историю (Контекст 89)
        cur.execute("SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT 89", 
                    (message.from_user.id,))
        rows = cur.fetchall()[::-1]
        
        history = "\n".join([f"{r[0]}: {r[1]}" for r in rows])
        prompt = f"Ты Ева (Моти), ИИ SatanaClub. Твоя история:\n{history}\nЕва:"
        
        response = model.generate_content(prompt)
        answer = response.text

        # Сохраняем ответ бота
        cur.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", 
                    (message.from_user.id, "model", answer))
        conn.commit()
        cur.close()

        await message.reply(answer, message_thread_id=t_id)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        # Резервный ответ без истории
        try:
            res = model.generate_content(f"Ты Моти. Ответь: {message.text}")
            await message.reply(res.text, message_thread_id=t_id)
        except: pass
    finally:
        if conn: conn.close()

async def main():
    # Очистка очереди обновлений (фикс TelegramConflictError)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Моти запущена и больше не слушает других ботов!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
