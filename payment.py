# -*- coding: utf-8 -*-
import sqlite3
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

# Admin IDs (apna ID yahan daalo)
ADMIN_ID = 8178162794  # <-- APNA ID YAHAN DAALO!
FREE_USER_ID = ADMIN_ID  # Admin free hai

# Payment methods
PAYMENT_METHODS = {
    'jazzcash': '03017178242',  # Apna JazzCash number
    'easypaisa': '03424546056',  # Apna EasyPaisa number
    'bank': 'Bank Account Details'
}

# Prices
PRICES = {
    '1day': 0,        # 1 day free trial
    'weekly': 100,    # 100 Rs per week
    'monthly': 300,   # 300 Rs per month
    'yearly': 2000    # 2000 Rs per year
}

# ========== LICENSE FUNCTIONS ==========
def generate_license_key():
    """Generate unique license key"""
    letters = string.ascii_uppercase + string.digits
    return 'MOV-' + ''.join(random.choice(letters) for _ in range(8))

def save_license(license_key, user_id, expiry_days):
    """Save license to database"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    expiry_date = datetime.now() + timedelta(days=expiry_days)
    
    cursor.execute('''
        INSERT INTO licenses (license_key, user_id, expiry_date, status)
        VALUES (?, ?, ?, 'active')
    ''', (license_key, user_id, expiry_date))
    
    # Update user
    cursor.execute('''
        UPDATE users 
        SET user_type = 'paid', 
            payment_status = 'active',
            expiry_date = ?,
            license_key = ?
        WHERE user_id = ?
    ''', (expiry_date, license_key, user_id))
    
    conn.commit()
    conn.close()
    return license_key

def check_user_access(user_id):
    """Check if user can use bot"""
    # Admin/free user ko hamesha access
    if user_id == FREE_USER_ID:
        return True, "free"
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_type, payment_status, expiry_date 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False, "new"
    
    user_type, payment_status, expiry_date = user
    
    if user_type == 'free':
        return True, "free"
    
    if payment_status == 'active' and expiry_date:
        if datetime.now() < datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S.%f'):
            return True, "paid"
        else:
            # Expired
            conn = sqlite3.connect('movies.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET payment_status = 'expired' WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            conn.close()
            return False, "expired"
    
    return False, "inactive"

# ========== PAYMENT HANDLERS ==========
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command"""
    user_id = update.effective_user.id
    
    # Check access
    has_access, status = check_user_access(user_id)
    
    if has_access:
        await update.message.reply_text(
            "✅ **Aap already active user hain!**\n\n"
            "Aap bot use kar sakte hain.",
            parse_mode='Markdown'
        )
        return
    
    # Show pricing with 1 day free trial
    keyboard = [
        [InlineKeyboardButton("🎁 1 Day Free Trial", callback_data="buy_1day")],
        [InlineKeyboardButton("📅 Weekly - 100 Rs", callback_data="buy_weekly")],
        [InlineKeyboardButton("📆 Monthly - 300 Rs", callback_data="buy_monthly")],
        [InlineKeyboardButton("🎫 Yearly - 2000 Rs", callback_data="buy_yearly")],
        [InlineKeyboardButton("❓ Help", callback_data="buy_help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💳 **Movie Bot Subscription**\n\n"
        "Bot use karne ke liye subscription leni hogi.\n\n"
        "**Prices:**\n"
        "• 1 Day Free Trial\n"
        "• Weekly: 100 Rs\n"
        "• Monthly: 300 Rs\n"
        "• Yearly: 2000 Rs\n\n"
        "Choose plan:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "buy_help":
        await query.edit_message_text(
            "❓ **Payment Help**\n\n"
            "1. Choose a plan\n"
            "2. Send payment to given number\n"
            "3. Send screenshot with transaction ID\n"
            "4. Admin will activate your license\n\n"
            "**Contact:** @admin_username",
            parse_mode='Markdown'
        )
        return
    
    # Plan selected
    plan = data.replace('buy_', '')
    
    if plan == '1day':
        days = 1
        amount = 0
    elif plan == 'weekly':
        days = 7
        amount = PRICES['weekly']
    elif plan == 'monthly':
        days = 30
        amount = PRICES['monthly']
    elif plan == 'yearly':
        days = 365
        amount = PRICES['yearly']
    else:
        days = 0
        amount = 0
    
    # Store in context
    context.user_data['payment_plan'] = plan
    context.user_data['payment_days'] = days
    context.user_data['payment_amount'] = amount
    
    # Show payment details
    keyboard = [
        [InlineKeyboardButton("✅ I have paid", callback_data="paid_confirmation")],
        [InlineKeyboardButton("🔙 Back", callback_data="buy_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💳 **Payment Instructions**\n\n"
        f"Plan: {plan.upper()}\n"
        f"Amount: {amount} Rs\n\n"
        f"**Send payment to:**\n"
        f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
        f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
        f"**After payment:**\n"
        f"1. Take screenshot\n"
        f"2. Click 'I have paid'\n"
        f"3. Send transaction ID\n\n"
        f"Admin will activate within 24 hours.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment confirmation"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📤 **Send Transaction Details**\n\n"
        "Please send:\n"
        "1. Transaction ID\n"
        "2. Payment method (JazzCash/EasyPaisa)\n"
        "3. Screenshot (optional)\n\n"
        "Example:\n"
        "`TXN123456789`\n"
        "JazzCash"
    )
    
    # Set state to wait for transaction
    context.user_data['waiting_transaction'] = True
    return

async def handle_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle transaction message"""
    if not context.user_data.get('waiting_transaction'):
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    # Generate license key
    license_key = generate_license_key()
    days = context.user_data.get('payment_days', 30)
    
    # Save to database
    save_license(license_key, user_id, days)
    
    # Clear waiting state
    context.user_data['waiting_transaction'] = False
    
    await update.message.reply_text(
        f"✅ **Payment Received!**\n\n"
        f"Your license key: `{license_key}`\n"
        f"Valid for: {days} days\n\n"
        f"Admin will verify and activate soon.\n"
        f"Or use `/activate {license_key}` to activate now.",
        parse_mode='Markdown'
    )
    
    # Notify admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 New payment!\nUser: {user_id}\nPlan: {context.user_data.get('payment_plan')}\nLicense: {license_key}"
    )

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually activate license"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("Usage: `/activate LICENSE_KEY`", parse_mode='Markdown')
        return
    
    license_key = context.args[0]
    
    # Check license in database
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM licenses WHERE license_key = ? AND status = "active"', (license_key,))
    license = cursor.fetchone()
    
    if license:
        # Activate user
        cursor.execute('''
            UPDATE users 
            SET user_type = 'paid', 
                payment_status = 'active',
                license_key = ?
            WHERE user_id = ?
        ''', (license_key, user_id))
        
        conn.commit()
        await update.message.reply_text("✅ License activated! Enjoy the bot!")
    else:
        await update.message.reply_text("❌ Invalid or used license key!")
    
    conn.close()

# ========== ADMIN FUNCTIONS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel command"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("💰 Payments", callback_data="admin_payments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\nChoose option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all users"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, first_name, user_type, payment_status, expiry_date 
        FROM users ORDER BY joined_date DESC LIMIT 10
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("📭 No users found!")
        return
    
    msg = "👥 **Recent Users:**\n\n"
    for user in users:
        expiry = user[5] if user[5] else "No expiry"
        msg += f"• {user[2]} (@{user[1]}) - {user[3]}/{user[4]}\n   Expiry: {expiry}\n\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending requests"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM requests WHERE status = 'pending' 
        ORDER BY request_date DESC LIMIT 10
    ''')
    
    requests = cursor.fetchall()
    conn.close()
    
    if not requests:
        await update.message.reply_text("📭 No pending requests!")
        return
    
    msg = "📝 **Pending Requests:**\n\n"
    for req in requests:
        msg += f"• {req[3]} (User: {req[1]}) - {req[4]}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_stats":
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
        active_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM payments')
        total_payments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM movies')
        total_movies = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM requests WHERE status = "pending"')
        pending_requests = cursor.fetchone()[0]
        
        conn.close()
        
        stats = (
            f"📊 **Bot Statistics**\n\n"
            f"🎬 Total Movies: {total_movies}\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Active Users: {active_users}\n"
            f"💰 Total Payments: {total_payments}\n"
            f"📝 Pending Requests: {pending_requests}\n"
        )
        await query.edit_message_text(stats, parse_mode='Markdown')
    
    elif data == "admin_requests":
        await admin_requests(update, context)
    
    elif data == "admin_users":
        await admin_users(update, context)