import os
import zipfile
import requests
from threading import Thread
from flask import Flask
from bot import bot, dp
import asyncio
import time

app = Flask(__name__)

# =====================
# СКАЧИВАНИЕ И РАСПАКОВКА data.zip
# =====================
DATA_DIR = "data"
ZIP_FILE = "data.zip"
MATCHES_FILE = os.path.join(DATA_DIR, "Matches.csv")
ELO_FILE = os.path.join(DATA_DIR, "EloRatings.csv")

def download_and_extract():
    """Скачивает и распаковывает data.zip, ищет файлы даже внутри вложенной папки"""
    # Проверяем, есть ли уже данные
    if os.path.exists(MATCHES_FILE) and os.path.exists(ELO_FILE):
        print("✅ Файлы данных уже есть в папке data/")
        return True

    # Создаём папку data, если её нет
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"📁 Папка {DATA_DIR} создана (или уже существует).")

    # Ссылка на Google Диск
    url = "https://drive.google.com/uc?export=download&id=1ig14dSVXzT5qj7iONoNEnZb7mWTcNHph"
    print("📦 Скачиваю data.zip из Google Диска...")

    try:
        # Скачиваем с таймаутом
        response = requests.get(url, timeout=300)
        response.raise_for_status()

        # Сохраняем архив
        with open(ZIP_FILE, "wb") as f:
            f.write(response.content)
        print(f"✅ data.zip скачан (размер: {os.path.getsize(ZIP_FILE) / 1024 / 1024:.2f} МБ)")

        # Распаковываем
        print("📦 Распаковываю архив...")
        with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:
            zip_ref.extractall(".")

        # Удаляем архив
        os.remove(ZIP_FILE)
        print("🗑️ data.zip удалён")

        # Проверяем, есть ли папка data внутри data/
        inner_data = os.path.join(DATA_DIR, DATA_DIR)
        if os.path.exists(inner_data):
            print(f"📁 Найдена вложенная папка data/, перемещаю файлы...")
            for f in os.listdir(inner_data):
                src = os.path.join(inner_data, f)
                dst = os.path.join(DATA_DIR, f)
                os.rename(src, dst)
                print(f"   Перемещён: {f}")
            os.rmdir(inner_data)
            print("✅ Вложенная папка удалена")

        # Проверяем, что файлы появились
        if os.path.exists(MATCHES_FILE) and os.path.exists(ELO_FILE):
            print("✅ Файлы Matches.csv и EloRatings.csv успешно найдены!")
            return True
        else:
            print(f"❌ После распаковки в папке {DATA_DIR} нет нужных файлов!")
            print(f"   Содержимое папки data: {os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else 'папка не создана'}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Ошибка: таймаут при скачивании файла")
        return False
    except Exception as e:
        print(f"❌ Ошибка при скачивании или распаковке: {e}")
        return False

# =====================
# FLASK WEB-СЕРВЕР
# =====================
@app.route('/')
def index():
    return "Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/check')
def check():
    """Проверка, что файлы на месте"""
    if os.path.exists(MATCHES_FILE) and os.path.exists(ELO_FILE):
        return "✅ Все файлы данных на месте", 200
    else:
        return f"❌ Файлы не найдены. Папка data существует: {os.path.exists(DATA_DIR)}", 500

def run_bot():
    """Запускает бота в фоновом потоке"""
    print("🚀 Запускаю бота...")
    while True:
        try:
            asyncio.run(dp.start_polling(bot))
        except Exception as e:
            print(f"⚠️ Бот упал: {e}")
            print("⏳ Перезапуск через 5 секунд...")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask сервер будет запущен на порту {port}")

    # Скачиваем и распаковываем данные
    print("📥 Загружаю данные...")
    if not download_and_extract():
        print("❌ Не удалось загрузить данные. Проверьте ссылку на Google Диск.")
        print("⚠️ Бот продолжит работу, но функциональность может быть ограничена.")

    # Запускаем бота в фоновом потоке
    Thread(target=run_bot, daemon=True).start()

    # Запускаем Flask
    print("🚀 Запускаю Flask веб-сервер...")
    app.run(host="0.0.0.0", port=port)