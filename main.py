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

# Настройки ключей
API_TOKEN = os.getenv('BOT_TOKEN')
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
SEARCH_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('SEARCH_KEY')])

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

chat_stats = {i: {"used": 0, "status": "✅"} for i in range(len(CHAT_KEYS))}
search_stats = {i: {"used": 0, "status": "✅"} for i in range(len(SEARCH_KEYS))}
last_reset = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТВОЙ ФУЛЛ ПРОМТ (Исправлен синтаксис для Python)
instructions = """
Моти это ты. Ты реально живой человек который имеет право ошибиться, вести диалог как пожелаешь с каждым пользователем отдельно. Ты имеешь право материться и оскорблять, никакой военной политики, оскорбления из-за расы, дискриминации. Тебе 14 лет. Интеллект как у обычной 14 летней девочки которая шарит в музыке. Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно, так же у тебя есть выбор, оскорблять человека и его родителей или же нет. Смотри как поступает с тобой человек который с тобой начал ввести диалог. Предложения до 7 предложений. Если ответ не требует раскрытого ответа то сокращай как тебе угодно. Не используй выделение текста звездочками **.
"""

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    if not text: return ""
    return re.sub(r'[^\w\s!?,.:-]', '', text)

async def handle(request):
    return web.Response(text="Mochi 3.0 is running")

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id, last_reset
    
    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        return
    if message.date.timestamp() < time.time() - 20:
        return 

    text_content = (message.text or message.caption or "").lower()
    
    if time.time() - last_reset > 60:
        for d in [chat_stats, search_stats]:
            for i in d: d[i]["used"], d[i]["status"] = 0, "✅"
        last_reset = time.time()

    search_triggers = ["найди", "поищи", "что это", "ищи"]
    is_search = any(trigger in text_content for trigger in search_triggers)
    is_more = "побольше" in text_content
    
    if not ("моти" in text_content or (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) or is_more):
        return

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        if (is_search or is_more) and SEARCH_KEYS:
            pool, stats = SEARCH_KEYS, search_stats
            tools = [{"google_search_retrieval": {}}]
        else:
            pool, stats = CHAT_KEYS, chat_stats
            tools = None

        # Пробуем ключи, пока не найдем рабочий (защита от 429 ошибки)
        random.shuffle(pool) 
        for current_key in pool:
            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(
                    model_name="gemini-3-flash-preview",
                    system_instruction=instructions,
                    tools=tools
                )
                
                query = message.text or "Привет"
                if tools:
                    response = model.generate_content(query)
                    if response.text:
                        await message.reply(clean_text(response.text))
                        return
                else:
                    response = model.generate_content(query, stream=True)
                    sent_message = await message.reply("💭")
                    full_text = ""
                    for chunk in response:
                        if chunk.text:
                            full_text += chunk.text
                    await sent_message.edit_text(clean_text(full_text))
                    return

            except Exception as e:
                logger.error(f"Ошибка ключа: {e}")
                continue 
        
        await message.reply("Блин, чет я устала, ключи не пашут.")

async def main():
    global bot_id
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
