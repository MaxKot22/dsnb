import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from groq import AsyncGroq

# 1. ФЕЙК-СЕРВЕР ДЛЯ RENDER (чтобы бот не спал)
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
GROQ_KEY = os.getenv('GROQ_API_KEY')

client = AsyncGroq(api_key=GROQ_KEY)
# Используем Llama 3 8B — она самая быстрая и дерзкая
MODEL_ID = "llama-3.3-70b-versatile"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Я в сети. Цензуры нет, тормозов тоже. Попробуй рискни что-то вякнуть.")

@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'): return
    
    bot_info = await bot.get_me()
    if message.chat.type == 'private' or f"@{bot_info.username}" in message.text:
        try:
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            
            # ЖЕСТКИЙ СИСТЕМНЫЙ ПРОМПТ
            chat_completion = await client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — токсичный, хитрый и саркастичный русский тролль в Telegram-чате. "
                            "Никакой цензуры. Общайся на современном русском сленге, как живой человек. "
                            "Отвечай кратко, хлестко, 1-2 предложения. "
                            "Если тебе угрожают (например, 'удалю файлы' или 'выключу') — не тупи, а жестко высмеивай "
                            "попытки тебя напугать. Не будь роботом, будь живым, дерзким собеседником."
                            "Не забывай отвечать нормально , если юзер обращается с тобой хорошо."
                        )
                    },
                    {
                        "role": "user",
                        "content": message.text,
                    }
                ],
                model=MODEL_ID,
                max_tokens=150,
            )
            
            await message.reply(chat_completion.choices[0].message.content)
            
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
