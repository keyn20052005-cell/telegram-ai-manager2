import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI

# Токены из переменных окружения (их добавишь на Railway)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализируем AsyncOpenAI клиент
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Функция для ответа через ChatGPT
async def ask_gpt(prompt):
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка: {e}"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши мне сообщение, упомянув бота (@telegram_ai_manager_bot), и я отвечу через ChatGPT!"
    )

# Обработчик сообщений (отвечает только когда упоминают)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, упоминается ли бот в сообщении
    if update.message.text and f"@{context.bot.username}" in update.message.text:
        user_text = update.message.text
        # Убираем упоминание
        clean_text = user_text.replace(f"@{context.bot.username}", "").strip()
        if clean_text:
            # Показываем, что бот печатает
            await update.message.chat.send_action("typing")
            reply = await ask_gpt(clean_text)
            await update.message.reply_text(reply)
    # Также отвечаем на ответы на сообщения бота
    elif update.message.reply_to_message and update.message.reply_to_message.from_user.username == context.bot.username:
        user_text = update.message.text
        if user_text:
            await update.message.chat.send_action("typing")
            reply = await ask_gpt(user_text)
            await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен и ждет сообщений...")
    app.run_polling()

if __name__ == "__main__":
    main()
