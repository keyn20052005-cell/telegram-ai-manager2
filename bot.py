import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

async def ask_groq(prompt):
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            max_tokens=300
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Ошибка: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.mention or (
        update.message.reply_to_message and
        update.message.reply_to_message.from_user.username == context.bot.username
    ):
        user_text = update.message.text
        clean_text = user_text.replace(f"@{context.bot.username}", "").strip()
        if clean_text:
            reply = await ask_groq(clean_text)
            await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
