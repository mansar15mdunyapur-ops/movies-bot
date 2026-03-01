# -*- coding: utf-8 -*-
import sqlite3
import random
import string
import time
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging
import database

logger = logging.getLogger(__name__)

# Admin IDs
ADMIN_ID = 8178162794  # <-- APNA ID DAALO
ADMIN_IDS = [ADMIN_ID]
FREE_USER_ID = ADMIN_ID

# Payment methods
PAYMENT_METHODS = {
    'jazzcash': '03017178242',  # Apna JazzCash number
    'easypaisa': '03424546056',  # Apna EasyPaisa number
}

# Payment channel/group for admin notifications
PAYMENT_CHANNEL_ID = -100123456789  # <-- Apna private channel ID daalo (optional)

# Prices
PRICES = {
    '1day': 0,
    'weekly': 100,
    'monthly': 300,
    'yearly': 2000
}

# Conversation states
WAITING_SCREENSHOT, WAITING_TRANSACTION_ID = range(2)

# ========== LICENSE FUNCTIONS ==========
def generate_license_key():
    letters = string.ascii_uppercase + string.digits
    return 'MOV-' + ''.join(random.choice(letters) for _ in range(8))

def generate_payment_id():
    timestamp = int(time.time())
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PAY-{timestamp}-{random_str}"

