from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    CallbackContext,
)
import os
from supabase import create_client
from mimetypes import guess_type

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
def start(update: Update, context: CallbackContext):

    main_menu = [
        [KeyboardButton("Today's Nutrition Report")],
        [KeyboardButton("Connect Website Account")],
        [KeyboardButton("Upload Photo")],
        [KeyboardButton("FAQ")],
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)

    update.message.reply_text(
        "Welcome! How can I assist you today?",
        reply_markup=reply_markup,
    )

    user_state[update.message.chat_id] = None


# Handle OTP input
def handle_otp(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    otp_input = update.message.text.strip()

    # Validate OTP format
    if not otp_input.isdigit() or len(otp_input) != 6:
        update.message.reply_text("❌ Invalid OTP. Please enter a 6-digit number.")
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
        update.message.reply_text("❌ OTP not found. Please try again.")
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

    update.message.reply_text("✅ Your NutritionLM account is now linked!")
    user_state[chat_id] = None


# photo upload handler
def photo_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    # User must explicitly choose Upload Photo before sending
    if user_state.get(chat_id) != "upload_photo_waiting":
        update.message.reply_text("❗ Please tap 'Upload Photo' from the menu first.")
        return

    # Reset state after receiving photo
    user_state[chat_id] = None

    # Check verification
    user_query = (
        supabase
        .from_("users")
        .select("*")
        .eq("telegram_chat_id", chat_id)
        .execute()
    )

    if len(user_query.data) == 0 or not user_query.data[0]["telegram_verified"]:
        update.message.reply_text("❌ Please connect your website account first.")
        return

    user = user_query.data[0]

    # Use largest file version
    file_id = update.message.photo[-1].file_id
    file = context.bot.get_file(file_id)
    photo_bytes = file.download_as_bytearray()

    file_path = f"{chat_id}/{file_id}.jpg"

    mime_type, _ = guess_type(file_path)

    supabase.storage.from_("telegram_photos").upload(
        file_path,
        file=bytes(photo_bytes),
        file_options={"content-type": mime_type or "image/jpeg"}
    )

    supabase.from_("telegram_photos").insert({
        "user_id": user["id"],
        "file_path": file_path
    }).execute()

    update.message.reply_text("📸 Photo successfully uploaded to your NutritionLM library!")



# Main text message handler
def message_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text

    # If user is entering OTP
    if user_state.get(chat_id) == "waiting_for_otp":
        handle_otp(update, context)
        return

    # If user selects "Connect Website Account"
    if text == "Connect Website Account":
        update.message.reply_text(
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

        update.message.reply_text(
            "Please choose a question:",
            reply_markup=markup,
        )
    elif text == "Upload Photo":
        update.message.reply_text("📸 Please send me the photo you want to upload!")
        user_state[chat_id] = "upload_photo_waiting"
        return

# Callback button handler (FAQ)
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if data == "faq_calorie":
        query.edit_message_text("Your calorie goal is automatically set based on your profile!")
    elif data == "faq_accuracy":
        query.edit_message_text("AI accuracy may vary depending on photo quality!")


# Run webhook (Render)
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.photo, photo_handler))

    # Start webhook
    updater.start_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="/",
        webhook_url=WEBHOOK_URL,
    )

    updater.idle()


if __name__ == "__main__":
    main()
