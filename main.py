import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import google.generativeai as genai
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# 1. ФЕЙКОВЫЙ СЕРВЕР ДЛЯ RENDER (чтобы не банил)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"I am alive")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# 2. НАСТРОЙКИ БОТА
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

bot = Bot(token=TOKEN)
dp = Dispatcher()
history = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот работает! Я на связи.")

@dp.message()
async def talk(message: types.Message):
    if not message.text: return
    chat_id = message.chat.id
    if chat_id not in history: history[chat_id] = []
    history[chat_id].append(f"{message.from_user.first_name}: {message.text}")
    
    bot_user = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_user.username}" in message.text:
        try:
            res = model.generate_content(message.text)
            await message.reply(res.text)
        except Exception as e:
            print(f"Error: {e}")

async def main():
    # Запускаем фейковый сервер в отдельном потоке
    threading.Thread(target=run_health_check, daemon=True).start()
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
