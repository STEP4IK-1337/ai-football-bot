import os
import sys
import asyncio
from threading import Thread
from flask import Flask
from bot import bot, dp

app = Flask(__name__)

@app.route('/')
def index():
    if os.path.exists("data/Matches.csv"):
        return "Bot is running with data!", 200
    else:
        return "Bot is running, but data files are missing.", 200

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    print("🚀 Запускаю бота...")
    while True:
        try:
            asyncio.run(dp.start_polling(bot))
        except Exception as e:
            print(f"⚠️ Бот упал: {e}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask сервер запущен на порту {port}")
    Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=port)