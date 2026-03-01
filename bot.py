# -*- coding: utf-8 -*-
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import database
import payment

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

# Initialize database
database.init_database()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== BOT COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    database.add_user(user.id, user.username, user.first_name)
    
    welcome_msg = (
        f"🎬 **Namaste {user.first_name}!** 🎬\n\n"
        "Main aapka **Movie Bot** hoon!\n\n"
        "/movies - Collection dekhein\n"
        "/buy - Subscription plans\n"
        "/help - Madad"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

# ========== MAIN FUNCTION ==========
def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN nahi mila!")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))  # Temporary
    
    print("🎬 Movie Bot starting...")
    print("✅ Database connected!")
    print("🚀 Bot is running!")
    
    # Start polling (blocking call)
    app.run_polling()

if __name__ == '__main__':
    main()
