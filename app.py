import os
import zipfile
import requests
from threading import Thread
from flask import Flask
from bot import bot, dp
import asyncio

app = Flask(__name__)

# =====================
# СКАЧИВАНИЕ И РАСПАКОВКА data.zip ИЗ ОБЛАКА
# =====================
if not os.path.exists("data/Matches.csv"):
    print("📦 Скачиваю data.zip из Google Диска...")
    url = "https://drive.google.com/uc?export=download&id=1ig14dSVXzT5qj7iONoNEnZb7mWTcNHph"
    try:
        response = requests.get(url, timeout=300)  # 5 минут на скачивание
        response.raise_for_status()
        with open("data.zip", "wb") as f:
            f.write(response.content)
        print("✅ data.zip успешно скачан.")
        
        print("📦 Распаковываю data.zip...")
        with zipfile.ZipFile("data.zip", "r") as zip_ref:
            zip_ref.extractall(".")
        print("✅ data.zip распакован.")
        
        # Удаляем архив после распаковки, чтобы сэкономить место
        os.remove("data.zip")
        print("🗑️ data.zip удалён.")
        
    except Exception as e:
        print(f"❌ Ошибка при скачивании или распаковке: {e}")

@app.route('/')
def index():
    return "Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    print("🚀 Запускаю бота...")
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask сервер запущен на порту {port}")
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=port)