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

# ========== ACTIVATE COMMAND ==========
async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate license manually"""
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Usage:</b> <code>/activate LICENSE_KEY</code>\n\n"
            "Example: <code>/activate MOV-ABC123XYZ789</code>",
            parse_mode='HTML'
        )
        return
    
    license_key = context.args[0]
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Check if license exists and is active
    cursor.execute('''
        SELECT user_id, plan, expiry_date 
        FROM licenses 
        WHERE license_key = ? AND status = 'active'
    ''', (license_key,))
    
    license = cursor.fetchone()
    
    if not license:
        await update.message.reply_text("❌ Invalid or expired license key!")
        conn.close()
        return
    
    lic_user_id, plan, expiry_date = license
    
    # Check if license is already used by someone else
    cursor.execute('SELECT license_key FROM users WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()
    
    if existing and existing[0]:
        await update.message.reply_text("❌ Aapke paas already ek active license hai!")
        conn.close()
        return
    
    # Activate user
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
    
    expiry_str = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S.%f').strftime('%d-%b-%Y')
    
    await update.message.reply_text(
        f"✅ <b>License Activated!</b>\n\n"
        f"<b>Plan:</b> {plan}\n"
        f"<b>Expiry:</b> {expiry_str}\n\n"
        f"Enjoy the bot! 🎬",
        parse_mode='HTML'
    )

# ========== PAYMENT HANDLERS ==========
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command"""
    user_id = update.effective_user.id
    
    # Check access
    has_access, status = check_user_access(user_id)
    
    if has_access:
        await update.message.reply_text(
            "✅ <b>Aap already active user hain!</b>\n\n"
            "Aap bot use kar sakte hain.\n"
            "Apna plan check karne ke liye /myplan use karein.",
            parse_mode='HTML'
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
        "💳 <b>Movie Bot Subscription</b>\n\n"
        "Bot use karne ke liye subscription leni hogi.\n\n"
        "<b>Prices:</b>\n"
        "• 1 Day Free Trial\n"
        "• Weekly: 100 Rs\n"
        "• Monthly: 300 Rs\n"
        "• Yearly: 2000 Rs\n\n"
        "Choose plan:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "buy_help":
        help_text = (
            "❓ <b>Payment Help</b>\n\n"
            "<b>Secure Payment System:</b>\n\n"
            "1. Choose a plan\n"
            "2. Send payment to given JazzCash/EasyPaisa number\n"
            "3. Take screenshot of payment\n"
            "4. Upload screenshot here\n"
            "5. Add transaction ID in caption\n"
            "6. Admin will verify within 1-2 hours\n\n"
            "<b>Payment Methods:</b>\n"
            f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
            f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
            "<b>⚠️ Important:</b>\n"
            "• Keep screenshot as proof\n"
            "• Fake transactions will be blocked\n"
            "• Admin verification is mandatory"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="buy_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='HTML')
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
            "💳 <b>Movie Bot Subscription</b>\n\nChoose a plan:",
            reply_markup=reply_markup,
            parse_mode='HTML'
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
        f"🛍️ <b>Payment Details</b>\n\n"
        f"<b>Plan:</b> {plan}\n"
        f"<b>Amount:</b> {amount} Rs\n"
        f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
        f"<b>Send payment to:</b>\n"
        f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
        f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
        f"<b>📸 Steps:</b>\n"
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
        parse_mode='HTML'
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
        f"📸 <b>Upload Payment Proof</b>\n\n"
        f"Payment ID: <code>{payment_id}</code>\n\n"
        f"Please send:\n"
        f"1️⃣ <b>Screenshot</b> of payment\n"
        f"2️⃣ <b>Transaction ID</b> in caption\n\n"
        f"Example caption: <code>TXN123456789</code>",
        parse_mode='HTML'
    )
    
    return WAITING_SCREENSHOT

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment screenshot"""
    payment_id = context.user_data.get('current_payment_id')
    
    if not payment_id:
        return ConversationHandler.END
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a screenshot photo!")
        return WAITING_SCREENSHOT
    
    # Get photo
    photo = update.message.photo[-1].file_id
    caption = update.message.caption or "No transaction ID"
    
    # Save screenshot info
    database.update_payment_with_screenshot(payment_id, photo, caption)
    
    # Get payment details
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
    
    # Forward to all admins
    admin_msg = (
        f"💰 <b>New Payment Request</b>\n\n"
        f"<b>Payment ID:</b> <code>{payment_id}</code>\n"
        f"<b>User:</b> {update.effective_user.first_name}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{update.effective_user.username}\n"
        f"<b>Amount:</b> {amount} Rs\n"
        f"<b>Plan:</b> {plan}\n"
        f"<b>Transaction ID:</b> {caption}\n\n"
        f"<b>Admin Commands:</b>\n"
        f"/approve {payment_id} - ✅ Activate user\n"
        f"/reject {payment_id} [reason] - ❌ Reject"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo,
                caption=admin_msg,
                parse_mode='HTML'
            )
        except:
            pass
    
    await update.message.reply_text(
        f"✅ <b>Payment proof received!</b>\n\n"
        f"Payment ID: <code>{payment_id}</code>\n"
        f"Admin will verify within 1-2 hours.\n"
        f"You'll receive license key after approval.",
        parse_mode='HTML'
    )
    
    context.user_data['current_payment_id'] = None
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

# ========== MY PLAN COMMAND ==========
async def myplan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current plan and upgrade options"""
    user_id = update.effective_user.id
    
    license_info = database.get_user_license(user_id)
    
    if not license_info:
        await update.message.reply_text(
            "❌ Aapke paas koi active plan nahi hai!\n"
            "/buy se naya plan lein."
        )
        return
    
    plan, expiry, license_key = license_info
    expiry_date = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S.%f')
    days_left = (expiry_date - datetime.now()).days
    
    # Format expiry date
    expiry_str = expiry_date.strftime('%d-%b-%Y %I:%M %p')
    
    msg = (
        f"📊 <b>Aapka Current Plan</b>\n\n"
        f"<b>Plan:</b> {plan.upper()}\n"
        f"<b>License:</b> <code>{license_key}</code>\n"
        f"<b>Expiry:</b> {expiry_str}\n"
        f"<b>Days Left:</b> {days_left}\n\n"
    )
    
    # Show upgrade options
    keyboard = []
    if plan == 'weekly':
        msg += "<b>Upgrade Options:</b>\n"
        msg += "• Monthly (add 23 days for 200 Rs)\n"
        msg += "• Yearly (add 358 days for 1900 Rs)"
        keyboard = [
            [InlineKeyboardButton("📆 Upgrade to Monthly - 200 Rs", callback_data="upgrade_weekly_monthly")],
            [InlineKeyboardButton("🎫 Upgrade to Yearly - 1900 Rs", callback_data="upgrade_weekly_yearly")]
        ]
    elif plan == 'monthly':
        msg += "<b>Upgrade Options:</b>\n"
        msg += "• Yearly (add 335 days for 1700 Rs)"
        keyboard = [
            [InlineKeyboardButton("🎫 Upgrade to Yearly - 1700 Rs", callback_data="upgrade_monthly_yearly")]
        ]
    else:
        msg += "✅ Aapke paas best plan hai!"
    
    msg += "\n\n<b>Renewal:</b>\n/renew - Same plan renew karein"
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode='HTML')

