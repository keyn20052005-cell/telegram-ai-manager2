import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Словарь для хранения истории диалога по каждому пользователю
# Ключ: user_id, значение: список из последних 100 сообщений (каждое в формате {"role": "user" или "assistant", "content": текст})
user_histories = {}

# Максимальное количество хранимых сообщений на пользователя
MAX_HISTORY = 100

async def ask_groq_with_history(user_id, new_message):
    """Отправляет запрос в Groq с учётом истории пользователя"""
    # Получаем историю пользователя (или создаём новую)
    history = user_histories.get(user_id, [])
    
    # Добавляем новое сообщение пользователя в историю
    history.append({"role": "user", "content": new_message})
    
    # Если история стала длиннее MAX_HISTORY, обрезаем самое старое сообщение
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    
    # Формируем список сообщений для Groq: системная инструкция + вся история
    messages = [
        {"role": "system", "content": "Ты полезный ассистент, который отвечает на вопросы. У тебя есть доступ к интернету для поиска актуальной информации."}
    ] + history
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="groq/compound",  # даёт доступ к интернету и инструментам
            max_tokens=2048,        # увеличенный лимит
            temperature=0.7
        )
        reply = chat_completion.choices[0].message.content
        
        # Сохраняем ответ ассистента в историю
        history.append({"role": "assistant", "content": reply})
        # Обновляем историю пользователя
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        user_histories[user_id] = history
        
        return reply
    except Exception as e:
        return f"Ошибка при запросе к ИИ: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    # Проверяем, упомянут ли бот
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
    
    if mentioned:
        user_text = update.message.text
        clean_text = user_text.replace(f"@{context.bot.username}", "").strip()
        if clean_text:
            user_id = update.message.from_user.id
            reply = await ask_groq_with_history(user_id, clean_text)
            await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
