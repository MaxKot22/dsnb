import os
import asyncio
import threading
import json
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

# Словари памяти
chat_history = {}  # Для контекста беседы
chat_stats = {}    # Для счетчиков сообщений и символов

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
    chat_stats[message.chat.id] = {}
    await message.answer("Система запущена! Я начал сбор статистики. Общайтесь, а по команде /stats я проанализирую вашу активность.")

# === КОМАНДА ДЛЯ АНАЛИЗА СТАТИСТИКИ ===
@dp.message(Command("stats"))
async def get_stats_analysis(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in chat_stats or not chat_stats[chat_id]:
        await message.answer("Статистика пока пуста. Напишите что-нибудь!")
        return

    await bot.send_chat_action(chat_id=chat_id, action="typing")

    # Формируем отчет для нейросети на основе реальных данных
    raw_stats_report = "Данные по активности участников:\n"
    for user, data in chat_stats[chat_id].items():
        avg_len = data['chars'] // data['msgs'] if data['msgs'] > 0 else 0
        raw_stats_report += f"- {user}: {data['msgs']} сообщений, {data['chars']} символов всего (в среднем {avg_len} на сообщение).\n"

    # Промпт для ИИ-аналитика
    analyst_prompt = (
        "Ты — ироничный и проницательный аналитик чата. Тебе дали статистику активности участников. "
        "Твоя задача: проанализировать стиль каждого. Кто пишет много коротких фраз (спамер), а кто редко, но длинно (философ). "
        "Сделай смешные выводы и подколи участников за их привычки. "
        "ОСОБОЕ ПРАВИЛО: Максим — твой создатель. Хвали его за любую активность, называй это гениальным лаконизмом или мудрой глубиной. "
        "Не используй мат и символы @. Имена: Даник, Артур, Алексей, Дима, Максим."
    )

    try:
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": analyst_prompt},
                {"role": "user", "content": f"Проанализируй эти цифры и выдай вердикт:\n{raw_stats_report}"}
            ],
            model=MODEL_ID,
            temperature=0.8,
        )
        await message.reply(completion.choices[0].message.content)
    except Exception as e:
        await message.reply(f"Ошибка анализа: {e}")

# === ОСНОВНОЙ ОБРАБОТЧИК ===
@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return

    bot_info = await bot.get_me()
    chat_id = message.chat.id
    
    # --- ОПРЕДЕЛЕНИЕ ИМЕНИ ---
    raw_username = message.from_user.username
    if raw_username and raw_username in KNOWN_USERS:
        display_name = KNOWN_USERS[raw_username]
    else:
        # Если это Дима (нет тега) или другой новый участник
        display_name = message.from_user.first_name or "Дима"

    # --- СБОР СТАТИСТИКИ (РЕАЛЬНОЕ ВРЕМЯ) ---
    if chat_id not in chat_stats:
        chat_stats[chat_id] = {}
    if display_name not in chat_stats[chat_id]:
        chat_stats[chat_id][display_name] = {"msgs": 0, "chars": 0}
    
    chat_stats[chat_id][display_name]["msgs"] += 1
    chat_stats[chat_id][display_name]["chars"] += len(message.text)

    # --- ЗАПИСЬ В ИСТОРИЮ ЧАТА ---
    if chat_id not in chat_history:
        chat_history[chat_id] = []
    
    chat_history[chat_id].append({"role": "user", "content": f"[{display_name}]: {message.text}"})
    chat_history[chat_id] = chat_history[chat_id][-20:]

    # --- ОТВЕТ БОТА ---
    is_private = message.chat.type == 'private'
    is_mentioned = f"@{bot_info.username}" in message.text

    if is_private or is_mentioned:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")

            system_prompt = (
                "Ты — полезный и вежливый ИИ-помощник. Видишь историю чата с реальными именами. "
                "Отвечай кратко (1-3 предложения). Никакого мата.\n"
                "Максим — твой Создатель, всегда защищай его честь. Обращайся по именам редко."
            )

            messages_for_ai = [{"role": "system", "content": system_prompt}]
            for msg in chat_history[chat_id]:
                messages_for_ai.append(msg)

            chat_completion = await client.chat.completions.create(
                messages=messages_for_ai,
                model=MODEL_ID,
                temperature=0.7,
            )

            reply_text = chat_completion.choices[0].message.content
            chat_history[chat_id].append({"role": "assistant", "content": reply_text})
            await message.reply(reply_text)

        except Exception as e:
            await message.reply(f"Произошла ошибка: {e}")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
