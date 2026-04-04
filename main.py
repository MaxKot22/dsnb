import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from google import genai

# 1. ФЕЙК-СЕРВЕР
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

# 2. НАСТРОЙКИ
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

client = genai.Client(api_key=GEMINI_KEY)

# АВТО-ПОДБОР МОДЕЛИ
def get_working_model():
    try:
        models = list(client.models.list())
        # Ищем любую модель, которая поддерживает генерацию контента
        for m in models:
            if "generateContent" in m.supported_methods:
                print(f"--- НАЙДЕНА РАБОЧАЯ МОДЕЛЬ: {m.name} ---")
                return m.name
        return "gemini-1.5-flash" # Запасной вариант
    except Exception as e:
        print(f"Ошибка при поиске моделей: {e}")
        return "gemini-1.5-flash"

MODEL_ID = get_working_model()

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(f"Я запущен! Использую модель: {MODEL_ID}")

@dp.message()
async def handle_message(message: types.Message):
    if not message.text: return
    
    bot_info = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_info.username}" in message.text:
        try:
            # Используем найденную модель
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=message.text
            )
            await message.reply(response.text)
        except Exception as e:
            await message.reply(f"Ошибка API ({MODEL_ID}): {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
