import os
import asyncio
import aiohttp
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq
from duckduckgo_search import DDGS

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

user_histories = {}
MAX_HISTORY = 5  # последние 5 сообщений

# ---------- Вспомогательные функции для перевода ----------
async def translate_text(text, target_lang="ru"):
    """Переводит текст на целевой язык (ru/en) через Groq"""
    if not text:
        return text
    lang_name = "русский" if target_lang == "ru" else "английский"
    prompt = f"Переведи на {lang_name} (только перевод, без пояснений):\n{text}"
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            max_tokens=300,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return text  # при ошибке возвращаем оригинал

async def translate_to_en(text):
    """Перевод на английский (короткий, для поиска)"""
    if not text:
        return text
    prompt = f"Translate to English for internet search (only translation, no extra text):\n{text}"
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            max_tokens=60,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return text

# ---------- Поиск в интернете через DuckDuckGo ----------
async def web_search(query):
    """Ищет в интернете через DuckDuckGo, переводит запрос на английский, результат переводит на русский"""
    # Переводим запрос на английский
    en_query = await translate_to_en(query)
    if not en_query:
        en_query = query
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(en_query, max_results=3))
            if not results:
                return "Ничего не найдено."
            # Формируем краткую выжимку на английском
            snippets = []
            for r in results:
                snippets.append(f"{r['title']}. {r['body'][:200]}")
            combined = "\n".join(snippets)
            # Переводим результат на русский
            ru_result = await translate_text(combined, "ru")
            return ru_result
    except Exception as e:
        return f"Ошибка поиска: {e}"

# ---------- Погода и время (без изменений) ----------
async def get_weather(city):
    try:
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(geocode_url) as resp:
                data = await resp.json()
                if not data.get("results"):
                    return f"Город '{city}' не найден."
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]
                city_name = data["results"][0]["name"]
                country = data["results"][0]["country"]
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        async with aiohttp.ClientSession() as session:
            async with session.get(weather_url) as resp:
                weather_data = await resp.json()
                current = weather_data["current_weather"]
                temp = current["temperature"]
                wind = current["windspeed"]
                return f"Погода в {city_name}, {country}: {temp}°C, ветер {wind} км/ч."
    except Exception as e:
        return f"Не удалось получить погоду: {e}"

async def get_time(timezone_str="UTC"):
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        return now.strftime("%d.%m.%Y %H:%M:%S")
    except:
        return "Неверный часовой пояс."

# ---------- Обычный ответ через Groq (с памятью) ----------
async def ask_groq(user_id, prompt):
    history = user_histories.get(user_id, [])
    history.append({"role": "user", "content": prompt})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    messages = [
        {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по существу."}
    ] + history

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
            max_tokens=1024,
            temperature=0.7
        )
        reply = chat_completion.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        user_histories[user_id] = history
        return reply
    except Exception as e:
        return f"Ошибка ИИ: {e}"

# ---------- Обработчик сообщений ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # Проверка упоминания
    mentioned = False
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                username = update.message.text[entity.offset:entity.offset+entity.length]
                if username == f"@{context.bot.username}":
                    mentioned = True
                    break
            elif entity.type == "text_mention":
                if entity.user.username == context.bot.username:
                    mentioned = True
                    break
    if (update.message.reply_to_message and 
        update.message.reply_to_message.from_user.username == context.bot.username):
        mentioned = True

    if not mentioned:
        return

    user_text = update.message.text
    clean_text = user_text.replace(f"@{context.bot.username}", "").strip()
    if not clean_text:
        return

    user_id = update.message.from_user.id
    lower = clean_text.lower()

    # ---- Погода ----
    if "погод" in lower:
        if "в " in lower:
            city = clean_text.split("в ", 1)[1].strip()
        else:
            city = "Москва"
        reply = await get_weather(city)
        await update.message.reply_text(reply)
        return

    # ---- Время ----
    if "врем" in lower or "сколько времени" in lower:
        if "в " in lower:
            tz_part = clean_text.split("в ", 1)[1].strip()
            tz_map = {
                "москва": "Europe/Moscow",
                "нью-йорк": "America/New_York",
                "лондон": "Europe/London",
                "токио": "Asia/Tokyo",
            }
            tz = tz_map.get(tz_part.lower(), "UTC")
        else:
            tz = "UTC"
        reply = f"Текущее время: {await get_time(tz)} (пояс {tz})"
        await update.message.reply_text(reply)
        return

    # ---- Интернет-поиск (автоматически, если есть ключевые слова) ----
    search_keywords = ["найди", "поищи", "узнай", "что такое", "кто такой", "какой", "где", "когда", "сколько"]
    if any(kw in lower for kw in search_keywords):
        reply = await web_search(clean_text)
        await update.message.reply_text(reply)
        return

    # ---- Обычный вопрос через ИИ ----
    reply = await ask_groq(user_id, clean_text)
    await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
