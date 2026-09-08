import os
import sys
import asyncio
from threading import Thread
from flask import Flask
from bot import bot, dp

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    print("🚀 Запускаю бота...")
    try:
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        print(f"⚠️ Бот упал: {e}")
        sys.exit(1)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask сервер запускается на порту {port}")
    
    # Запускаем бота в фоновом потоке
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask
    app.run(host="0.0.0.0", port=port)