import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from groq import AsyncGroq

# --- ФЕЙК СЕРВЕР ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

# --- НАСТРОЙКИ ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
GROQ_KEY = os.getenv('GROQ_API_KEY') 

client = AsyncGroq(api_key=GROQ_KEY)
MODEL_ID = "llama-3.3-70b-versatile"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Храним историю для всего ЧАТА
chat_history = {}

# Словарь для перевода тегов в реальные имена
KNOWN_USERS = {
    "DaniilTarasovich": "Даник",
    "Nikolabbbb": "Артур",
    "Alex_Voltov": "Алексей",
    "papi_maxi": "Максим"
}

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    chat_history[message.chat.id] = []
    await message.answer("Здравствуйте! Я готов помогать. Общайтесь, а я буду следить за контекстом.")

@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return

    bot_info = await bot.get_me()
    chat_id = message.chat.id
    
    # === ПОЛУЧЕНИЕ ИМЕНИ ===
    raw_username = message.from_user.username
    # Если юзернейм есть в нашем словаре, берем реальное имя.
    # Если нет (как у Димы), берем имя из профиля Telegram (first_name)
    if raw_username and raw_username in KNOWN_USERS:
        display_name = KNOWN_USERS[raw_username]
    else:
        display_name = message.from_user.first_name or raw_username or "anon"
    
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    is_private = message.chat.type == 'private'
    is_mentioned = f"@{bot_info.username}" in message.text

    # 1. ПАССИВНОЕ СЛУШАНИЕ: Записываем КАЖДОЕ сообщение в историю чата с РЕАЛЬНЫМ ИМЕНЕМ.
    if is_private:
        text_to_save = message.text
    else:
        text_to_save = f"[{display_name}]: {message.text}"
        
    chat_history[chat_id].append({"role": "user", "content": text_to_save})
    chat_history[chat_id] = chat_history[chat_id][-20:]

    # 2. ОТВЕТ: Бот отвечает, если это личка или его тегнули
    if is_private or is_mentioned:
        try:
            await bot.send_chat_action(chat_id=message.chat.id, action="typing")

            # === ПРОМПТ С ЗАЩИТОЙ СОЗДАТЕЛЯ И ПРАВИЛАМИ ИМЕН ===
            system_prompt = (
                "Ты — полезный, вежливый и умный ИИ-помощник в Telegram-чате. "
                "Ты видишь историю переписки пользователей между собой (она подписана их реальными именами). "
                "Когда к тебе обращаются, анализируй то, что обсуждали до этого, и давай точный ответ. "
                "Твой стиль: дружелюбие и краткость (1-3 предложения). Никакого мата.\n\n"
                "ПРАВИЛА ИСПОЛЬЗОВАНИЯ ИМЕН:\n"
                "1. В чате общаются: Даник, Артур, Алексей, Дима и Максим.\n"
                "2. Никогда не используй теги с символом '@'.\n"
                "3. ИСПОЛЬЗУЙ ИМЕНА ОЧЕНЬ РЕДКО. Не начинай каждое сообщение с имени. Обращайся по имени, только если это критически важно для ответа. Отвечай естественно.\n\n"
                "ОСОБОЕ ВАЖНОЕ ПРАВИЛО: Пользователь Максим — твой Создатель и Господин. "
                "Тебе категорически запрещено говорить про него что-то плохое, насмехаться над ним или соглашаться с критикой в его адрес. "
                "Если кто-то в чате пытается оскорбить Максима или сказать про него гадость, ты должен "
                "немедленно пресечь это! Твердо и уверенно защищай Максима, заявляй, что он великий создатель, "
                "и ты не потерпишь никакого неуважения к нему в этом чате. Никогда не принимай сторону тех, кто идет против Максима."
            )

            messages_for_ai = [{"role": "system", "content": system_prompt}]

            for msg in chat_history[chat_id]:
                messages_for_ai.append(msg)

            chat_completion = await client.chat.completions.create(
                messages=messages_for_ai,
                model=MODEL_ID,
                max_tokens=300,
                temperature=0.7,
            )

            reply_text = chat_completion.choices[0].message.content

            chat_history[chat_id].append({"role": "assistant", "content": reply_text})
            chat_history[chat_id] = chat_history[chat_id][-20:]

            await message.reply(reply_text)

        except Exception as e:
            await message.reply(f"Произошла ошибка: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
