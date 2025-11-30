from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import os


TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/"


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    main_menu = [
        [KeyboardButton("Today's Nutrition Report")],
        [KeyboardButton("Connect Website Account")],
        [KeyboardButton("FAQ")],
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! How can I assist you today?",
        reply_markup=reply_markup,
    )


# text message handler
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
            reply_markup=markup,
        )


# inline callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "faq_calorie":
        await query.edit_message_text(
            "Your calorie goal is automatically set based on your profile!"
        )
    elif query.data == "faq_accuracy":
        await query.edit_message_text(
            "AI accuracy may vary depending on photo quality."
        )


# build application
application = (
    ApplicationBuilder()
    .token(TOKEN)
    .build()
)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
application.add_handler(CallbackQueryHandler(button_handler))

def main():
    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url=WEBHOOK_URL,
        secret_token=None,
    )


if __name__ == "__main__":
    main()
