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
from supabase import create_client

# Supabase connection
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram bot configuration
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Track user state (for OTP input mode)
user_state = {}  # chat_id → "waiting_for_otp"


# /start command handler
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

    user_state[update.message.chat_id] = None


# Handle OTP input
async def handle_otp(update: Update, context):
    chat_id = update.message.chat_id
    otp_input = update.message.text.strip()

    # Validate OTP format
    if not otp_input.isdigit() or len(otp_input) != 6:
        await update.message.reply_text("❌ Invalid OTP. Please enter a 6-digit number.")
        return

    # Check OTP in Supabase
    result = (
        supabase
        .from_("users")
        .select("*")
        .eq("telegram_otp", otp_input)
        .execute()
    )


    if len(result.data) == 0:
        await update.message.reply_text("❌ OTP not found. Please try again.")
        return

    user = result.data[0]

    # Link account: verify and save chat ID
    supabase.from_("users") \
        .update({
            "telegram_verified": True,
            "telegram_chat_id": chat_id,
            "telegram_otp": None
        }) \
        .eq("id", user["id"]) \
        .execute()



    await update.message.reply_text("✅ Your NutritionLM account is now linked!")
    user_state[chat_id] = None


# Main text message handler
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text

    # If user is entering OTP
    if user_state.get(chat_id) == "waiting_for_otp":
        await handle_otp(update, context)
        return

    # If user selects "Connect Website Account"
    if text == "Connect Website Account":
        await update.message.reply_text(
            "🔗 Please send your 6-digit OTP from the website."
        )
        user_state[chat_id] = "waiting_for_otp"
        return

    # FAQ menu
    if text == "FAQ":
        faq_buttons = [
            [InlineKeyboardButton("Set Calorie Goal", callback_data="faq_calorie")],
            [InlineKeyboardButton("AI Analysis Accuracy", callback_data="faq_accuracy")],
        ]
        markup = InlineKeyboardMarkup(faq_buttons)

        await update.message.reply_text(
            "Please choose a question:",
            reply_markup=markup,
        )


# Callback button handler (FAQ)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "faq_calorie":
        await query.edit_message_text("Your calorie goal is automatically set based on your profile!")
    elif query.data == "faq_accuracy":
        await query.edit_message_text("AI accuracy may vary depending on photo quality.")


# Telegram bot initialization
application = (
    ApplicationBuilder()
    .token(TOKEN)
    .build()
)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
application.add_handler(CallbackQueryHandler(button_handler))


# Run webhook
def main():
    application.run_webhook(
        listen="0.0.0.0",
        port=10000,
        webhook_url=WEBHOOK_URL,
        secret_token=None,
    )


if __name__ == "__main__":
    main()
