# -*- coding: utf-8 -*-
import database
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Admin IDs (apna Telegram ID yahan daalo)
ADMIN_IDS = [8178162794]  # <-- YAHAN APNA ID DAALO!

# Conversation states
ADD_MOVIE_TMDB, ADD_MOVIE_QUALITY, ADD_MOVIE_FILE, ADD_MOVIE_SIZE = range(4)

# ========== DATABASE FUNCTIONS FOR BAN ==========
def ban_user(user_id, admin_id, reason="No reason"):
    """Ban a user from using the bot"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return False, "User not found"
    
    # Update user status to banned
    cursor.execute('''
        UPDATE users 
        SET user_type = 'banned', 
            payment_status = 'banned',
            admin_notes = ?
        WHERE user_id = ?
    ''', (f"Banned by admin {admin_id}: {reason}", user_id))
    
    # Deactivate any active licenses
    cursor.execute('''
        UPDATE licenses 
        SET status = 'banned' 
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    return True, "User banned successfully"

def unban_user(user_id):
    """Unban a user"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Update user status
    cursor.execute('''
        UPDATE users 
        SET user_type = 'paid', 
            payment_status = 'inactive',
            admin_notes = NULL
        WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    return True, "User unbanned successfully"

def get_banned_users():
    """Get list of banned users"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, first_name, admin_notes 
        FROM users 
        WHERE user_type = 'banned' OR payment_status = 'banned'
        ORDER BY joined_date DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()
    return users

def check_if_banned(user_id):
    """Check if user is banned"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_type, payment_status 
        FROM users 
        WHERE user_id = ?
    ''', (user_id,))
    
    user = cursor.fetchone()
    conn.close()
    
    if user and (user[0] == 'banned' or user[1] == 'banned'):
        return True
    return False

# ========== ADMIN CHECK FUNCTION ==========
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# ========== BAN/UNBAN COMMANDS ==========
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user - /ban user_id reason"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Usage: /ban USER_ID [reason]\n"
            "Example: /ban 123456789 Spamming"
        )
        return
    
    target_user = int(context.args[0])
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason specified"
    
    success, message = ban_user(target_user, user_id, reason)
    
    if success:
        await update.message.reply_text(f"✅ User {target_user} banned!\nReason: {reason}")
        
        # Try to notify the banned user
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text=f"❌ You have been banned from using this bot.\nReason: {reason}\nContact admin for more information."
            )
        except:
            pass
    else:
        await update.message.reply_text(f"❌ {message}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user - /unban user_id"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /unban USER_ID")
        return
    
    target_user = int(context.args[0])
    
    success, message = unban_user(target_user)
    
    if success:
        await update.message.reply_text(f"✅ User {target_user} unbanned!")
        
        # Try to notify the unbanned user
        try:
            await context.bot.send_message(
                chat_id=target_user,
                text="✅ You have been unbanned. You can now use the bot again."
            )
        except:
            pass
    else:
        await update.message.reply_text(f"❌ {message}")

async def banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of banned users"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    banned = get_banned_users()
    
    if not banned:
        await update.message.reply_text("✅ No banned users found.")
        return
    
    msg = "🚫 <b>Banned Users:</b>\n\n"
    for user in banned[:10]:  # Show first 10
        user_id, username, first_name, reason = user
        username_display = f"@{username}" if username else "No username"
        msg += f"• <b>ID:</b> <code>{user_id}</code>\n"
        msg += f"  <b>Name:</b> {first_name} ({username_display})\n"
        msg += f"  <b>Reason:</b> {reason if reason else 'Not specified'}\n\n"
    
    if len(banned) > 10:
        msg += f"... and {len(banned) - 10} more"
    
    await update.message.reply_text(msg, parse_mode='HTML')

# ========== ADD MOVIE FUNCTIONALITY ==========
async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add movie process"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🎬 <b>Add New Movie</b>\n\n"
        "Step 1: Send me the <b>TMDb ID</b> of the movie.\n\n"
        "Example: <code>299534</code> for Avengers Endgame\n\n"
        "Or send the movie name and I'll search.",
        parse_mode='HTML'
    )
    
    return ADD_MOVIE_TMDB

