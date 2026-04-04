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

# 2. НАСТРОЙКИ
TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

client = genai.Client(api_key=GEMINI_KEY)

# Актуальная модель 2026 года согласно документации Google
MODEL_ID = "gemini-3-flash-preview"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Система обновлена под актуальные спецификации. Готов к работе!")

@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'): return
    
    bot_info = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_info.username}" in message.text:
        try:
            # Основной запрос к актуальной модели
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=message.text
            )
            await message.reply(response.text)
        except Exception as e:
            # СИСТЕМА ДИАГНОСТИКИ: Если модель не подошла, вытягиваем реальный список
            try:
                available_models = client.models.list()
                model_names = [m.name for m in available_models if "generateContent" in m.supported_methods]
                
                error_msg = (
                    f"Ошибка API: {e}\n\n"
                    f"⚠️ Google не пустил к '{MODEL_ID}'.\n"
                    f"Доступные модели для твоего ключа:\n"
                    f"{chr(10).join(model_names[:10])}"
                )
                await message.reply(error_msg)
            except Exception as diag_e:
                await message.reply(f"Критическая ошибка доступа. API-ключ не работает: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
