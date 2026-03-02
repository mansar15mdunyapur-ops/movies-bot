# -*- coding: utf-8 -*-
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes,
    ConversationHandler
)
import database
import payment
import admin

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
ADMIN_IDS = [8178162794]  # Apna ID

# Initialize database
database.init_database()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== KEYBOARD FUNCTIONS ==========
def get_main_keyboard(user_id=None):
    """Main menu keyboard - hamesha dikhega"""
    
    # Main buttons - 2 in each row
    keyboard = [
        [KeyboardButton("🎬 Search Movie"), KeyboardButton("🎥 My Collection")],
        [KeyboardButton("💳 Buy Plan"), KeyboardButton("📋 My Plan")],
        [KeyboardButton("📝 Request Movie"), KeyboardButton("❓ Help")],
        [KeyboardButton("📞 Contact Admin")]
    ]
    
    # Admin button sirf admin ke liye
    if user_id and user_id in ADMIN_IDS:
        keyboard.append([KeyboardButton("👑 Admin Panel")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== TMDb API FUNCTIONS ==========
def search_tmdb(query):
    if not TMDB_API_KEY:
        logger.error("TMDB_API_KEY not found!")
        return []
    
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        'api_key': TMDB_API_KEY,
        'query': query,
        'language': 'en-US',
        'page': 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('results', [])
        else:
            logger.error(f"TMDb API error: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

def get_tmdb_details(movie_id):
    if not TMDB_API_KEY:
        return None
    
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'append_to_response': 'credits'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Details error: {e}")
    return None

# ========== LANGUAGE FILTER FUNCTIONS (FIXED) ==========
def filter_movies_by_language(movies, language):
    """Filter movies by exact language"""
    if language == 'all':
        return movies
    
    filtered = []
    
    for movie in movies:
        title = movie.get('title', '').lower()
        original_lang = movie.get('original_language', '').lower()
        overview = movie.get('overview', '').lower()
        
        # Urdu movies - exact match
        if language == 'urdu':
            if original_lang == 'ur' or 'urdu' in title or 'pakistan' in title or 'lahore' in title:
                filtered.append(movie)
        
        # Punjabi movies - exact match
        elif language == 'punjabi':
            if original_lang == 'pa' or 'punjabi' in title or 'jatt' in title or 'sardar' in title:
                filtered.append(movie)
        
        # Hindi movies - exact match
        elif language == 'hindi':
            if original_lang == 'hi' or 'hindi' in title or 'bollywood' in title:
                filtered.append(movie)
        
        # Hindi Dubbed movies
        elif language == 'hindidubbed':
            if 'dubbed' in title or 'hindi' in title or 'desi' in title:
                filtered.append(movie)
        
        # English movies - exact match
        elif language == 'english':
            if original_lang == 'en':
                filtered.append(movie)
        
        # All others
        elif language == 'all':
            filtered.append(movie)
    
    return filtered

# ========== BOT COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username, user.first_name)
    
    # Get keyboard with buttons
    keyboard = get_main_keyboard(user.id)
    
    welcome_msg = (
        f"السلام علیکم <b>{user.first_name}!</b> ورحمتہ اللہ وبرکاتہ\n\n"
        "🎬 <b>Movie Bot</b> mein khush amdeed!\n\n"
        "👇 <b>Neche diye gaye buttons use karo:</b>\n"
        "• 🎬 Search Movie - Movie search karo\n"
        "• 🎥 My Collection - Hamari collection dekho\n"
        "• 💳 Buy Plan - Subscription lo\n"
        "• 📋 My Plan - Apna plan check karo\n"
        "• 📝 Request Movie - Nai movie request karo\n"
        "• ❓ Help - Madad\n"
        "• 📞 Contact Admin - Admin se contact\n"
    )
    
    # Send message with keyboard
    await update.message.reply_text(
        welcome_msg, 
        reply_markup=keyboard, 
        parse_mode='HTML'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = get_main_keyboard(update.effective_user.id)
    
    help_text = (
        "📚 <b>Madad</b> 📚\n\n"
        "<b>🎯 Movie Search:</b>\n"
        "• 'Search Movie' button dabao\n"
        "• Pehle language select karo\n"
        "• Phir movie ka naam likho\n\n"
        "<b>📋 Commands:</b>\n"
        "• /movies - Saari available movies\n"
        "• /buy - Subscription plans\n"
        "• /myplan - Current plan details\n"
        "• /renew - Plan renew karein\n"
        "• /activate [key] - License activate karo\n\n"
        "<b>💳 Payment Issues?</b>\n"
        "Contact admin: @Movieshub015helps"
    )
    
    await update.message.reply_text(help_text, reply_markup=keyboard, parse_mode='HTML')

async def movies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = get_main_keyboard(update.effective_user.id)
    results = database.search_movies_db("")
    
    if not results:
        await update.message.reply_text("📭 Filhaal koi movies nahi hain collection mein.", reply_markup=keyboard)
        return
    
    msg = "🎥 <b>Hamari Collection:</b>\n\n"
    for tmdb_id, title, year in results[:10]:
        msg += f"• {title} ({year})\n"
    
    msg += f"\nTotal: {len(results)} movies"
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='HTML')

async def search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search mode with language selection"""
    keyboard_main = get_main_keyboard(update.effective_user.id)
    
    # Language selection buttons
    keyboard_inline = [
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hindi"),
         InlineKeyboardButton("🇵🇰 Urdu", callback_data="lang_urdu")],
        [InlineKeyboardButton("🎭 Punjabi", callback_data="lang_punjabi"),
         InlineKeyboardButton("🇮🇳 Hindi Dubbed", callback_data="lang_hindidubbed")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_english"),
         InlineKeyboardButton("🎬 All Languages", callback_data="lang_all")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
    
    await update.message.reply_text(
        "🔍 <b>Movie Search</b>\n\n"
        "Pehle language select karo:",
        reply_markup=reply_markup_inline,
        parse_mode='HTML'
    )
    
    context.user_data['search_mode'] = True

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    lang = data.replace('lang_', '')
    
    # Store language in context
    context.user_data['selected_language'] = lang
    
    # Language display names
    lang_names = {
        'hindi': '🇮🇳 Hindi',
        'urdu': '🇵🇰 Urdu',
        'punjabi': '🎭 Punjabi',
        'hindidubbed': '🇮🇳 Hindi Dubbed',
        'english': '🇺🇸 English',
        'all': '🎬 All Languages'
    }
    
    lang_display = lang_names.get(lang, lang.upper())
    
    await query.edit_message_text(
        f"✅ <b>{lang_display}</b> select ki gayi\n\n"
        f"Ab movie ka naam likho:",
        parse_mode='HTML'
    )
    
    # Set flag for movie search
    context.user_data['awaiting_movie_name'] = True

async def request_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request mode activate"""
    keyboard = get_main_keyboard(update.effective_user.id)
    await update.message.reply_text(
        "📝 Kaunsi movie chahiye? Naam likho:",
        reply_markup=keyboard
    )
    context.user_data['request_mode'] = True

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Contact admin"""
    keyboard = get_main_keyboard(update.effective_user.id)
    await update.message.reply_text(
        "📞 Admin se contact karne ke liye:\n"
        "Telegram: @movieshub015help\n"
        "Email: mansar15mdunyapur.com",
        reply_markup=keyboard
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks from keyboard"""
    text = update.message.text
    user_id = update.effective_user.id
    keyboard = get_main_keyboard(user_id)
    
    # Main menu buttons
    if text == "🎬 Search Movie":
        await search_mode(update, context)
    
    elif text == "🎥 My Collection":
        await movies_command(update, context)
    
    elif text == "💳 Buy Plan":
        await payment.buy_command(update, context)
    
    elif text == "📋 My Plan":
        await payment.myplan_command(update, context)
    
    elif text == "📝 Request Movie":
        await request_mode(update, context)
    
    elif text == "❓ Help":
        await help_command(update, context)
    
    elif text == "📞 Contact Admin":
        await contact_admin(update, context)
    
    elif text == "👑 Admin Panel" and user_id in ADMIN_IDS:
        await payment.admin_panel(update, context)
    
    # Handle search mode - movie name after language selection
    elif context.user_data.get('awaiting_movie_name'):
        query = text
        context.user_data['awaiting_movie_name'] = False
        await handle_message(update, context)
    
    # Handle request mode
    elif context.user_data.get('request_mode'):
        query = text
        context.user_data['request_mode'] = False
        database.add_request(user_id, query)
        await update.message.reply_text(
            f"✅ '{query}' request add kar di!",
            reply_markup=keyboard
        )
    
    # Normal message - direct search with last used language
    else:
        await handle_message(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle movie search results with exact language filter"""
    query = update.message.text.strip()
    
    if query.startswith('/'):
        return
    
    # Get selected language (default to all)
    selected_lang = context.user_data.get('selected_language', 'all')
    
    await update.message.chat.send_action(action='typing')
    
    # Search on TMDb
    results = search_tmdb(query)
    
    if not results:
        keyboard_inline = [[InlineKeyboardButton("📝 Request Movie", callback_data=f"req_{query}")]]
        reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
        
        await update.message.reply_text(
            f"❌ '{query}' ke liye koi movie nahi mili!",
            reply_markup=reply_markup_inline
        )
        return
    
    # Filter results by exact language
    filtered_results = filter_movies_by_language(results, selected_lang)
    
    # Agar filtered results empty hain to user ko batao
    if not filtered_results:
        lang_names = {
            'hindi': '🇮🇳 Hindi',
            'urdu': '🇵🇰 Urdu',
            'punjabi': '🎭 Punjabi',
            'hindidubbed': '🇮🇳 Hindi Dubbed',
            'english': '🇺🇸 English',
            'all': '🎬 All Languages'
        }
        lang_display = lang_names.get(selected_lang, selected_lang)
        
        keyboard_inline = [
            [InlineKeyboardButton("🌍 Search in All Languages", callback_data="lang_all")],
            [InlineKeyboardButton("📝 Request Movie", callback_data=f"req_{query}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
        
        await update.message.reply_text(
            f"❌ <b>{lang_display}</b> mein '{query}' ke liye koi movie nahi mili!\n\n"
            f"Dobara search karo ya language change karo.",
            reply_markup=reply_markup_inline,
            parse_mode='HTML'
        )
        return
    
    # Language display names
    lang_names = {
        'hindi': '🇮🇳 Hindi',
        'urdu': '🇵🇰 Urdu',
        'punjabi': '🎭 Punjabi',
        'hindidubbed': '🇮🇳 Hindi Dubbed',
        'english': '🇺🇸 English',
        'all': '🎬 All Languages'
    }
    
    lang_display = lang_names.get(selected_lang, 'All Languages')
    
    # TMDb results dikhao
    keyboard_inline = []
    for movie in filtered_results[:5]:
        title = movie['title']
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
        original_lang = movie.get('original_language', '')
        
        # Language flag emoji based on actual language
        if original_lang == 'hi':
            lang_flag = "🇮🇳"
        elif original_lang == 'ur':
            lang_flag = "🇵🇰"
        elif original_lang == 'pa':
            lang_flag = "🎭"
        elif original_lang == 'en':
            lang_flag = "🇺🇸"
        else:
            lang_flag = "🌍"
        
        btn_text = f"{lang_flag} {title} ({year})"
        keyboard_inline.append([InlineKeyboardButton(btn_text, callback_data=f"info_{movie['id']}")])
    
    # Filter and main menu options
    keyboard_inline.append([InlineKeyboardButton("🔍 Change Language", callback_data="show_languages")])
    keyboard_inline.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
    
    reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
    
    await update.message.reply_text(
        f"🔍 <b>'{query}' ke liye {len(filtered_results)} results</b>\n"
        f"📌 <b>Language:</b> {lang_display}\n\n"
        f"👇 Select movie:",
        reply_markup=reply_markup_inline,
        parse_mode='HTML'
    )

async def show_languages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show language filter options"""
    query = update.callback_query
    await query.answer()
    
    keyboard_inline = [
        [InlineKeyboardButton("🇮🇳 Hindi", callback_data="filter_hindi"),
         InlineKeyboardButton("🇵🇰 Urdu", callback_data="filter_urdu")],
        [InlineKeyboardButton("🎭 Punjabi", callback_data="filter_punjabi"),
         InlineKeyboardButton("🇮🇳 Hindi Dubbed", callback_data="filter_hindidubbed")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="filter_english"),
         InlineKeyboardButton("🎬 All Languages", callback_data="filter_all")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_results")]
    ]
    reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
    
    await query.edit_message_text(
        "🔍 <b>Filter by Language:</b>\n\n"
        "Choose language:",
        reply_markup=reply_markup_inline,
        parse_mode='HTML'
    )

async def filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language filter selection"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    lang = data.replace('filter_', '')
    
    context.user_data['selected_language'] = lang
    
    # Language display names
    lang_names = {
        'hindi': '🇮🇳 Hindi',
        'urdu': '🇵🇰 Urdu',
        'punjabi': '🎭 Punjabi',
        'hindidubbed': '🇮🇳 Hindi Dubbed',
        'english': '🇺🇸 English',
        'all': '🎬 All Languages'
    }
    
    lang_display = lang_names.get(lang, lang.upper())
    
    await query.edit_message_text(
        f"✅ <b>{lang_display}</b> filter applied!\n\n"
        f"Ab dobara movie search karo.",
        parse_mode='HTML'
    )

async def back_to_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to previous results"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("🔍 Dobara movie search karo.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    keyboard_main = get_main_keyboard(user_id)
    
    if query.data == "main_menu":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="🔙 Main Menu:",
            reply_markup=keyboard_main
        )
        return
    
    data = query.data.split('_')
    action = data[0]
    
    if action == "info":
        movie_id = int(data[1])
        
        # Send loading message
        loading_msg = await context.bot.send_message(
            chat_id=query.from_user.id,
            text="⏳ Movie details la raha hoon..."
        )
        
        movie = get_tmdb_details(movie_id)
        
        if not movie:
            await loading_msg.edit_text("❌ Details nahi mil sakin!")
            return
        
        title = movie['title']
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
        rating = movie.get('vote_average', 0)
        runtime = movie.get('runtime', 'N/A')
        
        genres = ', '.join([g['name'] for g in movie.get('genres', [])])
        
        cast = []
        if movie.get('credits') and movie['credits'].get('cast'):
            cast = [a['name'] for a in movie['credits']['cast'][:3]]
        cast_text = ', '.join(cast) if cast else 'N/A'
        
        overview = movie.get('overview', 'No overview available.')
        if len(overview) > 300:
            overview = overview[:300] + '...'
        
        info_msg = (
            f"🎬 <b>{title}</b> ({year})\n\n"
            f"⭐ <b>Rating:</b> {rating}/10\n"
            f"⏱️ <b>Runtime:</b> {runtime} min\n"
            f"🎭 <b>Genres:</b> {genres}\n"
            f"👥 <b>Cast:</b> {cast_text}\n\n"
            f"📝 <b>Story:</b>\n{overview}\n\n"
        )
        
        keyboard_inline = [
            [InlineKeyboardButton("📝 Request This Movie", callback_data=f"req_{title}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
        
        # Delete loading message
        await loading_msg.delete()
        
        if movie.get('poster_path'):
            poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            await query.message.reply_photo(
                photo=poster_url,
                caption=info_msg,
                reply_markup=reply_markup_inline,
                parse_mode='HTML'
            )
        else:
            await query.message.reply_text(info_msg, reply_markup=reply_markup_inline, parse_mode='HTML')
    
    elif action == "req":
        movie_name = '_'.join(data[1:])
        database.add_request(query.from_user.id, movie_name)
        
        await query.edit_message_text(
            f"✅ Request received!\n\nMovie: {movie_name}\nHum jald hi ise add karenge. Thanks! 🙏",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
            ]])
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    error_str = str(context.error)
    if "There is no text in the message to edit" in error_str:
        return
    
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Koi error aagaya! Thodi der baad try karein."
            )
    except:
        pass

# ========== MAIN FUNCTION ==========
def main():
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN nahi mila!")
        return
    
    if not TMDB_API_KEY:
        print("❌ Error: TMDB_API_KEY nahi mila!")
        return
    
    print(f"✅ TMDB_API_KEY found")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("movies", movies_command))
    
    # Payment commands
    app.add_handler(CommandHandler("buy", payment.buy_command))
    app.add_handler(CommandHandler("myplan", payment.myplan_command))
    app.add_handler(CommandHandler("renew", payment.renew_command))
    app.add_handler(CommandHandler("activate", payment.activate_command))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", payment.admin_panel))
    app.add_handler(CommandHandler("approve", payment.approve_payment))
    app.add_handler(CommandHandler("reject", payment.reject_payment))
    app.add_handler(CommandHandler("addmovie", admin.add_movie_start))
    
    # Add conversation handler for add movie process
    from admin import ADD_MOVIE_TMDB, ADD_MOVIE_QUALITY, ADD_MOVIE_FILE, ADD_MOVIE_SIZE
    
    add_movie_conv = ConversationHandler(
        entry_points=[CommandHandler('addmovie', admin.add_movie_start)],
        states={
            ADD_MOVIE_TMDB: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.add_movie_tmdb)],
            ADD_MOVIE_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.add_movie_quality)],
            ADD_MOVIE_FILE: [MessageHandler(filters.VIDEO, admin.add_movie_file)],
            ADD_MOVIE_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.add_movie_size)],
        },
        fallbacks=[CommandHandler('cancel', admin.cancel)]
    )
    app.add_handler(add_movie_conv)
    
    # ========== CALLBACK HANDLERS - CORRECT ORDER ==========
    # 1. Language callbacks
    app.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    app.add_handler(CallbackQueryHandler(show_languages, pattern='^show_languages$'))
    app.add_handler(CallbackQueryHandler(filter_callback, pattern='^filter_'))
    app.add_handler(CallbackQueryHandler(back_to_results, pattern='^back_to_results$'))
    
    # 2. Payment callbacks
    app.add_handler(CallbackQueryHandler(payment.payment_callback, pattern='^buy_'))
    app.add_handler(CallbackQueryHandler(payment.paid_callback, pattern='^paid_'))
    app.add_handler(CallbackQueryHandler(payment.upgrade_callback, pattern='^upgrade_'))
    
    # 3. General button callback (catch all)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Conversation handler for payment screenshots
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(payment.paid_callback, pattern='^paid_')],
        states={
            payment.WAITING_SCREENSHOT: [MessageHandler(filters.PHOTO, payment.handle_screenshot)]
        },
        fallbacks=[CommandHandler("cancel", payment.cancel)]
    )
    app.add_handler(conv_handler)
    
    # Button handler for main keyboard
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("🎬 Movie Bot starting with EXACT LANGUAGE FILTER...")
    print("✅ Database connected!")
    print(f"📊 Total movies in DB: {database.get_total_movies()}")
    print(f"👥 Total users: {database.get_total_users()}")
    print(f"📝 Total requests: {database.get_total_requests()}")
    print("🚀 Bot is running!")
    
    # Start polling
    app.run_polling()

if __name__ == '__main__':
    main()
