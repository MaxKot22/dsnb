import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai

# Берем ключи из настроек Render
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Настройка ИИ
genai.configure(api_key=GEMINI_KEY)
# ИСПОЛЬЗУЕМ СТАБИЛЬНОЕ ИМЯ МОДЕЛИ
model = genai.GenerativeModel('models/gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Память чата
history = {}

@dp.message(Command("judge"))
async def judge(message: types.Message):
    chat_id = message.chat.id
    chat_data = history.get(chat_id, [])
    if len(chat_data) < 2:
        await message.reply("Мало сообщений для анализа!")
        return
    context = "\n".join(chat_data[-20:])
    try:
        res = model.generate_content(f"Рассуди спор в чате, кто прав? Будь краток:\n{context}")
        await message.reply(res.text)
    except Exception as e:
        await message.reply(f"Ошибка ИИ: {e}")

@dp.message()
async def talk(message: types.Message):
    if not message.text: return
    chat_id = message.chat.id
    if chat_id not in history: history[chat_id] = []
    
    # Запоминаем фразу
    history[chat_id].append(f"{message.from_user.first_name}: {message.text}")
    if len(history[chat_id]) > 30: history[chat_id].pop(0)
    
    # Отвечаем, если это личка или тегнули бота
    bot_user = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_user.username}" in message.text:
        try:
            # Убираем имя бота из запроса
            clean_text = message.text.replace(f"@{bot_user.username}", "").strip()
            res = model.generate_content(clean_text if clean_text else "Привет!")
            await message.reply(res.text)
        except Exception as e:
            await message.reply("У меня возникла проблема с доступом к ИИ. Проверь логи!")
            print(f"ERROR: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
