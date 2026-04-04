import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# 1. ФЕЙК-СЕРВЕР ДЛЯ RENDER
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I am alive")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 2. НАСТРОЙКИ
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Проверка ключа Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=TOKEN)
dp = Dispatcher()
history = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("ИИ-бот на связи! Попробуй написать мне что-нибудь.")

@dp.message()
async def talk(message: types.Message):
    if not message.text: return
    
    chat_id = message.chat.id
    if chat_id not in history: history[chat_id] = []
    
    # Сохраняем контекст (имя: текст)
    history[chat_id].append(f"{message.from_user.first_name}: {message.text}")
    if len(history[chat_id]) > 20: history[chat_id].pop(0)

    # Проверяем: личка или упоминание
    bot_user = await bot.get_me()
    is_private = message.chat.type == 'private'
    is_mentioned = f"@{bot_user.username}" in message.text
    
    if is_private or is_mentioned:
        try:
            # Запрос к ИИ
            prompt = "\n".join(history[chat_id])
            response = model.generate_content(prompt)
            
            if response.text:
                await message.reply(response.text)
            else:
                await message.reply("ИИ прислал пустой ответ. Проверь настройки API.")
                
        except Exception as e:
            # Бот сам скажет, если ИИ выдал ошибку
            await message.reply(f"Ошибка ИИ: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
