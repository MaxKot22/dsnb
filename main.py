import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from google import genai

# 1. ФЕЙК-СЕРВЕР ДЛЯ RENDER
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

# 2. НАСТРОЙКИ КЛЮЧЕЙ
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Инициализация нового клиента Google AI
client = genai.Client(api_key=GEMINI_KEY)
MODEL_ID = "gemini-1.5-flash"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Бот обновлен до последней версии API! Я готов к общению.")

@dp.message()
async def handle_message(message: types.Message):
    if not message.text: return
    
    # Отвечаем в личке или если тегнули
    bot_info = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_info.username}" in message.text:
        try:
            # Новый способ вызова Gemini (через новый SDK)
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=message.text
            )
            await message.reply(response.text)
        except Exception as e:
            await message.reply(f"Ошибка нового API: {e}")

async def main():
    # Запуск проверки здоровья для Render
    threading.Thread(target=run_health_check, daemon=True).start()
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
