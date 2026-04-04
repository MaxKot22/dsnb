import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from groq import AsyncGroq

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
GROQ_KEY = os.getenv('GROQ_API_KEY')

client = AsyncGroq(api_key=GROQ_KEY)
MODEL_ID = "llama-3.3-70b-versatile"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище памяти бота (контекст)
user_history = {}

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_history[message.from_user.id] = [] 
    await message.answer("Я на связи. Будешь вежлив — пообщаемся нормально. Будешь борзеть — пеняй на себя.")

@dp.message()
async def talk(message: types.Message):
    # Игнорируем пустые сообщения и команды
    if not message.text or message.text.startswith('/'): return
    
    bot_info = await bot.get_me()
    # Условие: отвечаем, если это ЛС ИЛИ если в тексте есть упоминание бота через @
    is_private = message.chat.type == 'private'
    is_mentioned = f"@{bot_info.username}" in message.text

    if is_private or is_mentioned:
        user_id = message.from_user.id
        
        if user_id not in user_history:
            user_history[user_id] = []

        try:
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")
            
            # Убираем @username из текста, чтобы ИИ не воспринимал свой ник как часть вопроса
            clean_text = message.text.replace(f"@{bot_info.username}", "").strip()

            # СИСТЕМНЫЙ ПРОМПТ (Твой характер)
            system_prompt = (
                "Ты — обычный парень из русского телеграм-чата. Твой стиль — краткость и ирония. "
                "1. Если юзер общается нормально — будь адекватным, отвечай как живой человек, а не нейросеть. "
                "2. Если юзер дерзит или угрожает — отвечай жестко, используй сарказм и ставь его на место. "
                "Используй 1-2 коротких предложения. Помни контекст беседы."
            )

            # Собираем контекст: Промпт + История + Новое сообщение
            messages_for_ai = [{"role": "system", "content": system_prompt}]
            
            for msg in user_history[user_id][-6:]:
                messages_for_ai.append(msg)
                
            messages_for_ai.append({"role": "user", "content": clean_text})

            # Запрос к Groq
            chat_completion = await client.chat.completions.create(
                messages=messages_for_ai,
                model=MODEL_ID,
                max_tokens=150,
            )
            
            reply_text = chat_completion.choices[0].message.content
            
            # Сохраняем в память (именно чистый текст и ответ бота)
            user_history[user_id].append({"role": "user", "content": clean_text})
            user_history[user_id].append({"role": "assistant", "content": reply_text})
            
            # Ограничиваем историю 10 записями
            user_history[user_id] = user_history[user_id][-10:]

            await message.reply(reply_text)
            
        except Exception as e:
            await message.reply(f"Ошибка: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
