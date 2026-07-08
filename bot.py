import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import openai

# Токены из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Функция для ответа через ChatGPT
async def ask_gpt(prompt):
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при запросе к ИИ: {e}"

# Обработчик сообщений – отвечает, только когда бота упомянули
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, есть ли упоминание бота
    if update.message.mention or (
        update.message.reply_to_message and
        update.message.reply_to_message.from_user.username == context.bot.username
    ):
        user_text = update.message.text
        # Убираем упоминание из текста
        clean_text = user_text.replace(f"@{context.bot.username}", "").strip()
        if clean_text:
            reply = await ask_gpt(clean_text)
            await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if name == "__main__":
    main()