async def add_movie_tmdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get TMDb ID and movie details"""
    text = update.message.text.strip()
    
    # Store in context
    context.user_data['tmdb_id'] = text
    
    await update.message.reply_text(
        f"✅ TMDb ID: {text}\n\n"
        "Step 2: Send the <b>quality</b> (1080p, 720p, etc.)",
        parse_mode='HTML'
    )
    
    return ADD_MOVIE_QUALITY

async def add_movie_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get quality"""
    quality = update.message.text.strip()
    context.user_data['quality'] = quality
    
    await update.message.reply_text(
        f"✅ Quality: {quality}\n\n"
        "Step 3: Upload the <b>movie file</b> (video)",
        parse_mode='HTML'
    )
    
    return ADD_MOVIE_FILE

async def add_movie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get file"""
    if update.message.video:
        file_id = update.message.video.file_id
        context.user_data['file_id'] = file_id
        
        await update.message.reply_text(
            "✅ File received!\n\n"
            "Step 4: Send the <b>file size</b> (e.g., 2.5 GB)",
            parse_mode='HTML'
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
        f"✅ <b>Movie Added Successfully!</b>\n\n"
        f"TMDb ID: {tmdb_id}\n"
        f"Quality: {quality}\n"
        f"File Size: {file_size}\n\n"
        "Note: You need to add title/year manually for now.",
        parse_mode='HTML'
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

# ========== ADMIN PANEL ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin panel - /admin command"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 Add Movie", callback_data="admin_addmovie")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("🚫 Banned Users", callback_data="admin_banned")],
        [InlineKeyboardButton("🔨 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 <b>Admin Panel</b>\n\n"
        "Choose an option:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    total_movies = database.get_total_movies()
    total_users = database.get_total_users()
    total_requests = database.get_total_requests()
    
    # Get banned count
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'banned' OR payment_status = 'banned'")
    banned_count = cursor.fetchone()[0]
    conn.close()
    
    stats_msg = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"🎬 <b>Movies:</b> {total_movies}\n"
        f"👥 <b>Users:</b> {total_users}\n"
        f"🚫 <b>Banned Users:</b> {banned_count}\n"
        f"📝 <b>Requests:</b> {total_requests}\n"
    )
    
    await update.message.reply_text(stats_msg, parse_mode='HTML')

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show users list"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, first_name, user_type, joined_date 
        FROM users 
        ORDER BY joined_date DESC 
        LIMIT 10
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("📭 No users found!")
        return
    
    msg = "👥 <b>Recent Users (Last 10):</b>\n\n"
    for user in users:
        user_id, username, first_name, user_type, joined = user
        username_display = f"@{username}" if username else "No username"
        status_emoji = "✅" if user_type == 'paid' else "🆓" if user_type == 'free' else "🚫"
        msg += f"{status_emoji} <b>{first_name}</b> ({username_display})\n"
        msg += f"   ID: <code>{user_id}</code> | Type: {user_type}\n"
        msg += f"   Joined: {joined[:10]}\n\n"
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending requests"""
    pending = database.get_pending_requests()
    
    if not pending:
        await update.message.reply_text("📝 No pending requests!")
        return
    
    msg = "📝 <b>Pending Requests:</b>\n\n"
    for req in pending[:10]:
        msg += f"• {req[3]} (User: {req[1]})\n"
    
    await update.message.reply_text(msg, parse_mode='HTML')

# ========== CALLBACK HANDLER ==========
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_stats":
        await admin_stats(update, context)
    
    elif data == "admin_addmovie":
        await query.message.delete()
        await add_movie_start(update, context)
    
    elif data == "admin_requests":
        await admin_requests(update, context)
    
    elif data == "admin_users":
        await admin_users(update, context)
    
    elif data == "admin_banned":
        await banned_list(update, context)
    
    elif data == "admin_ban":
        await query.edit_message_text(
            "🔨 <b>Ban User</b>\n\n"
            "Use command: <code>/ban USER_ID REASON</code>\n\n"
            "Example: <code>/ban 123456789 Spamming</code>",
            parse_mode='HTML'
        )
    
    elif data == "admin_unban":
        await query.edit_message_text(
            "✅ <b>Unban User</b>\n\n"
            "Use command: <code>/unban USER_ID</code>\n\n"
            "Example: <code>/unban 123456789</code>",
            parse_mode='HTML'
        )
