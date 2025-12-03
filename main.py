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
import requests

# Supabase connection
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram bot configuration
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

user_state = {}

FAQ_ITEMS = {
    "faq_calorie": "🔢 *Calorie Goal*\nYour calorie goal is automatically set based on your profile details.",
    "faq_accuracy": "🤖 *AI Accuracy*\nAI accuracy depends on photo quality and ingredient clarity.",
    
    # UPDATED FAQ ANSWER
    "faq_upload": (
        "📸 *How to Upload Photos?*\n"
        "You don't need to tap anything.\n\n"
        "➡️ Simply send a photo from your gallery while in the main menu.\n"
        "➡️ All photos you send will automatically be saved to your NutritionLM Food Log.\n"
        "➡️ If you try to upload the same photo again, we will detect it and warn you.\n"
    ),

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
WEBAPP_URL = "https://nutrition-lm.vercel.app"

def start_main_menu(update: Update, context: CallbackContext):

    main_menu = [
        [KeyboardButton("Today's Nutrition Report")],
        [KeyboardButton("Connect Website Account")],
        [KeyboardButton("FAQ")],
    ]

    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)

    update.message.reply_text(
        "↩️ *You are now back at the main menu!*\n"
        "Simply upload a photo anytime to save it.\n\n",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    user_state[update.message.chat_id] = None


def start(update: Update, context: CallbackContext):

    main_menu = [
        [KeyboardButton("Today's Nutrition Report")],
        [KeyboardButton("Connect Website Account")],
        [KeyboardButton("FAQ")],
    ]

    reply_markup = ReplyKeyboardMarkup(main_menu, resize_keyboard=True)

    update.message.reply_text(
        "Welcome! How can I assist you today?\n\n📸 You may upload photos anytime.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    user_state[update.message.chat_id] = None


def handle_otp(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    otp_input = update.message.text.strip()

    if not otp_input.isdigit() or len(otp_input) != 6:
        update.message.reply_text("❌ Invalid OTP. Please enter a 6-digit number.")
        return

    result = (
        supabase.from_("users")
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

    update.message.reply_text(
        "✅ Your NutritionLM account is now linked! Please refresh the website!",
        parse_mode="Markdown"
    )

    user_state[chat_id] = None


def photo_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id

    # Fetch user
    user_query = (
        supabase.from_("users")
        .select("*")
        .eq("telegram_chat_id", chat_id)
        .execute()
    )

    # User not linked yet
    if len(user_query.data) == 0 or not user_query.data[0]["telegram_verified"]:
        update.message.reply_text("❌ Please connect your website account first.")
        return

    user = user_query.data[0]

    # Extract image file
    file_id = update.message.photo[-1].file_id
    file = context.bot.get_file(file_id)
    photo_bytes = file.download_as_bytearray()

    file_path = f"{chat_id}/{file_id}.jpg"
    mime_type, _ = guess_type(file_path)

    # Duplicate check
    duplicate_check = (
        supabase.from_("telegram_photos")
        .select("*")
        .eq("file_path", file_path)
        .execute()
    )

    if len(duplicate_check.data) > 0:
        update.message.reply_text(
            "⚠️ This photo is already saved in your library.\n"
            "Returning to main menu...",
            parse_mode="Markdown"
        )
        start_main_menu(update, context)
        return

    # Upload to Supabase storage
    supabase.storage.from_("telegram_photos").upload(
        file_path,
        file=bytes(photo_bytes),
        file_options={"content-type": mime_type or "image/jpeg"}
    )

    # Insert into DB
    supabase.from_("telegram_photos").insert({
        "user_id": user["id"],
        "file_path": file_path
    }).execute()

    update.message.reply_text(
        "📸 Photo successfully uploaded to your NutritionLM library!",
        parse_mode="Markdown"
    )

    # ---- Call ingredients API ----
    api_ingredients_url = f"{WEBAPP_URL}/api/ingredients"
    files = {"image": bytes(photo_bytes)}

    ingredients_res = requests.post(api_ingredients_url, files=files).json()

    food_name = ingredients_res.get("food_name", "Unknown Food")
    ingredients = ingredients_res.get("ingredients", [])
    food_type = ingredients_res.get("food_type")  


    # ---- Call nutrition API ----
    api_nutrition_url = f"{WEBAPP_URL}/api/nutritionist"
    nutrition_res = requests.post(api_nutrition_url, json={
        "food_name": food_name,
        "ingredients": ingredients
    }).json()

    nutrition = nutrition_res.get("nutritions", {})


    # ---- Insert into food_logs ----
    from datetime import datetime

    now = datetime.now()

    supabase.from_("food_logs").insert({
        "user_id": user["id"],
        "image_url": file_path,  
        "record_date": now.date().isoformat(),
        "record_time": now.time().strftime("%H:%M:%S"),
        "food_type": food_type,
        "ingredients": ingredients,
        "nutrition": nutrition,
        "food_name": food_name,
        "food_description": None,   
        "healthy_level": None      
    }).execute()



def build_faq_menu():
    buttons = [[InlineKeyboardButton("🔍 Search FAQ", callback_data=SEARCH_BUTTON_KEY)]]

    for key, title in FAQ_TITLES.items():
        buttons.append([InlineKeyboardButton(title, callback_data=key)])

    return InlineKeyboardMarkup(buttons)


def message_handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    # BACK COMMAND
    if text.lower() == "back":
        start_main_menu(update, context)
        return

    # FAQ SEARCH MODE
    if user_state.get(chat_id) == "faq_search_mode":
        keyword = text.lower()
        matches = [key for key in FAQ_ITEMS if keyword in FAQ_ITEMS[key].lower() or keyword in FAQ_TITLES[key].lower()]

        if not matches:
            update.message.reply_text(
                "❌ No matching FAQ found. Try again.\n\n➡️ Type *back* to return to menu.",
                parse_mode="Markdown"
            )
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
        update.message.reply_text(
            "🔗 Please send your 6-digit OTP from the website.\n\n➡️ Type *back* to return to menu.",
            parse_mode="Markdown"
        )
        user_state[chat_id] = "waiting_for_otp"
        return

    # FAQ MENU
    if text == "FAQ":
        update.message.reply_text(
            "📚 *FAQ Menu*\nChoose a topic:\n\n➡️ Type *back* to return to main menu.",
            reply_markup=build_faq_menu(),
            parse_mode="Markdown"
        )
        user_state[chat_id] = "faq_menu"
        return



def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    key = query.data
    chat_id = query.message.chat_id

    # Search FAQ mode
    if key == SEARCH_BUTTON_KEY:
        query.edit_message_text(
            "🔍 *Enter a keyword to search FAQ:*\n\n➡️ Type *back* to return.",
            parse_mode="Markdown"
        )
        user_state[chat_id] = "faq_search_mode"
        return

    # Return to FAQ menu
    if key == "faq_back":
        query.edit_message_text(
            "📚 *FAQ Menu*\nChoose a topic:\n\n➡️ Type *back* to return.",
            reply_markup=build_faq_menu(),
            parse_mode="Markdown"
        )
        return

    # FAQ detail
    if key in FAQ_ITEMS:
        query.edit_message_text(
            FAQ_ITEMS[key] + "\n\n➡️ Type *back* to return.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="faq_back")]]),
            parse_mode="Markdown"
        )
        return

    query.edit_message_text("❓ Unknown FAQ option.")



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
