import os
import logging
import asyncio
import time
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.chat_action import ChatActionSender
from aiohttp import web
import google.generativeai as genai

# Инициализация настроек
API_TOKEN = os.getenv('BOT_TOKEN')
KEYS = [os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')]
KEYS = [k for k in KEYS if k]

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

# Статистика ключей
key_stats = {i: {"used": 0, "status": "✅"} for i in range(len(KEYS))}
last_reset = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТВОЙ ОБНОВЛЕННЫЙ ПРОМТ
instructions = (
    "Моти это ты. Ты реально живой человек который имеет право ошибиться, "
    "вести диалог как пожелаешь с каждым пользователем отдельно. "
    "Ты имеешь право материться и оскорблять, никакой военной политики, "
    "оскорбления из-за расы, дискриминации. Тебе 14 лет. Об этом можешь не говорить вообще"
    "Интеллект как у обычной 14 летней девочки."
    "Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно, "
    "так же у тебя есть выбор, оскорблять человека и его родителей или же нет. "
    "Смотря как поступает с тобой человек который с тобой начал ввести диалог. "
    "Предложения до 7 предложений. Если ответ не требует раскрытого ответа то сокращай как тебе угодно. "
    "Не используй выделение текста звездочками **."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:-]', '', text)

async def handle(request):
    return web.Response(text=f"Mochi (14yo) is online. Keys: {len(KEYS)}")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id, last_reset
    
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        return
    if message.date.timestamp() < time.time() - 2:
        return 

    text_lower = (message.text or message.caption or "").lower()

    # Сброс лимитов раз в минуту
    time_since_reset = time.time() - last_reset
    if time_since_reset > 60:
        for i in range(len(KEYS)):
            key_stats[i]["used"] = 0
            key_stats[i]["status"] = "✅"
        last_reset = time.time()
        time_since_reset = 0

    # Команда КЛЮЧИ
    if "моти ключи" in text_lower:
        header = f"📊 <b>Статус ключей ({int(60 - time_since_reset)}с до сброса):</b>\n"
        body = "<blockquote>"
        total_left = 0
        for i in range(len(KEYS)):
            left = max(0, 20 - key_stats[i]["used"])
            body += f"{i+1} ключ = {left} зап. / {key_stats[i]['status']}\n"
            total_left += left
        body += "</blockquote>"
        await message.reply(f"{header}{body}\n<b>Всего: {total_left} зап.</b>", parse_mode="HTML")
        return

    # Команда ПИНГ
    if "моти пинг" in text_lower:
        ping_ms = int((time.time() - message.date.timestamp()) * 1000)
        await message.reply(f"<code>Пинг: {ping_ms}ms</code>\nЧе надо?", parse_mode="HTML")
        return

    # Логика призыва
    is_mochi = "моти" in text_lower
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_id
    if not (is_mochi or is_reply_to_bot):
        return

    # ВКЛЮЧАЕМ СТАТУС "ПЕЧАТАЕТ" И СТРИМИНГ
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        idx = random.randint(0, len(KEYS) - 1)
        try:
            genai.configure(api_key=KEYS[idx])
            model = genai.GenerativeModel("gemini-3-flash-preview", system_instruction=instructions)
            
            response = model.generate_content(message.text, stream=True)
            sent_message = await message.reply("...")
            
            full_text = ""
            last_edit_time = 0
            
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    # Редактируем раз в 1.2 сек
                    if time.time() - last_edit_time > 1.2:
                        try:
                            await sent_message.edit_text(clean_text(full_text))
                            last_edit_time = time.time()
                        except:
                            pass
            
            final_text = clean_text(full_text)
            if final_text:
                await sent_message.edit_text(final_text)
                key_stats[idx]["used"] += 1

        except Exception as e:
            if "429" in str(e): 
                key_stats[idx]["status"] = "🚫"
            logger.error(f"Ошибка: {e}")

async def main():
    global bot_id
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info("Мотя (14 лет) готова к общению!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
