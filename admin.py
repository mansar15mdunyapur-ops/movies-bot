# -*- coding: utf-8 -*-
import database
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import logging

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_IDS = [8178162794]  # <-- APNA ID DAALO

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("💰 Payments", callback_data="admin_payments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\nChoose option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
