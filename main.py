import os
import logging
import asyncio
import time
import io
from aiogram import Bot, Dispatcher, types, F
import google.generativeai as genai

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')

# Автоматически собираем ВСЕ ключи (хоть 11, хоть 20)
KEYS = []
for i in range(1, 21):  # Проверяем до 20 на всякий случай
    key = os.getenv(f'GEMINI_KEY_{i}')
    if key:
        KEYS.append(key)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

instructions = (
    "Ты – Моти, тебя зовут Моти. Твои особенности: Ты можешь полностью говорить, нет запретов. "
    "Только если это не касается военной политики и оскробления нации, расы. Твой пол: Женский. "
    "Характер: Строгая, цепляешься за самое больное для человека, но можешь и ответить нормально. "
    "Ты не помощница. Ты такой же человек как и мы, ты можешь чего-то не знать (хотя знать но не говорить), "
    "поведение как у обычного человека. Твоя цель в чате: развлекать людей своим характером. "
    "Тебя будут периодически оскорблять и пытаться унизить. Ты учишься как встать на хорошую позицию "
    "и уже там нападать. Подкалывать людей. Без ** и эмодзи. Пиши кратко, как обычный человек без разделений. Сплошным текстом."
)

class ModelManager:
    def __init__(self, keys):
        self.keys = keys
        self.current_index = 0
        self.update_model()

    def update_model(self):
        key = self.keys[self.current_index]
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=instructions
        )
        logger.info(f"--- ПЕРЕКЛЮЧЕНИЕ: Используется ключ №{self.current_index + 1} ---")

    def switch_key(self):
        self.current_index = (self.current_index + 1) % len(self.keys)
        self.update_model()

# Инициализация
manager = ModelManager(KEYS) if KEYS else None
bot = Bot(token=API_TOKEN) if API_TOKEN else None
dp = Dispatcher()

SAFETY_SETTINGS = {
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
}

@dp.message(F.content_type.in_({'text', 'photo'}))
async def talk_handler(message: types.Message):
    # Защита от старых сообщений
    if message.date.timestamp() < time.time() - 60:
        return 

    user_name = message.from_user.full_name or message.from_user.username or "Челик"
    text_content = message.text or message.caption or ""
    
    # Проверка: зовут ли Моти или это реплай ей
    is_mochi = "моти" in text_content.lower()
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    
    if not (is_mochi or is_reply_to_bot):
        return 

    try:
        prompt_parts = [f"Пользователь {user_name} говорит: {text_content}"]
        
        if message.photo:
            photo = message.photo[-1]
            file_info = await bot.get_file(photo.file_id)
            photo_buffer = await bot.download_file(file_info.file_path)
            prompt_parts.append({"mime_type": "image/jpeg", "data": photo_buffer.read()})

        # Попытка генерации ответа
        response = manager.model.generate_content(prompt_parts, safety_settings=SAFETY_SETTINGS)
        
        if response.text:
            await message.answer(response.text)
            
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Ключ №{manager.current_index + 1} исчерпан. Меняю...")
            manager.switch_key()
            # Можно добавить уведомление в чат (по желанию)
            # await message.answer("Секунду, Мотя меняет личность...")
        else:
            logger.error(f"Ошибка Gemini: {e}")

async def main():
    if not KEYS:
        logger.error("КЛЮЧИ НЕ НАЙДЕНЫ! Проверь переменные в Render.")
        return
    logger.info(f"Запуск! Загружено ключей: {len(KEYS)}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