def check_user_access(user_id):
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
        help_text = (
            "❓ **Payment Help**\n\n"
            "**Secure Payment System:**\n\n"
            "1. Choose a plan\n"
            "2. Send payment to given JazzCash/EasyPaisa number\n"
            "3. Take screenshot of payment\n"
            "4. Upload screenshot here\n"
            "5. Add transaction ID in caption\n"
            "6. Admin will verify within 1-2 hours\n\n"
            "**Payment Methods:**\n"
            f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
            f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
            "**⚠️ Important:**\n"
            "• Keep screenshot as proof\n"
            "• Fake transactions will be blocked\n"
            "• Admin verification is mandatory"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="buy_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        return
    
    if data == "buy_back":
        keyboard = [
            [InlineKeyboardButton("🎁 1 Day Free Trial", callback_data="buy_1day")],
            [InlineKeyboardButton("📅 Weekly - 100 Rs", callback_data="buy_weekly")],
            [InlineKeyboardButton("📆 Monthly - 300 Rs", callback_data="buy_monthly")],
            [InlineKeyboardButton("🎫 Yearly - 2000 Rs", callback_data="buy_yearly")],
            [InlineKeyboardButton("❓ Help", callback_data="buy_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💳 **Movie Bot Subscription**\n\nChoose a plan:",
            reply_markup=reply_markup
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
        return
    
    # Store in context
    context.user_data['payment_plan'] = plan
    context.user_data['payment_days'] = days
    context.user_data['payment_amount'] = amount
    
    # Generate payment ID
    payment_id = generate_payment_id()
    context.user_data['payment_id'] = payment_id
    
    # Save to database
    database.save_pending_payment(payment_id, query.from_user.id, amount, plan)
    
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_data = f"MOVIEBOT|{payment_id}|{amount}|PKR|{PAYMENT_METHODS['jazzcash']}"
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    instructions = (
        f"🛍️ **Payment Details**\n\n"
        f"**Plan:** {plan}\n"
        f"**Amount:** {amount} Rs\n"
        f"**Payment ID:** `{payment_id}`\n\n"
        f"**Send payment to:**\n"
        f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
        f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
        f"**📸 Steps:**\n"
        f"1. Send payment to above number\n"
        f"2. Take screenshot\n"
        f"3. Click 'I have paid' button\n"
        f"4. Upload screenshot with transaction ID\n\n"
        f"✅ Admin will verify within 1-2 hours"
    )
    
    await query.message.delete()
    await query.message.reply_photo(
        photo=bio,
        caption=instructions,
        parse_mode='Markdown'
    )
    
    keyboard = [[InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{payment_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "Click after payment:",
        reply_markup=reply_markup
    )

async def paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'I have paid' button"""
    query = update.callback_query
    await query.answer()
    
    payment_id = query.data.replace('paid_', '')
    context.user_data['current_payment_id'] = payment_id
    
    await query.edit_message_text(
        f"📸 **Upload Payment Proof**\n\n"
        f"Payment ID: `{payment_id}`\n\n"
        f"Please send:\n"
        f"1️⃣ **Screenshot** of payment\n"
        f"2️⃣ **Transaction ID** in caption\n\n"
        f"Example caption: `TXN123456789`"
    )
    
    return WAITING_SCREENSHOT

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment screenshot"""
    payment_id = context.user_data.get('current_payment_id')
    
    if not payment_id:
        return
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a screenshot photo!")
        return WAITING_SCREENSHOT
    
    # Get photo
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or "No transaction ID"
    
    # Get pending payment
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, amount, plan FROM pending_payments WHERE payment_id = ?', (payment_id,))
    payment = cursor.fetchone()
    conn.close()
    
    if not payment:
        await update.message.reply_text("❌ Invalid payment ID!")
        context.user_data['current_payment_id'] = None
        return ConversationHandler.END
    
    user_id, amount, plan = payment
    
    # Save screenshot info
    database.update_payment_with_screenshot(payment_id, photo, caption)
    
    # Forward to admin
    admin_msg = (
        f"💰 **New Payment Request**\n\n"
        f"**Payment ID:** `{payment_id}`\n"
        f"**User:** {update.effective_user.first_name}\n"
        f"**User ID:** `{user_id}`\n"
        f"**Username:** @{update.effective_user.username}\n"
        f"**Amount:** {amount} Rs\n"
        f"**Plan:** {plan}\n"
        f"**Transaction ID:** {caption}\n\n"
        f"**Admin Commands:**\n"
        f"/approve {payment_id} - ✅ Activate user\n"
        f"/reject {payment_id} [reason] - ❌ Reject"
    )
    
    # Send to all admins
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo,
                caption=admin_msg,
                parse_mode='Markdown'
            )
        except:
            pass
    
    await update.message.reply_text(
        f"✅ **Payment proof received!**\n\n"
        f"Payment ID: `{payment_id}`\n"
        f"Admin will verify within 1-2 hours.\n"
        f"You'll receive license key after approval."
    )
    
    context.user_data['current_payment_id'] = None
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

# ========== ADMIN APPROVAL COMMANDS ==========
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approve payment"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /approve PAYMENT_ID")
        return
    
    payment_id = context.args[0]
    
    # Get payment details
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, plan FROM pending_payments WHERE payment_id = ? AND status = "pending"', (payment_id,))
    payment = cursor.fetchone()
    
    if not payment:
        await update.message.reply_text("❌ No pending payment found!")
        conn.close()
        return
    
    user_id, plan = payment
    
    # Generate license
    license_key = generate_license_key()
    days = 7 if plan == 'weekly' else 30 if plan == 'monthly' else 365
    
    # Save license
    database.save_license(license_key, user_id, days)
    
    # Update payment status
    cursor.execute('UPDATE pending_payments SET status = "approved" WHERE payment_id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User {user_id} activated with license: {license_key}")
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ **Payment Approved!**\n\n"
                 f"Assalamualaikum! 👋\n"
                 f"Your payment has been verified.\n\n"
                 f"**License Key:** `{license_key}`\n"
                 f"**Plan:** {plan}\n"
                 f"**Valid for:** {days} days\n\n"
                 f"Use /activate {license_key} to start using the bot!\n\n"
                 f"Shukriya! 🙏"
        )
    except:
        pass

async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin reject payment"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /reject PAYMENT_ID [reason]")
        return
    
    payment_id = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason specified"
    
    # Get user_id
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM pending_payments WHERE payment_id = ? AND status = "pending"', (payment_id,))
    payment = cursor.fetchone()
    
    if not payment:
        await update.message.reply_text("❌ No pending payment found!")
        conn.close()
        return
    
    user_id = payment[0]
    
    # Update payment status
    cursor.execute('UPDATE pending_payments SET status = "rejected" WHERE payment_id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"❌ Payment {payment_id} rejected")
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ **Payment Rejected**\n\n"
                 f"Payment ID: `{payment_id}`\n"
                 f"Reason: {reason}\n\n"
                 f"Please contact admin for more information."
        )
    except:
        pass

# ========== ADMIN PANEL FUNCTIONS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel command"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📝 Pending Payments", callback_data="admin_pending")],
        [InlineKeyboardButton("📋 Pending Requests", callback_data="admin_requests")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **Admin Panel**\n\nChoose option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "admin_stats":
        total_users = database.get_total_users()
        total_movies = database.get_total_movies()
        total_requests = database.get_total_requests()
        
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pending_payments WHERE status = "pending"')
        pending_payments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
        active_users = cursor.fetchone()[0]
        conn.close()
        
        stats = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Active Users: {active_users}\n"
            f"🎬 Total Movies: {total_movies}\n"
            f"📝 Pending Requests: {total_requests}\n"
            f"💰 Pending Payments: {pending_payments}"
        )
        await query.edit_message_text(stats, parse_mode='Markdown')
    
    elif query.data == "admin_pending":
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT payment_id, user_id, amount, plan, created_at 
            FROM pending_payments WHERE status = "pending" 
            ORDER BY created_at DESC LIMIT 10
        ''')
        payments = cursor.fetchall()
        conn.close()
        
        if not payments:
            await query.edit_message_text("📭 No pending payments!")
            return
        
        msg = "💰 **Pending Payments:**\n\n"
        for p in payments:
            msg += f"• `{p[0]}` - User: {p[1]} - {p[3]} - {p[2]} Rs\n"
        
        await query.edit_message_text(msg, parse_mode='Markdown')

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate license"""
    if not context.args:
        await update.message.reply_text("Usage: /activate LICENSE_KEY")
        return
    
    license_key = context.args[0]
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM licenses WHERE license_key = ? AND status = "active"', (license_key,))
    license = cursor.fetchone()
    
    if license:
        cursor.execute('''
            UPDATE users 
            SET user_type = 'paid', payment_status = 'active', license_key = ?
            WHERE user_id = ?
        ''', (license_key, user_id))
        
        conn.commit()
        await update.message.reply_text("✅ License activated! Enjoy the bot!")
    else:
        await update.message.reply_text("❌ Invalid or used license key!")
    
    conn.close()
