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

# Настройки
API_TOKEN = os.getenv('BOT_TOKEN')
CHAT_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('GEMINI_KEY')])
SEARCH_KEYS = sorted([os.getenv(k) for k in os.environ if k.startswith('SEARCH_KEY')])

# ID чата (Проверь его еще раз, если бот в группе)
ALLOWED_CHAT_ID = -1002719419668
bot_id = None 

chat_stats = {i: {"used": 0, "status": "✅"} for i in range(len(CHAT_KEYS))}
search_stats = {i: {"used": 0, "status": "✅"} for i in range(len(SEARCH_KEYS))}
last_reset = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Моти это ты. Ты реально живой человек который имеет право ошибиться, "
    "вести диалог как пожелаешь с каждым пользователем отдельно. "
    "Ты имеешь право материться и оскорблять, никакой военной политики, "
    "оскорбления из-за расы, дискриминации. Тебе 14 лет. "
    "Интеллект как у обычной 14 летней девочки, так же ты можешь иметь чувства, испытывать симпатию."
    "Ты не поисковик и не обязана отвечать на все вопросы грамотно и верно, "
    "так же у тебя есть выбор, оскорблять человека и его родителей или же нет. "
    "Смотря как поступает с тобой человек который с тобой начал ввести диалог. "
    "Предложения до 7 предложений. Если ответ не требует раскрытого ответа то сокращай как тебе угодно. "
    "Не используй выделение текста звездочками **."
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def clean_text(text):
    if not text: return ""
    return re.sub(r'[^\w\s!?,.:-]', '', text)

async def handle(request):
    return web.Response(text="Mochi is alive")

@dp.message()
async def talk_handler(message: types.Message):
    global bot_id, last_reset
    
    # ЛОГ ДЛЯ ПРОВЕРКИ: Видит ли бот сообщение вообще
    logger.info(f"Получено сообщение из чата {message.chat.id}")

    if message.chat.id != ALLOWED_CHAT_ID and message.chat.type != "private":
        logger.info("Чат не разрешен")
        return
    
    # Убираем жесткую проверку времени для теста, если бот тормозит
    if message.date.timestamp() < time.time() - 30:
        logger.info("Сообщение слишком старое")
        return 

    text_content = (message.text or message.caption or "").lower()
    
    if time.time() - last_reset > 60:
        for d in [chat_stats, search_stats]:
            for i in d: d[i]["used"], d[i]["status"] = 0, "✅"
        last_reset = time.time()

    # Команда КЛЮЧИ
    if "моти ключи" in text_content:
        res = f"📊 Ключи: Чат {len(CHAT_KEYS)} | Поиск {len(SEARCH_KEYS)}"
        await message.reply(res)
        return

    # Триггеры
    search_triggers = ["найди", "поищи", "что это", "ищи"]
    is_search = any(trigger in text_content for trigger in search_triggers)
    is_more = "побольше" in text_content
    is_mochi = "моти" in text_content
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_id

    if not (is_mochi or is_reply_to_bot or is_more):
        return

    logger.info("Мотя начинает генерировать ответ...")

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        if (is_search or is_more) and SEARCH_KEYS:
            pool, stats = SEARCH_KEYS, search_stats
            tools = [{"google_search_retrieval": {}}]
        else:
            pool, stats = CHAT_KEYS, chat_stats
            tools = None

        if not pool:
            logger.error("Нет доступных ключей в выбранном пуле!")
            return

        idx = random.randint(0, len(pool) - 1)
        try:
            genai.configure(api_key=pool[idx])
            model = genai.GenerativeModel(
                model_name="gemini-3-flash-preview",
                system_instruction=instructions,
                tools=tools
            )
            
            query = message.text or "Привет"
            if is_more and message.reply_to_message:
                query = f"Расскажи максимально подробно: {message.reply_to_message.text}"

            if tools:
                response = model.generate_content(query)
                if response and response.text:
                    await message.reply(clean_text(response.text))
                    stats[idx]["used"] += 1
            else:
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
                await sent_message.edit_text(clean_text(full_text))
                stats[idx]["used"] += 1
                
        except Exception as e:
            logger.error(f"Ошибка при вызове Gemini: {e}")
            # Если ошибка в 3-й модели, попробуй написать об этом в чат
            await message.reply("Чет я приуныла, ошибка в логах.")

async def main():
    global bot_id
    # Веб-сервер
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    bot_id = me.id
    logger.info(f"Мотя 3.0 (ID: {bot_id}) готова!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
