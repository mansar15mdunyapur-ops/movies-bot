# -*- coding: utf-8 -*-
import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes,
    ConversationHandler
)
import database
import payment
import admin  # <-- IMPORTANT: Admin module add kiya

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

# ========== BOT COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username, user.first_name)
    
    welcome_msg = (
        f"السلام علیکم <b>{user.first_name}!</b> ورحمتہ اللہ وبرکاتہ\n\n"
        "🎬 <b>Movie Bot</b> mein khush amdeed!\n\n"
        "<b>✨ Features:</b>\n"
        "• Movie search - Kisi bhi movie ka naam likho\n"
        "• Movie details - Rating, cast, story, poster\n"
        "• Subscription - /buy se lo\n\n"
        "<b>📌 Commands:</b>\n"
        "/movies - Collection dekhein\n"
        "/buy - Subscription plans\n"
        "/myplan - Apna plan check karein\n"
        "/help - Madad\n\n"
        "<b>Bas movie ka naam likho!</b> 🔍"
    )
    await update.message.reply_text(welcome_msg, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 <b>Madad</b> 📚\n\n"
        "<b>🎯 Movie Search:</b>\n"
        "• Direct naam likho - Jaise 'Avengers', '3 Idiots'\n\n"
        "<b>📋 Commands:</b>\n"
        "/movies - Saari available movies\n"
        "/buy - Subscription plans\n"
        "/myplan - Current plan details\n"
        "/renew - Plan renew karein\n"
        "/activate [key] - License activate karo\n"
        "/help - Yeh message\n\n"
        "<b>💳 Payment Issues?</b>\n"
        "Contact admin: @YourAdminUsername"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def movies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = database.search_movies_db("")
    
    if not results:
        await update.message.reply_text("📭 Filhaal koi movies nahi hain collection mein.")
        return
    
    msg = "🎥 <b>Hamari Collection:</b>\n\n"
    for tmdb_id, title, year in results[:10]:
        msg += f"• {title} ({year})\n"
    
    msg += f"\nTotal: {len(results)} movies"
    await update.message.reply_text(msg, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    
    if query.startswith('/'):
        return
    
    await update.message.chat.send_action(action='typing')
    
    # Search on TMDb
    results = search_tmdb(query)
    
    if not results:
        keyboard = [[InlineKeyboardButton("📝 Request Movie", callback_data=f"req_{query}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ '{query}' ke liye koi movie nahi mili!\n\n"
            "Request karo, hum add kar denge:",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for movie in results[:5]:
        title = movie['title']
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
        btn_text = f"ℹ️ {title} ({year})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"info_{movie['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🔍 <b>'{query}' ke liye {len(results)} results:</b>\n\n"
        "Details ke liye select karo:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
        
        keyboard = [[InlineKeyboardButton("📝 Request This Movie", callback_data=f"req_{title}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Delete loading message
        await loading_msg.delete()
        
        if movie.get('poster_path'):
            poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            await query.message.reply_photo(
                photo=poster_url,
                caption=info_msg,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.message.reply_text(info_msg, reply_markup=reply_markup, parse_mode='HTML')
    
    elif action == "req":
        movie_name = '_'.join(data[1:])
        database.add_request(query.from_user.id, movie_name)
        
        # Check if message is photo or text
        try:
            if query.message.photo:
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=f"✅ Request received!\n\nMovie: {movie_name}\nHum jald hi ise add karenge. Thanks! 🙏"
                )
                await query.message.delete()
            else:
                await query.edit_message_text(
                    f"✅ Request received!\n\nMovie: {movie_name}\nHum jald hi ise add karenge. Thanks! 🙏"
                )
        except:
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=f"✅ Request received!\n\nMovie: {movie_name}\nHum jald hi ise add karenge. Thanks! 🙏"
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    # Ignore specific errors
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
    
    # ========== ADD MOVIE COMMAND (FIX) ==========
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
    # ==============================================
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(payment.payment_callback, pattern='^buy_'))
    app.add_handler(CallbackQueryHandler(payment.paid_callback, pattern='^paid_'))
    app.add_handler(CallbackQueryHandler(payment.upgrade_callback, pattern='^upgrade_'))
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
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("🎬 Movie Bot starting...")
    print("✅ Database connected!")
    print(f"📊 Total movies in DB: {database.get_total_movies()}")
    print(f"👥 Total users: {database.get_total_users()}")
    print(f"📝 Total requests: {database.get_total_requests()}")
    print("🚀 Bot is running!")
    
    # Start polling
    app.run_polling()

if __name__ == '__main__':
    main()
