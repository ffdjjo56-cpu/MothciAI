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
from google.generativeai.types import Tool

# Настройки ключей
API_TOKEN = os.getenv('BOT_TOKEN')
# Подгружаем все ключи, которые начинаются с этих префиксов
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
SEARCH_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('SEARCH_KEY')])

ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

# Динамическая статистика
chat_stats = {i: {"used": 0, "status": "✅"} for i in range(len(CHAT_KEYS))}
search_stats = {i: {"used": 0, "status": "✅"} for i in range(len(SEARCH_KEYS))}
last_reset = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Твой промт (14-летняя Моти)
instructions = (
    "Моти это ты. Ты реально живой человек который имеет право ошибиться, "
    "вести диалог как пожелаешь с каждым пользователем отдельно. Тебе 14 лет. "
    "Интеллект как у обычной 14 летней девочки которая шарит в музыке. "
    "Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно. "
    "Имеешь право материться и оскорблять (в т.ч. родителей), смотря как к тебе относятся. "
    "Никакой политики, расы, дискриминации. До 7 предложений. Не пиши **."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    return re.sub(r'[^\w\s!?,.:-]', '', text)

async def handle(request):
    return web.Response(text=f"Mochi Online. Chat: {len(CHAT_KEYS)}, Search: {len(SEARCH_KEYS)}")

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

    text_content = (message.text or message.caption or "").lower()
    
    # Сброс лимитов раз в минуту
    time_since_reset = time.time() - last_reset
    if time_since_reset > 60:
        for d in [chat_stats, search_stats]:
            for i in d:
                d[i]["used"], d[i]["status"] = 0, "✅"
        last_reset = time.time()
        time_since_reset = 0

    # Команда КЛЮЧИ
    if "моти ключи" in text_content:
        res = f"📊 <b>Лимиты ({int(60-time_since_reset)}с до сброса):</b>\n\n"
        
        chat_left = sum(max(0, 15-chat_stats[i]['used']) for i in chat_stats)
        res += f"💬 <b>Болталка ({len(CHAT_KEYS)} шт):</b>\n"
        res += f"<blockquote>Осталось запросов: {chat_left}</blockquote>\n"
        
        search_left = sum(max(0, 15-search_stats[i]['used']) for i in search_stats)
        res += f"🔍 <b>Поиск ({len(SEARCH_KEYS)} шт):</b>\n"
        res += f"<blockquote>Осталось запросов: {search_left}</blockquote>"
        
        await message.reply(res, parse_mode="HTML")
        return

    # Триггеры поиска
    search_triggers = ["найди", "поищи", "что это", "ищи"]
    is_search = any(trigger in text_content for trigger in search_triggers)
    is_more = "побольше" in text_content
    
    if not ("моти" in text_content or (message.reply_to_message and message.reply_to_message.from_user.id == bot_id) or is_more):
        return

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        # Выбор пула ключей
        if (is_search or is_more) and SEARCH_KEYS:
            pool, stats = SEARCH_KEYS, search_stats
            tools = [Tool.from_google_search_retrieval(google_search_retrieval=genai.types.GoogleSearchRetrieval())]
        else:
            pool, stats = CHAT_KEYS, chat_stats
            tools = None

        idx = random.randint(0, len(pool) - 1)
        try:
            genai.configure(api_key=pool[idx])
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=instructions, tools=tools)
            
            query = message.text
            if is_more and message.reply_to_message:
                query = f"Расскажи максимально подробно про это: {message.reply_to_message.text}"
            
            # Стриминг
            response = model.generate_content(query, stream=True)
            sent_message = await message.reply("💭")
            
            full_text, last_edit = "", 0
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    if time.time() - last_edit > 1.2:
                        try:
                            await sent_message.edit_text(clean_text(full_text))
                            last_edit = time.time()
                        except: pass
            
            final = clean_text(full_text)
            if final:
                await sent_message.edit_text(final)
                stats[idx]["used"] += 1
        except Exception as e:
            if "429" in str(e): stats[idx]["status"] = "🚫"
            logger.error(f"Err: {e}")

async def main():
    global bot_id
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info(f"Мотя запущена. База: {len(CHAT_KEYS)} чат-ключей и {len(SEARCH_KEYS)} поиск-ключей.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
