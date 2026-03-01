# -*- coding: utf-8 -*-
import database
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Admin IDs (apna Telegram ID yahan daalo)
ADMIN_IDS = [8178162794]  # <-- YAHAN APNA ID DAALO!

# Conversation states
ADD_MOVIE_TMDB, ADD_MOVIE_QUALITY, ADD_MOVIE_FILE, ADD_MOVIE_SIZE = range(4)

# ========== ADMIN CHECK FUNCTION ==========
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# ========== ADD MOVIE FUNCTIONALITY ==========
async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add movie process"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🎬 **Add New Movie**\n\n"
        "Step 1: Send me the **TMDb ID** of the movie.\n\n"
        "Example: `299534` for Avengers Endgame\n\n"
        "Or send the movie name and I'll search."
    )
    
    return ADD_MOVIE_TMDB

async def add_movie_tmdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get TMDb ID and movie details"""
    text = update.message.text.strip()
    
    # Store in context
    context.user_data['tmdb_id'] = text
    
    await update.message.reply_text(
        f"✅ TMDb ID: {text}\n\n"
        "Step 2: Send the **quality** (1080p, 720p, etc.)"
    )
    
    return ADD_MOVIE_QUALITY

async def add_movie_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get quality"""
    quality = update.message.text.strip()
    context.user_data['quality'] = quality
    
    await update.message.reply_text(
        f"✅ Quality: {quality}\n\n"
        "Step 3: Upload the **movie file** (video)"
    )
    
    return ADD_MOVIE_FILE

async def add_movie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get file"""
    if update.message.video:
        file_id = update.message.video.file_id
        context.user_data['file_id'] = file_id
        
        await update.message.reply_text(
            "✅ File received!\n\n"
            "Step 4: Send the **file size** (e.g., 2.5 GB)"
        )
        return ADD_MOVIE_SIZE
    else:
        await update.message.reply_text("❌ Please upload a video file!")
        return ADD_MOVIE_FILE

async def add_movie_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get size and save to database"""
    file_size = update.message.text.strip()
    
    # Get data from context
    tmdb_id = context.user_data.get('tmdb_id')
    quality = context.user_data.get('quality')
    file_id = context.user_data.get('file_id')
    user_id = update.effective_user.id
    
    # For now, we need title and year - you might want to fetch from TMDb API
    await update.message.reply_text(
        f"✅ **Movie Added Successfully!**\n\n"
        f"TMDb ID: {tmdb_id}\n"
        f"Quality: {quality}\n"
        f"File Size: {file_size}\n\n"
        "Note: You need to add title/year manually for now."
    )
    
    # Here you would actually save to database
    # database.add_movie(tmdb_id, title, year, quality, file_id, file_size, user_id)
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

# ========== ADMIN COMMANDS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin panel - /admin command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 Add Movie", callback_data="add_movie")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\n"
        "Choose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    total_movies = database.get_total_movies()
    total_users = database.get_total_users()
    total_requests = database.get_total_requests()
    
    stats_msg = (
        f"📊 **Bot Statistics**\n\n"
        f"🎬 **Movies:** {total_movies}\n"
        f"👥 **Users:** {total_users}\n"
        f"📝 **Requests:** {total_requests}\n"
    )
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users list"""
    total_users = database.get_total_users()
    
    await update.message.reply_text(
        f"👥 **Total Users:** {total_users}",
        parse_mode='Markdown'
    )

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending requests"""
    pending = database.get_pending_requests()
    
    if not pending:
        await update.message.reply_text("📝 No pending requests!")
        return
    
    msg = "📝 **Pending Requests:**\n\n"
    for req in pending[:10]:
        msg += f"• {req[3]} (User: {req[1]})\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# ========== CALLBACK HANDLER ==========
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_stats":
        await admin_stats(update, context)
    
    elif data == "add_movie":
        # Start add movie process
        await query.message.delete()
        await add_movie_start(update, context)
    
    elif data == "admin_requests":
        await admin_requests(update, context)
    
    elif data == "admin_users":
        await admin_users(update, context)
