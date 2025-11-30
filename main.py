from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from flask import Flask, request
import os

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)

# Telegram Bot setup
application = ApplicationBuilder().token(TOKEN).build()


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    main_menu = [
        [KeyboardButton("Today's Nutrition Report")],
        [KeyboardButton("Connect Website Account")],
        [KeyboardButton("FAQ")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! How can I assist you today?",
        reply_markup=reply_markup
    )


# Text menu handler
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "FAQ":
        faq_buttons = [
            [InlineKeyboardButton("Set Calorie Goal", callback_data="faq_calorie")],
            [InlineKeyboardButton("AI Analysis Accuracy", callback_data="faq_accuracy")],
        ]
        markup = InlineKeyboardMarkup(faq_buttons)

        await update.message.reply_text(
            "Please choose one of the frequently asked questions 👇",
            reply_markup=markup
        )


# Inline button handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "faq_calorie":
        await query.edit_message_text("Your calorie goal is automatically set based on your profile!")
    elif query.data == "faq_accuracy":
        await query.edit_message_text("AI accuracy may vary depending on photo quality.")


# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
application.add_handler(CallbackQueryHandler(button_handler))


# Webhook endpoint (Render will call this)
@app.post("/")
def webhook():
    update = Update.de_json(request.json, application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200


# Set webhook on startup
@app.get("/setwebhook")
async def setwebhook():
    await application.bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook set", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
