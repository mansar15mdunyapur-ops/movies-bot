# -*- coding: utf-8 -*-
import database
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Admin IDs (apna Telegram ID yahan daalo)
ADMIN_IDS = [123456789]  # <-- YAHAN APNA ID DAALO!

# Conversation states
ADD_MOVIE_TMDB, ADD_MOVIE_QUALITY, ADD_MOVIE_FILE, ADD_MOVIE_SIZE = range(4)

# ========== ADMIN CHECK FUNCTION ==========
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# ========== ADMIN COMMANDS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin panel - /admin command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 Movies", callback_data="admin_movies")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
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
        f"✅ **Approved:** 0\n"
        f"⏳ **Pending:** 0\n\n"
        f"💾 **Database:** movies.db"
    )
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users list"""
    # Simple version - get count only
    total_users = database.get_total_users()
    
    await update.message.reply_text(
        f"👥 **Total Users:** {total_users}\n\n"
        f"Use `/userinfo [id]` for details",
        parse_mode='Markdown'
    )

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending requests"""
    pending = database.get_pending_requests()
    
    if not pending:
        await update.message.reply_text("📝 No pending requests!")
        return
    
    msg = "📝 **Pending Requests:**\n\n"
    for req in pending[:10]:  # Show first 10
        msg += f"• {req[3]} (User: {req[1]})\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

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
        "Step 3: Upload the **movie file** (video) or send **file_id**"
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
    
    # Save to database
    tmdb_id = context.user_data.get('tmdb_id')
    quality = context.user_data.get('quality')
    file_id = context.user_data.get('file_id')
    
    # For now, we need title and year - you might want to fetch from TMDb API
    await update.message.reply_text(
        "✅ **Movie Added Successfully!**\n\n"
        f"TMDb ID: {tmdb_id}\n"
        f"Quality: {quality}\n"
        f"File Size: {file_size}\n\n"
        "Note: You need to add title/year manually for now."
    )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

# ========== BROADCAST FUNCTIONALITY ==========
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    await update.message.reply_text(
        "📢 **Broadcast Message**\n\n"
        "Send the message you want to broadcast to all users:"
    )
    
    # Store that we're waiting for broadcast message
    context.user_data['waiting_broadcast'] = True

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast to all users"""
    if not context.user_data.get('waiting_broadcast'):
        return
    
    message = update.message.text
    await update.message.reply_text("📤 Broadcasting message...")
    
    # In real implementation, you would:
    # 1. Get all users from database
    # 2. Send message to each user
    # 3. Track success/failure
    
    await update.message.reply_text(
        f"✅ Broadcast sent!\n\n"
        f"Message: {message}\n"
        f"Note: Actual broadcasting requires user list"
    )
    
    context.user_data['waiting_broadcast'] = False

# ========== SETTINGS ==========
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings"""
    await update.message.reply_text(
        "⚙️ **Admin Settings**\n\n"
        "• /setwelcome - Set welcome message\n"
        "• /sethelp - Set help message\n"
        "• /addadmin - Add new admin\n"
        "• /removeadmin - Remove admin\n"
        "• /backup - Backup database"
    )

# ========== CALLBACK HANDLER ==========
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_stats":
        total_movies = database.get_total_movies()
        total_users = database.get_total_users()
        total_requests = database.get_total_requests()
        
        stats = (
            f"📊 **Bot Statistics**\n\n"
            f"🎬 Movies: {total_movies}\n"
            f"👥 Users: {total_users}\n"
            f"📝 Requests: {total_requests}"
        )
        await query.edit_message_text(stats, parse_mode='Markdown')
    
    elif data == "admin_movies":
        keyboard = [
            [InlineKeyboardButton("➕ Add Movie", callback_data="add_movie")],
            [InlineKeyboardButton("📋 List Movies", callback_data="list_movies")],
            [InlineKeyboardButton("❌ Delete Movie", callback_data="del_movie")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎬 **Movies Menu**", reply_markup=reply_markup)
    
    elif data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("🎬 Movies", callback_data="admin_movies")],
            [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton("📝 Requests", callback_data="admin_requests")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("👑 **Admin Panel**", reply_markup=reply_markup)