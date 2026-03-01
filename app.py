# -*- coding: utf-8 -*-
import os
import threading
import time
import logging
from flask import Flask, jsonify
import bot

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "Movie Bot is running on Railway! ??"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_bot():
    """Run the bot in a separate thread"""
    try:
        bot.main()
    except Exception as e:
        logging.error(f"Bot error: {e}")
        time.sleep(5)
        run_bot()

# Start bot in background
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)