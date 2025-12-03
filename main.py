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

# Track user state
user_state = {}  # chat_id → string

# FAQ content
FAQ_ITEMS = {
    "faq_calorie": "🔢 *Calorie Goal*\nYour calorie goal is automatically set based on your profile details.",
    "faq_accuracy": "🤖 *AI Accuracy*\nAI accuracy depends on photo quality and ingredient clarity.",
    "faq_upload": "📸 *How to Upload Photos?*\nTap 'Upload Photo' → Send your food photo → We save it automatically.",
    "faq_report": "📊 *Weekly Reports*\nVisit the website → Profile → Weekly Reports section.",
    "faq_privacy": "🔐 *Privacy*\nAll your data is securely stored with Supabase RLS policies.",
    "faq_support": "🛟 *Support*\nNeed help? Contact support@nutritionlm.com.",
}

FAQ_TITLES = {
    "faq_calorie": "Set Calorie Goal",
    "faq_accuracy": "AI Analysis Accuracy",
    "faq_upload": "How to Upload Photos?",
    "faq_report": "View Weekly Reports",
    "faq_privacy": "Privacy Information",
    "faq_support": "Contact Support",
}

SEARCH_BUTTON_KEY = "faq_search"


# --------------------------
# START COMMAND
# --------------------------
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


# --------------------------
# OTP INPUT HANDLER
# --------------------------
def handle_otp(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    otp_input = update.message.text.strip()

    if not otp_input.isdigit() or len(otp_input) != 6:
        update.message.reply_text("❌ Invalid OTP. Please enter a 6-digit number.")
        return

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

    supabase.from_("users").update({
        "telegram_verified": True,
        "telegram_chat_id": chat_id,
        "telegram_otp": None
    }).eq("id", user["id"]).execute()

    update.message.reply_text("✅ Your NutritionLM account is now linked!")
    user_state[chat_id] = None


# --------------------------
# PHOTO UPLOAD HANDLER
# --------------------------
def photo_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    if user_state.get(chat_id) != "upload_photo_waiting":
        update.message.reply_text("❗ Please tap 'Upload Photo' from the menu first.")
        return

    user_state[chat_id] = None

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


# --------------------------
# BUILD FAQ MENU UI
# --------------------------
def build_faq_menu():
    faq_buttons = []
    row = []

    # Search button at top
    row.append(InlineKeyboardButton("🔍 Search FAQ", callback_data=SEARCH_BUTTON_KEY))

    for key, title in FAQ_TITLES.items():
        if len(row) == 2:
            faq_buttons.append(row)
            row = []

        row.append(InlineKeyboardButton(title, callback_data=key))

    if row:
        faq_buttons.append(row)

    return InlineKeyboardMarkup(faq_buttons)


# --------------------------
# TEXT MESSAGE HANDLER
# --------------------------
def message_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    # FAQ SEARCH MODE
    if user_state.get(chat_id) == "faq_search_mode":
        keyword = text.lower()
        matches = []

        for key, content in FAQ_ITEMS.items():
            if keyword in content.lower() or keyword in FAQ_TITLES[key].lower():
                matches.append(key)

        if not matches:
            update.message.reply_text("❌ No matching FAQ found. Try another keyword.")
            return

        buttons = [[InlineKeyboardButton(FAQ_TITLES[k], callback_data=k)] for k in matches]
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="faq_back")])

        update.message.reply_text(
            "🔍 *Search Results:*",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        user_state[chat_id] = None
        return

    # OTP MODE
    if user_state.get(chat_id) == "waiting_for_otp":
        handle_otp(update, context)
        return

    # Connect Website Account
    if text == "Connect Website Account":
        update.message.reply_text("🔗 Please send your 6-digit OTP from the website.")
        user_state[chat_id] = "waiting_for_otp"
        return

    # Upload Photo
    if text == "Upload Photo":
        update.message.reply_text(
            "📸 Please send me the photo you want to upload!\n\n"
            "Reminder: All photos uploaded will be automatically logged into your food diary."
        )
        user_state[chat_id] = "upload_photo_waiting"
        return

    # FAQ MENU
    if text == "FAQ":
        markup = build_faq_menu()
        update.message.reply_text(
            "📚 *FAQ Menu*\nChoose a topic:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        user_state[chat_id] = "faq_menu"
        return


# --------------------------
# BUTTON HANDLER (FAQ / SEARCH)
# --------------------------
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    key = query.data
    chat_id = query.message.chat_id

    # Search FAQ button
    if key == SEARCH_BUTTON_KEY:
        query.edit_message_text(
            "🔍 *Enter a keyword to search FAQ:*",
            parse_mode="Markdown"
        )
        user_state[chat_id] = "faq_search_mode"
        return

    # BACK BUTTON
    if key == "faq_back":
        query.edit_message_text(
            "📚 *FAQ Menu*\nChoose a topic:",
            reply_markup=build_faq_menu(),
            parse_mode="Markdown"
        )
        return

    # FAQ detail page
    if key in FAQ_ITEMS:
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="faq_back")]
        ])

        query.edit_message_text(
            FAQ_ITEMS[key],
            reply_markup=back_button,
            parse_mode="Markdown"
        )
        return

    query.edit_message_text("❓ Unknown FAQ option.")


# --------------------------
# RUN WEBHOOK
# --------------------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.photo, photo_handler))

    updater.start_webhook(
        listen="0.0.0.0",
        port=10000,
        url_path="/",
        webhook_url=WEBHOOK_URL,
    )

    updater.idle()


if __name__ == "__main__":
    main()