async def renew_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renew current plan"""
    user_id = update.effective_user.id
    
    license_info = database.get_user_license(user_id)
    
    if not license_info:
        await update.message.reply_text("❌ Pehle /buy se plan lein.")
        return
    
    plan, expiry, license_key = license_info
    amount = PRICES[plan]
    
    # Generate payment ID
    payment_id = generate_payment_id()
    context.user_data['payment_plan'] = plan
    context.user_data['payment_id'] = payment_id
    context.user_data['renewal'] = True
    context.user_data['old_license'] = license_key
    
    database.save_pending_payment(payment_id, user_id, amount, plan)
    
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_data = f"MOVIEBOT|{payment_id}|{amount}|PKR|RENEW"
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    instructions = (
        f"🔄 <b>Renew {plan.upper()} Plan</b>\n\n"
        f"Amount: {amount} Rs\n"
        f"Payment ID: <code>{payment_id}</code>\n\n"
        f"Send payment to:\n"
        f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
        f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}\n\n"
        f"After payment, click 'I have paid'"
    )
    
    await update.message.reply_photo(
        photo=bio,
        caption=instructions,
        parse_mode='HTML'
    )
    
    keyboard = [[InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{payment_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Click after payment:", reply_markup=reply_markup)

async def upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle upgrade button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Parse upgrade request
    if data.startswith('upgrade_'):
        parts = data.split('_')
        old_plan = parts[1]
        new_plan = parts[2]
        
        # Calculate additional cost
        if old_plan == 'weekly' and new_plan == 'monthly':
            amount = 200
            additional_days = 23
        elif old_plan == 'weekly' and new_plan == 'yearly':
            amount = 1900
            additional_days = 358
        elif old_plan == 'monthly' and new_plan == 'yearly':
            amount = 1700
            additional_days = 335
        else:
            await query.edit_message_text("❌ Invalid upgrade option!")
            return
        
        user_id = query.from_user.id
        payment_id = generate_payment_id()
        
        # Store upgrade info
        context.user_data['upgrade'] = {
            'old_plan': old_plan,
            'new_plan': new_plan,
            'amount': amount,
            'additional_days': additional_days,
            'payment_id': payment_id
        }
        
        # Save payment
        database.save_pending_payment(payment_id, user_id, amount, f"upgrade_{old_plan}_to_{new_plan}")
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_data = f"UPGRADE|{payment_id}|{amount}|PKR|{old_plan}2{new_plan}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        instructions = (
            f"🔼 <b>Upgrade Plan</b>\n\n"
            f"<b>From:</b> {old_plan.upper()}\n"
            f"<b>To:</b> {new_plan.upper()}\n"
            f"<b>Additional Days:</b> {additional_days}\n"
            f"<b>Amount:</b> {amount} Rs\n"
            f"<b>Payment ID:</b> <code>{payment_id}</code>\n\n"
            f"Send payment to:\n"
            f"JazzCash: {PAYMENT_METHODS['jazzcash']}\n"
            f"EasyPaisa: {PAYMENT_METHODS['easypaisa']}"
        )
        
        await query.message.delete()
        await query.message.reply_photo(
            photo=bio,
            caption=instructions,
            parse_mode='HTML'
        )
        
        keyboard = [[InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{payment_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Click after payment:", reply_markup=reply_markup)

# ========== ADMIN APPROVAL COMMANDS ==========
async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approve payment (with renewal/upgrade support)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /approve PAYMENT_ID")
        return
    
    payment_id = context.args[0]
    admin_id = update.effective_user.id
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Get payment details
    cursor.execute('''
        SELECT user_id, plan FROM pending_payments 
        WHERE payment_id = ? AND status = 'pending'
    ''', (payment_id,))
    
    payment = cursor.fetchone()
    
    if not payment:
        await update.message.reply_text("❌ No pending payment found!")
        conn.close()
        return
    
    user_id, plan = payment
    
    # Check if it's an upgrade
    if plan.startswith('upgrade_'):
        # Upgrade case
        parts = plan.split('_')
        old_plan = parts[1]
        new_plan = parts[2]
        
        # Calculate additional days
        if old_plan == 'weekly' and new_plan == 'monthly':
            additional_days = 23
        elif old_plan == 'weekly' and new_plan == 'yearly':
            additional_days = 358
        elif old_plan == 'monthly' and new_plan == 'yearly':
            additional_days = 335
        else:
            additional_days = 0
        
        # Extend license
        new_expiry = database.extend_license(user_id, additional_days)
        
        if new_expiry:
            # Update plan in licenses
            cursor.execute('''
                UPDATE licenses SET plan = ? WHERE user_id = ? AND status = 'active'
            ''', (new_plan, user_id))
            
            license_info = database.get_user_license(user_id)
            license_key = license_info[2] if license_info else "Unknown"
            
            message = f"✅ Plan upgraded from {old_plan} to {new_plan}\nNew expiry: {new_expiry}"
        else:
            message = "❌ No active license found!"
    
    elif plan in ['weekly', 'monthly', 'yearly', '1day']:
        # Check if renewal (user already has license)
        cursor.execute('SELECT license_key FROM licenses WHERE user_id = ? AND status = "active"', (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Renewal case
            days = 7 if plan == 'weekly' else 30 if plan == 'monthly' else 365 if plan == 'yearly' else 1
            new_expiry = database.extend_license(user_id, days)
            license_key = existing[0]
            message = f"✅ License renewed! New expiry: {new_expiry}"
        else:
            # New license
            license_key = generate_license_key()
            days = 7 if plan == 'weekly' else 30 if plan == 'monthly' else 365 if plan == 'yearly' else 1
            database.save_license(license_key, user_id, plan, days)
            message = f"✅ New license created: {license_key}"
    else:
        message = "Unknown plan type"
    
    # Update payment status
    database.approve_payment(payment_id, admin_id)
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Payment approved!\n{message}")
    
    # Notify user
    try:
        license_info = database.get_user_license(user_id)
        if license_info:
            plan, expiry, license_key = license_info
            expiry_str = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S.%f').strftime('%d-%b-%Y')
            
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"السلام علیکم! 👋\n\n"
                    f"✅ <b>Payment Approved!</b>\n\n"
                    f"<b>License:</b> <code>{license_key}</code>\n"
                    f"<b>Plan:</b> {plan}\n"
                    f"<b>Expiry:</b> {expiry_str}\n\n"
                    f"اب آپ bot use kar sakte hain!\n\n"
                    f"شکریہ! 🙏"
                ),
                parse_mode='HTML'
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
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM pending_payments WHERE payment_id = ? AND status = "pending"', (payment_id,))
    payment = cursor.fetchone()
    conn.close()
    
    if not payment:
        await update.message.reply_text("❌ No pending payment found!")
        return
    
    user_id = payment[0]
    
    database.reject_payment(payment_id, update.effective_user.id, reason)
    
    await update.message.reply_text(f"❌ Payment {payment_id} rejected")
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ <b>Payment Rejected</b>\n\n"
                f"Payment ID: <code>{payment_id}</code>\n"
                f"Reason: {reason}\n\n"
                f"Please contact admin for more information."
            ),
            parse_mode='HTML'
        )
    except:
        pass

# ========== ADMIN PANEL FUNCTIONS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel command"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Aap admin nahi hain!")
        return
    
    total_users = database.get_total_users()
    total_movies = database.get_total_movies()
    total_requests = database.get_total_requests()
    active_users = database.get_active_license_count()
    
    pending = database.get_all_pending_payments()
    pending_count = len(pending)
    
    # HTML format - safe from parsing errors
    stats = (
        f"<b>👑 ADMIN DASHBOARD</b>\n\n"
        f"<b>📊 STATISTICS:</b>\n"
        f"• Total Users: {total_users}\n"
        f"• Active Users: {active_users}\n"
        f"• Total Movies: {total_movies}\n"
        f"• Pending Requests: {total_requests}\n"
        f"• Pending Payments: {pending_count}\n\n"
        f"<b>PENDING PAYMENTS:</b>\n"
    )
    
    for p in pending[:5]:
        stats += f"• <code>{p[0]}</code> - User {p[1]} - {p[3]} - {p[2]} Rs\n"
    
    if pending_count > 5:
        stats += f"... and {pending_count-5} more\n"
    
    stats += "\nUse /approve PAYMENT_ID to approve"
    
    # Send with HTML parse mode
    await update.message.reply_text(stats, parse_mode='HTML')
