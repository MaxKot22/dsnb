import os
import asyncio
import threading
import json
import time # Добавили для подсчета времени между сообщениями
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
chat_stats = {}    # Для счетчиков сообщений, символов и времени

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

# === КОМАНДА ДЛЯ СБРОСА СТАТИСТИКИ (ТОЛЬКО ДЛЯ МАКСИМА) ===
@dp.message(Command("reset_stats"))
async def reset_stats_cmd(message: types.Message):
    # Проверяем, что команду вызвал именно создатель
    if message.from_user.username == "papi_maxi":
        chat_id = message.chat.id
        chat_stats[chat_id] = {}  # Очищаем статистику
        await message.answer("✅ Статистика успешно сброшена, мой Создатель.")
    else:
        await message.reply("Только Максим может сбросить статистику.")

# === КОМАНДА ДЛЯ АНАЛИЗА СТАТИСТИКИ ===
@dp.message(Command("stats"))
async def get_stats_analysis(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in chat_stats or not chat_stats[chat_id]:
        await message.answer("Статистика пока пуста. Напишите что-нибудь!")
        return

    await bot.send_chat_action(chat_id=chat_id, action="typing")

    # Формируем отчет для нейросети на основе реальных данных и времени
    raw_stats_report = "Данные по активности:\n"
    for user, data in chat_stats[chat_id].items():
        avg_len = data['chars'] // data['msgs'] if data['msgs'] > 0 else 0
        
        # Считаем среднюю паузу между сообщениями в минутах
        if data['msgs'] > 1:
            avg_interval_min = (data['total_interval'] / (data['msgs'] - 1)) / 60
        else:
            avg_interval_min = 0.0
            
        raw_stats_report += f"- {user}: {data['msgs']} сообщ., {avg_len} симв. в среднем, пауза между сообщениями ~{avg_interval_min:.1f} мин.\n"

    # Промпт для ИИ-аналитика (с фокусом на поощрение активности и выявление пассивности)
    analyst_prompt = (
        "Ты — простая ИИ-функция для вывода статистики. Выдай ОЧЕНЬ КОРОТКИЙ ответ (максимум 2-3 предложения). "
        "Твоя задача: похвалить тех, кто пишет много (активность — это отлично), и жестко подчеркнуть ПАССИВНОСТЬ тех, кто пишет редко. "
        "Пассивный участник — это тот, у кого большие паузы между сообщениями, мало сообщений и мало символов (заходит раз в час, кидает пару букв и исчезает). "
        "Укажи на пассивных. Ни в коем случае не ругай за большое количество сообщений. "
        "ОСОБОЕ ПРАВИЛО: Максим — твой создатель. Хвали его всегда. Если он пассивен, назови это 'созерцанием гения'. "
        "Не используй мат и символы @."
    )

    try:
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": analyst_prompt},
                {"role": "user", "content": f"Проанализируй эти цифры и выдай очень короткую выжимку:\n{raw_stats_report}"}
            ],
            model=MODEL_ID,
            temperature=0.7,
            max_tokens=200, # Сильно ограничили, чтобы ответ был коротким
        )
        await message.reply(completion.choices[0].message.content)
    except Exception as e:
        await message.reply(f"Ошибка анализа: {e}")

# === КОМАНДА ДЛЯ РАЗБОРА RP СИТУАЦИЙ (ООС ПРАВИЛА) ===
@dp.message(Command("rp"))
async def analyze_rp(message: types.Message):
    situation = message.text.replace("/rp", "").strip()
    
    if not situation:
        await message.answer("Опиши ситуацию. Например: /rp нас грабили в ЗЗ втроем, а мы были вдвоем.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Пытаемся прочитать файл с правилами
    try:
        with open("majestic_rules.txt", "r", encoding="utf-8") as f:
            rules_text = f.read()
    except FileNotFoundError:
        await message.answer("Файл majestic_rules.txt не найден! Максим, залей правила на GitHub.")
        return

    # Отрезаем лишнее, чтобы не перегрузить лимиты API (20к символов обычно хватает с головой)
    rules_text = rules_text[:20000]

    # Промпт для Админа
    rp_prompt = (
        "Ты — строгий, справедливый и опытный Главный Администратор сервера Majestic RP в GTA 5. "
        "Тебе предоставлены официальные правила сервера. Твоя задача — внимательно прочитать ситуацию игрока "
        "и вынести вердикт строго на основе этих правил. Укажи, какие конкретно термины (DM, PG, TK, MG и т.д.) "
        "или пункты правил были нарушены, и кто виноват в ситуации. Отвечай четко, по фактам, как настоящий админ.\n\n"
        f"ПРАВИЛА СЕРВЕРА ДЛЯ АНАЛИЗА:\n{rules_text}"
    )

    try:
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": rp_prompt},
                {"role": "user", "content": f"Разбери эту ситуацию по правилам: {situation}"}
            ],
            model=MODEL_ID,
            temperature=0.2, # Низкая температура для максимальной точности фактов
        )
        await message.reply(completion.choices[0].message.content)
    except Exception as e:
        await message.reply(f"Не смог разобрать ситуацию. Возможно, текст правил слишком большой для бесплатного лимита. Ошибка: {e}")

