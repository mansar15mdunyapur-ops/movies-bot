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
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')  # 2e822b46b04411667ee5a3723c78e674

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
    """Search movies on TMDb"""
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
        logger.info(f"Searching TMDb for: {query}")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            logger.info(f"Found {len(results)} results")
            return results
        else:
            logger.error(f"TMDb API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

def get_tmdb_details(movie_id):
    """Get detailed movie info from TMDb"""
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
        else:
            logger.error(f"TMDb details error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Details error: {e}")
        return None

# ========== BOT COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    database.add_user(user.id, user.username, user.first_name)
    
    welcome_msg = (
        f"🎬 **Namaste {user.first_name}!** 🎬\n\n"
        "Main aapka **Movie Bot** hoon!\n\n"
        "**✨ Features:**\n"
        "• Movie search - Kisi bhi movie ka naam likho\n"
        "• Movie details - Rating, cast, story, poster\n"
        "• Collection - /movies se dekho\n"
        "• Subscription - /buy se lo\n\n"
        "**📌 Commands:**\n"
        "/movies - Collection dekhein\n"
        "/buy - Subscription plans\n"
        "/help - Madad\n\n"
        "**Bas movie ka naam likho!** 🔍"
    )
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📚 **Bot Guide** 📚\n\n"
        "**🎯 Movie Search:**\n"
        "• Direct naam likho - Jaise 'Avengers', '3 Idiots'\n"
        "• Details ke liye button click karo\n\n"
        "**📋 Commands:**\n"
        "/movies - Saari available movies\n"
        "/buy - Subscription plans\n"
        "/help - Yeh message\n\n"
        "**Need help?** Contact @admin_username"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def movies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available movies in our collection"""
    results = database.search_movies_db("")  # Get all movies
    
    if not results:
        await update.message.reply_text("📭 Filhaal koi movies nahi hain collection mein.")
        return
    
    msg = "🎥 **Hamari Collection:**\n\n"
    for tmdb_id, title, year in results[:10]:  # Show first 10
        msg += f"• {title} ({year})\n"
    
    msg += f"\nTotal: {len(results)} movies"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle movie search"""
    query = update.message.text.strip()
    
    if query.startswith('/'):
        return
    
    await update.message.chat.send_action(action='typing')
    
    # Pehle database mein search karo
    db_results = database.search_movies_db(query)
    
    if db_results:
        # Agar database mein hai to file option do
        keyboard = []
        for tmdb_id, title, year in db_results[:5]:
            btn_text = f"📥 {title} ({year}) [Download]"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"download_{tmdb_id}")])
        
        # TMDb search ka bhi option do
        keyboard.append([InlineKeyboardButton("🔍 TMDb se bhi search karo", callback_data=f"tmdb_{query}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"✅ '{query}' humari collection mein mili!\n\n"
            "Download ke liye select karo:",
            reply_markup=reply_markup
        )
    else:
        # Database mein nahi to TMDb se search karo
        results = search_tmdb(query)
        
        if not results:
            # Request button ke saath
            keyboard = [[InlineKeyboardButton("📝 Request Movie", callback_data=f"req_{query}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"❌ '{query}' ke liye koi movie nahi mili!\n\n"
                "Request karo, hum add kar denge:",
                reply_markup=reply_markup
            )
            return
        
        # TMDb results dikhao
        keyboard = []
        for movie in results[:5]:
            title = movie['title']
            year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
            btn_text = f"ℹ️ {title} ({year})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"info_{movie['id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🔍 **'{query}' ke liye {len(results)} results:**\n\n"
            "Details ke liye select karo:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    
    # Show TMDb info
    if action == "info":
        movie_id = int(data[1])
        await query.edit_message_text("⏳ Movie details la raha hoon...")
        
        movie = get_tmdb_details(movie_id)
        
        if not movie:
            await query.edit_message_text("❌ Details nahi mil sakin!")
            return
        
        # Format movie info
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
            f"🎬 **{title}** ({year})\n\n"
            f"⭐ **Rating:** {rating}/10\n"
            f"⏱️ **Runtime:** {runtime} min\n"
            f"🎭 **Genres:** {genres}\n"
            f"👥 **Cast:** {cast_text}\n\n"
            f"📝 **Story:**\n{overview}\n\n"
        )
        
        # Request button bhi do
        keyboard = [[InlineKeyboardButton("📝 Request This Movie", callback_data=f"req_{title}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if movie.get('poster_path'):
            poster_url = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            await query.message.delete()
            await query.message.reply_photo(
                photo=poster_url,
                caption=info_msg,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(info_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Handle movie request
    elif action == "req":
        movie_name = '_'.join(data[1:])  # Join remaining parts
        user_id = query.from_user.id
        
        # Save request to database
        database.add_request(user_id, 0, movie_name)  # tmdb_id=0 for unknown
        
        await query.edit_message_text(
            f"✅ Request received!\n\n"
            f"Movie: {movie_name}\n"
            f"Hum jald hi ise add karenge. Thanks! 🙏"
        )
    
    # TMDb search from database result
    elif action == "tmdb":
        search_query = '_'.join(data[1:])
        results = search_tmdb(search_query)
        
        if results:
            keyboard = []
            for movie in results[:5]:
                title = movie['title']
                year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
                btn_text = f"ℹ️ {title} ({year})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"info_{movie['id']}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🔍 TMDb se results:\n\nSelect movie:",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("❌ TMDb par bhi koi result nahi mila!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
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
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN nahi mila!")
        print("Please set BOT_TOKEN in Railway variables")
        return
    
    if not TMDB_API_KEY:
        print("❌ Error: TMDB_API_KEY nahi mila!")
        print("Please set TMDB_API_KEY in Railway variables")
        return
    
    print(f"✅ TMDB_API_KEY found: {TMDB_API_KEY[:5]}...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("movies", movies_command))
    
    # Payment handlers
    app.add_handler(CommandHandler("buy", payment.buy_command))
    app.add_handler(CommandHandler("activate", payment.activate_command))
    app.add_handler(CallbackQueryHandler(payment.payment_callback, pattern='^buy_'))
    app.add_handler(CallbackQueryHandler(payment.payment_confirmation, pattern='^paid_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment.handle_transaction))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", payment.admin_panel))
    app.add_handler(CommandHandler("users", payment.admin_users))
    app.add_handler(CommandHandler("requests", payment.admin_requests))
    app.add_handler(CallbackQueryHandler(payment.admin_callback, pattern='^admin_'))
    
    # Message and callback handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    print("🎬 Movie Bot starting...")
    print("✅ Database connected!")
    print(f"📊 Total movies in DB: {database.get_total_movies()}")
    print(f"👥 Total users: {database.get_total_users()}")
    print(f"📝 Total requests: {database.get_total_requests()}")
    print("🚀 Bot is running!")
    
    # Start polling (blocking call)
    app.run_polling()

if __name__ == '__main__':
    main()
