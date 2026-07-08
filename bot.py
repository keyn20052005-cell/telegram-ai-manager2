import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

user_histories = {}

MAX_HISTORY = 10          # всего 10 сообщений на пользователя
MAX_MSG_LEN = 500         # каждое сообщение не длиннее 500 символов

async def ask_groq_with_history(user_id, new_message):
    history = user_histories.get(user_id, [])
    
    # Обрезаем новое сообщение
    if len(new_message) > MAX_MSG_LEN:
        new_message = new_message[:MAX_MSG_LEN]
    
    history.append({"role": "user", "content": new_message})
    
    # Оставляем только последние MAX_HISTORY
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    
    messages = [
        {"role": "system", "content": "Ты полезный ассистент с доступом в интернет. Отвечай кратко, но информативно."}
    ] + history
    
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="groq/compound",
            max_tokens=1024,        # уменьшили до 1024
            temperature=0.7
        )
        reply = chat_completion.choices[0].message.content
        
        # Обрезаем ответ, если он слишком длинный, перед сохранением
        if len(reply) > MAX_MSG_LEN:
            reply = reply[:MAX_MSG_LEN]
        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        user_histories[user_id] = history
        
        return reply
    except Exception as e:
        return f"Ошибка при запросе к ИИ: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
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
