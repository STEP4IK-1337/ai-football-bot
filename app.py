import os
import zipfile
import requests
from threading import Thread
from flask import Flask
from bot import bot, dp
import asyncio

app = Flask(__name__)

# =====================
# СКАЧИВАНИЕ И РАСПАКОВКА data.zip (в папку data/)
# =====================
def download_and_extract():
    # Проверяем, есть ли уже данные
    if os.path.exists("data/Matches.csv") and os.path.exists("data/EloRatings.csv"):
        print("✅ Файлы данных уже есть")
        return True
    
    # Ссылка на data.zip на GitHub (RAW)
    url = "https://raw.githubusercontent.com/STEP4IK-1337/ai-football-bot/main/data.zip"
    zip_path = "data.zip"
    
    print("📦 Скачиваю data.zip с GitHub...")
    try:
        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            print(f"❌ Ошибка скачивания: {response.status_code}")
            return False
        
        with open(zip_path, "wb") as f:
            f.write(response.content)
        print(f"✅ data.zip скачан ({len(response.content)} байт)")
        
        # СОЗДАЁМ ПАПКУ data
        os.makedirs("data", exist_ok=True)
        
        # Распаковываем файлы В ПАПКУ data
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for file in zip_ref.namelist():
                # Извлекаем каждый файл прямо в папку data
                zip_ref.extract(file, "data")
        print("✅ data.zip распакован в папку data")
        
        # Удаляем архив
        os.remove(zip_path)
        print("🗑️ data.zip удалён")
        
        # Проверяем
        if os.path.exists("data/Matches.csv") and os.path.exists("data/EloRatings.csv"):
            print("✅ Файлы Matches.csv и EloRatings.csv на месте")
            return True
        else:
            print("❌ Файлы не найдены после распаковки")
            print(f"   Содержимое папки data: {os.listdir('data')}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# =====================
# FLASK
# =====================
@app.route('/')
def index():
    if os.path.exists("data/Matches.csv"):
        return "Bot is running with data!", 200
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
    
    # Скачиваем данные перед запуском
    print("📥 Загружаю данные...")
    if download_and_extract():
        print("✅ Данные готовы")
    else:
        print("⚠️ Бот запустится без данных")
    
    # Запускаем бота
    Thread(target=run_bot, daemon=True).start()
    
    # Запускаем Flask
    print(f"🌐 Flask сервер на порту {port}")
    app.run(host="0.0.0.0", port=port)