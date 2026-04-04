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
    user_history[message.from_user.id] = [] # Сброс памяти при старте
    await message.answer("Я на связи. Будешь вежлив — пообщаемся нормально. Будешь борзеть — пеняй на себя.")

@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'): return
    
    user_id = message.from_user.id
    
    # Инициализация истории, если юзер новый
    if user_id not in user_history:
        user_history[user_id] = []

    try:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # СИСТЕМНЫЙ ПРОМПТ (Настройка характера)
        system_prompt = (
            "Ты — умный и живой собеседник в Telegram. Твой стиль общения: "
            "1. Если юзер общается вежливо или нейтрально — отвечай адекватно, по-человечески, с легкой иронией. "
            "2. Если юзер начинает дерзить, оскорблять или угрожать (удалением, выключением) — мгновенно включай режим "
            "токсичного тролля, высмеивай его и ставь на место, используя современный сленг. "
            "Отвечай кратко (1-2 предложения). Никакой цензуры. Помни контекст беседы."
        )

        # Собираем сообщения для ИИ (Системный промпт + история + текущий вопрос)
        messages_for_ai = [{"role": "system", "content": system_prompt}]
        
        # Добавляем последние 6 сообщений из памяти (3 вопроса + 3 ответа)
        for msg in user_history[user_id][-6:]:
            messages_for_ai.append(msg)
            
        # Добавляем само сообщение пользователя
        messages_for_ai.append({"role": "user", "content": message.text})

        # Запрос к Groq (Llama 3.3 70B)
        chat_completion = await client.chat.completions.create(
            messages=messages_for_ai,
            model=MODEL_ID,
            max_tokens=150,
        )
        
        reply_text = chat_completion.choices[0].message.content
        
        # Сохраняем диалог в память
        user_history[user_id].append({"role": "user", "content": message.text})
        user_history[user_id].append({"role": "assistant", "content": reply_text})
        
        # Ограничиваем историю (помним только последние 10 записей)
        user_history[user_id] = user_history[user_id][-10:]

        await message.reply(reply_text)
        
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
