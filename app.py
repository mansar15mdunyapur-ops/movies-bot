# -*- coding: utf-8 -*-
import os
import threading
import time
import logging
import asyncio
from flask import Flask, jsonify
import bot

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "Movie Bot is running on Railway! 🎬"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_bot():
    """Run the bot with proper event loop"""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run bot in this loop
        bot.main()
        
    except Exception as e:
        logging.error(f"Bot error: {e}")
        time.sleep(5)
        # Don't recursively call, just let the thread exit
        # Railway will restart if needed
        return

# Start bot in background thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# Also create a watchdog thread to monitor bot thread
def watchdog():
    while True:
        time.sleep(30)
        if not bot_thread.is_alive():
            logging.error("Bot thread died! Starting new thread...")
            new_thread = threading.Thread(target=run_bot, daemon=True)
            new_thread.start()
            # Update global reference
            globals()['bot_thread'] = new_thread

watchdog_thread = threading.Thread(target=watchdog, daemon=True)
watchdog_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
