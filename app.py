import os
import zipfile
import requests  # убедитесь, что этот импорт есть в начале файла
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
    # ЗДЕСЬ ВСТАВЬТЕ ВАШУ ПРЯМУЮ ССЫЛКУ
    url = "https://drive.google.com/uc?export=download&id=1ig14dSVXzT5qj7iONoNEnZb7mWTcNHph"
    try:
        response = requests.get(url, timeout=120)  # увеличенный таймаут для больших файлов
        response.raise_for_status()  # Проверяем, не возникла ли ошибка
        with open("data.zip", "wb") as f:
            f.write(response.content)
        print("✅ data.zip успешно скачан.")
        
        print("📦 Распаковываю data.zip...")
        with zipfile.ZipFile("data.zip", "r") as zip_ref:
            zip_ref.extractall(".")
        print("✅ data.zip распакован.")
    except Exception as e:
        print(f"❌ Ошибка при скачивании или распаковке: {e}")
        # Здесь можно добавить логику повторной попытки или остановки бота