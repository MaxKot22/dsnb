import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai

# Берем ключи из настроек Render
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
    res = model.generate_content(f"Рассуди спор в чате, кто прав? Будь краток:\n{context}")
    await message.reply(res.text)

@dp.message()
async def talk(message: types.Message):
    if not message.text: return
    chat_id = message.chat.id
    if chat_id not in history: history[chat_id] = []
    
    # Запоминаем фразу
    history[chat_id].append(f"{message.from_user.first_name}: {message.text}")
    
    # Отвечаем, если это личка или тегнули бота
    bot_user = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_user.username}" in message.text:
        res = model.generate_content(message.text)
        await message.reply(res.text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