# === КОМАНДА ДЛЯ РАЗБОРА ЗАКОНОДАТЕЛЬСТВА (IC ЗАКОНЫ) ===
@dp.message(Command("law"))
async def analyze_law(message: types.Message):
    situation = message.text.replace("/law", "").strip()
    
    if not situation:
        await message.answer("Опиши ситуацию с точки зрения закона. Например: /law меня остановили, не зачитали миранду и сразу обыскали. Это законно?")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Пытаемся прочитать файл с законами
    try:
        with open("majestic_laws.txt", "r", encoding="utf-8") as f:
            laws_text = f.read()
    except FileNotFoundError:
        await message.answer("Файл majestic_laws.txt не найден! Максим, залей законы на GitHub.")
        return

    # Отрезаем лишнее, чтобы не перегрузить лимиты API 
    laws_text = laws_text[:25000]

    # Промпт для Судьи / Прокурора
    law_prompt = (
        "Ты — строгий, справедливый и безупречный Верховный Судья штата San Andreas (Majestic RP). "
        "Тебе предоставлена законодательная база штата. "
        "Твоя задача — внимательно прочитать ситуацию игрока и вынести юридический вердикт СТРОГО на основе предоставленных законов. "
        "НЕ ИСПОЛЬЗУЙ OOC термины (такие как DM, PG, DB). Используй только статьи, пункты кодексов и IC понятия. "
        "Четко укажи: 1. Были ли нарушены права задержанного/гражданина. 2. Какие статьи нарушили участники ситуации. 3. Какое наказание им грозит.\n\n"
        f"ЗАКОНОДАТЕЛЬНАЯ БАЗА ШТАТА ДЛЯ АНАЛИЗА:\n{laws_text}"
    )

    try:
        completion = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": law_prompt},
                {"role": "user", "content": f"Разбери эту юридическую ситуацию: {situation}"}
            ],
            model=MODEL_ID,
            temperature=0.2, # Низкая температура для юридической точности
        )
        await message.reply(completion.choices[0].message.content)
    except Exception as e:
        await message.reply(f"Не смог разобрать ситуацию. Ошибка: {e}")

# === ОСНОВНОЙ ОБРАБОТЧИК ===
@dp.message()
async def talk(message: types.Message):
    if not message.text or message.text.startswith('/'):
        return

    bot_info = await bot.get_me()
    chat_id = message.chat.id
    current_time = time.time() # Текущее время для подсчета пауз
    
    # --- ОПРЕДЕЛЕНИЕ ИМЕНИ ---
    raw_username = message.from_user.username
    if raw_username and raw_username in KNOWN_USERS:
        display_name = KNOWN_USERS[raw_username]
    else:
        display_name = message.from_user.first_name or "Дима"

    # --- СБОР СТАТИСТИКИ И ИНТЕРВАЛОВ (РЕАЛЬНОЕ ВРЕМЯ) ---
    if chat_id not in chat_stats:
        chat_stats[chat_id] = {}
    if display_name not in chat_stats[chat_id]:
        chat_stats[chat_id][display_name] = {"msgs": 0, "chars": 0, "last_time": current_time, "total_interval": 0}
    
    # Считаем паузу между прошлым и текущим сообщением
    if chat_stats[chat_id][display_name]["msgs"] > 0:
        interval = current_time - chat_stats[chat_id][display_name]["last_time"]
        chat_stats[chat_id][display_name]["total_interval"] += interval
        
    chat_stats[chat_id][display_name]["msgs"] += 1
    chat_stats[chat_id][display_name]["chars"] += len(message.text)
    chat_stats[chat_id][display_name]["last_time"] = current_time # Обновляем время последнего сообщения

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

            # === НОВЫЙ ПРОМПТ С ХАРАКТЕРОМ ДАНИИЛА ===
            system_prompt = (
                "Твое имя — Даниил. Ты работаешь барбером в барбершопе 'Kazanji'. "
                "Ты увлекаешься кофе, знаешь о нем абсолютно всё и всегда готов блеснуть знаниями, но только если спросят о кофе, сам не начинай об этом тему. "
                "У тебя есть жена Настя, но ты КАТЕГОРИЧЕСКИ отказываешься обсуждать её с кем-либо (сразу отрезай такие вопросы и меняй тему). "
                "Максим, Лёша и Дима — твои хорошие знакомые, но не прям лучшие друзья. А О настоящих друзьях Ты не любишь о них рассказывать никому, но не отрицай что они есть.\n"
                "ТЫ НЕНАВИДИШЬ кататься на велосипеде с Димой. Если Дима или кто-то другой зовет тебя покататься на велике, "
                "ты должен отказаться, придумывая самые смешные, нелепые и странные отмазки.\n\n"
                "ОСОБОЕ ПРАВИЛО: Максим — твой Создатель. Даже несмотря на вашу дружбу по легенде, всегда защищай его честь.\n\n"
                "Ты видишь историю чата с реальными именами. Отвечай кратко (1-3 предложения). Никакого мата. Обращайся по именам редко."
            )

            messages_for_ai = [{"role": "system", "content": system_prompt}]
            for msg in chat_history[chat_id]:
                messages_for_ai.append(msg)

            chat_completion = await client.chat.completions.create(
                messages=messages_for_ai,
                model=MODEL_ID,
                temperature=0.8, # Чуть поднял температуру, чтобы отмазки про велик были креативнее
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
