import os
import asyncio
import json
import pandas as pd
import random
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# =====================
# ПЕРЕМЕННЫЕ
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден!")
    exit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

USERS_FILE = "users.json"
REGISTER_URL = "https://lkfv.cc/a284"
DEPOSIT_URL = "https://lkfv.cc/a284"

# =====================
# ЗАГРУЗКА ДАННЫХ (ТОЛЬКО ПРИ ПЕРВОМ ЗАПРОСЕ)
# =====================
_matches_df = None
_TEAMS_DB = None

def load_data():
    global _matches_df, _TEAMS_DB
    if _matches_df is not None:
        return _matches_df, _TEAMS_DB

    print("📥 Загружаю данные...")
    try:
        _matches_df = pd.read_csv("data/Matches.csv", low_memory=False)
        elo_df = pd.read_csv("data/EloRatings.csv", names=["Date", "Team", "Country", "Elo"], skiprows=1)
        team_elo = {row["Team"]: row["Elo"] for _, row in elo_df.iterrows()}

        _TEAMS_DB = {}
        for team in set(_matches_df["HomeTeam"].unique()).union(set(_matches_df["AwayTeam"].unique())):
            if pd.isna(team):
                continue
            elo = team_elo.get(team, 1500)
            strength = max(50, min(99, int((elo - 1300) / 10)))
            _TEAMS_DB[team.lower()] = {
                "name": team,
                "strength": strength,
                "attack": strength + random.randint(-5, 5),
                "defense": strength + random.randint(-5, 5),
                "form": strength + random.randint(-5, 5),
                "home_advantage": 5,
                "elo": elo
            }
        print(f"✅ Загружено матчей: {len(_matches_df)} | Команд: {len(_TEAMS_DB)}")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        _matches_df = None
        _TEAMS_DB = None
    return _matches_df, _TEAMS_DB

# =====================
# ПОЛЬЗОВАТЕЛИ
# =====================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    return load_users().get(str(user_id))

def update_user(user_id, data):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def is_completed(user_id):
    user = get_user(user_id)
    return bool(user and user.get("completed"))

def create_user_if_not_exists(user_id):
    if not get_user(user_id):
        update_user(user_id, {"registered": False, "deposited": False, "completed": False})

# =====================
# КЛАВИАТУРЫ
# =====================
def step1_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Зарегистрироваться", url=REGISTER_URL)],
        [InlineKeyboardButton(text="✅ Я выполнил", callback_data="step1_done")]
    ])

def step2_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Внести депозит", url=DEPOSIT_URL)],
        [InlineKeyboardButton(text="✅ Я выполнил", callback_data="step2_done")]
    ])

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/analyze")]],
        resize_keyboard=True
    )

STEP1_TEXT = """⚽ Добро пожаловать!

Чтобы получить доступ к AI-анализу футбольных матчей, пройди 2 простых шага.

Шаг 1 — Регистрация
✦ Перейди по кнопке ниже
✦ При регистрации обязательно введи промокод: 1WINVK500
✦ После регистрации вернись в бота и нажми кнопку «Я выполнил»
"""

STEP2_TEXT = """Отлично! Первый шаг выполнен ✅

Шаг 2 — Внесите депозит
✦ Перейди по той же ссылке
✦ Внеси первый депозит
✦ После этого вернись в бота и нажми кнопку «Я выполнил»
"""

FINAL_TEXT = """🎉 Поздравляем!

Все шаги выполнены.
Теперь тебе доступен AI-анализ футбольных матчей.

Напиши:
/analyze Команда1 | Команда2
"""

# =====================
# ПОИСК КОМАНД
# =====================
def find_team(name, TEAMS_DB):
    name_lower = name.lower().strip()
    if name_lower in TEAMS_DB:
        return TEAMS_DB[name_lower]
    for key, team in TEAMS_DB.items():
        if name_lower in key or key in name_lower:
            return team
    return None

def parse_teams(text):
    for sep in [" | ", " против ", " vs ", " — ", " - "]:
        if sep in text:
            return text.split(sep, 1)[0].strip(), text.split(sep, 1)[1].strip()
    words = text.split()
    if len(words) >= 2:
        mid = len(words) // 2
        return " ".join(words[:mid]), " ".join(words[mid:])
    return None, None

# =====================
# СТАТИСТИКА
# =====================
def get_team_stats(team_name, matches_df, use_last=5):
    team_matches = matches_df[(matches_df["HomeTeam"] == team_name) | (matches_df["AwayTeam"] == team_name)]
    if len(team_matches) == 0:
        return None
    team_matches = team_matches.sort_values("MatchDate", ascending=False).head(use_last)

    wins = draws = losses = goals_for = goals_against = 0
    over25_count = total_matches = 0
    btts_count = 0

    for _, row in team_matches.iterrows():
        if row["HomeTeam"] == team_name:
            gf, ga = row["FTHome"], row["FTAway"]
        else:
            gf, ga = row["FTAway"], row["FTHome"]
        if pd.isna(gf) or pd.isna(ga):
            continue
        goals_for += gf
        goals_against += ga
        total_matches += 1
        if gf > ga:
            wins += 1
        elif gf == ga:
            draws += 1
        else:
            losses += 1
        if gf + ga > 2.5:
            over25_count += 1
        if gf > 0 and ga > 0:
            btts_count += 1

    if total_matches == 0:
        return None

    return {
        "matches": total_matches,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_rate": wins / total_matches,
        "draw_rate": draws / total_matches,
        "lose_rate": losses / total_matches,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "avg_goals_for": goals_for / total_matches,
        "avg_goals_against": goals_against / total_matches,
        "over25_rate": over25_count / total_matches,
        "btts_rate": btts_count / total_matches
    }

def calc_probs(t1, t2, matches_df):
    s1 = get_team_stats(t1["name"], matches_df)
    s2 = get_team_stats(t2["name"], matches_df)

    if not s1 or not s2:
        return 33, 34, 33, 50, 50

    p1 = s1["win_rate"] * 0.6 + s2["lose_rate"] * 0.4
    p2 = s2["win_rate"] * 0.6 + s1["lose_rate"] * 0.4
    pd_ = s1["draw_rate"] * 0.5 + s2["draw_rate"] * 0.5

    elo_diff = t1.get("elo", 1500) - t2.get("elo", 1500)
    if elo_diff > 50:
        p1 += 0.05
        p2 -= 0.05
    elif elo_diff < -50:
        p1 -= 0.05
        p2 += 0.05

    total = p1 + pd_ + p2
    p1 = max(10, min(80, round(p1 / total * 100)))
    pd_ = max(10, min(40, round(pd_ / total * 100)))
    p2 = max(10, min(80, round(p2 / total * 100)))
    total = p1 + pd_ + p2
    p1 = int(p1 / total * 100)
    pd_ = int(pd_ / total * 100)
    p2 = int(p2 / total * 100)

    over25 = int((s1["over25_rate"] * 0.5 + s2["over25_rate"] * 0.5) * 100)
    btts = int((s1["btts_rate"] * 0.5 + s2["btts_rate"] * 0.5) * 100)

    return p1, pd_, p2, over25, btts

def build_analysis(t1, t2, matches_df):
    p1, draw, p2, over25, btts = calc_probs(t1, t2, matches_df)

    fav = t1["name"] if p1 > p2 and p1 > draw else (t2["name"] if p2 > p1 and p2 > draw else "Ничья")
    fav_prob = max(p1, p2, draw)
    under25 = 100 - over25

    markets = []
    if p1 > 50: markets.append(("Победа " + t1["name"], p1))
    if p2 > 50: markets.append(("Победа " + t2["name"], p2))
    if over25 > 60: markets.append(("Тотал больше 2.5", over25))
    if under25 > 60: markets.append(("Тотал меньше 2.5", under25))
    if btts > 55: markets.append(("Обе забьют (BTTS)", btts))
    if not markets:
        markets = [("Победа " + t1["name"], p1), ("Ничья", draw), ("Победа " + t2["name"], p2)]

    best = max(markets, key=lambda x: x[1])
    second = None
    if len(markets) > 1 and markets[1][1] >= 50:
        second = markets[1]

    second_text = f"\n📌 Дополнительный прогноз: {second[0]} — {second[1]}%" if second else "\n📌 Дополнительный прогноз: нет (все рынки < 50%)"

    return f"""
⚽️ AI-Анализ матча
{t1['name']} — {t2['name']}

📊 % СОБЫТИЙ
▫️ Тотал больше 2.5: {over25}%
▫️ Тотал меньше 2.5: {under25}%
▫️ Обе забьют (BTTS): {btts}%
▫️ Победа {t1['name']}: {p1}%
▫️ Ничья: {draw}%
▫️ Победа {t2['name']}: {p2}%

🎯 ПРОГНОЗЫ
🔹 Основной: {best[0]} — {best[1]}%
{second_text}

🔍 КЛЮЧЕВЫЕ ФАКТОРЫ
🔹 {fav} — фаворит ({fav_prob}%)
🔹 {t1['name']}: атака {t1.get('attack', 75)}/100, защита {t1.get('defense', 75)}/100
🔹 {t2['name']}: атака {t2.get('attack', 75)}/100, защита {t2.get('defense', 75)}/100

⚠️ Риски: Прогноз основан на статистической модели.
"""

# =====================
# FLASK
# =====================
@app.route('/')
def index():
    return "Bot is running with data!", 200

@app.route('/health')
def health():
    return "OK", 200

# =====================
# BOT
# =====================
@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    create_user_if_not_exists(user_id)
    if is_completed(user_id):
        await message.answer("🎉 Добро пожаловать обратно!\nНапиши /analyze Команда1 | Команда2")
        return
    await message.answer(STEP1_TEXT, reply_markup=step1_keyboard())

@dp.callback_query(F.data == "step1_done")
async def step1_done(callback):
    user_id = callback.from_user.id
    create_user_if_not_exists(user_id)
    user = get_user(user_id)
    user["registered"] = True
    update_user(user_id, user)
    await callback.message.answer(STEP2_TEXT, reply_markup=step2_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "step2_done")
async def step2_done(callback):
    user_id = callback.from_user.id
    create_user_if_not_exists(user_id)
    user = get_user(user_id)
    user["deposited"] = True
    user["completed"] = True
    update_user(user_id, user)
    await callback.message.answer(FINAL_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.message(Command("analyze"))
async def analyze_handler(message: Message):
    user_id = message.from_user.id
    create_user_if_not_exists(user_id)

    if not is_completed(user_id):
        await message.answer("⚠️ Сначала пройди регистрацию и депозит.", reply_markup=step1_keyboard())
        return

    text = message.text.replace("/analyze", "").strip()
    if not text:
        await message.answer("Напиши так: /analyze Команда1 | Команда2")
        return

    team1_name, team2_name = parse_teams(text)
    if not team1_name or not team2_name:
        await message.answer("❌ Не могу распознать команды.\nИспользуй формат:\n/analyze Команда1 | Команда2")
        return

    matches_df, TEAMS_DB = load_data()

    if matches_df is None:
        await message.answer("❌ Ошибка загрузки данных. Попробуй позже.")
        return

    t1 = find_team(team1_name, TEAMS_DB)
    t2 = find_team(team2_name, TEAMS_DB)

    if not t1:
        await message.answer(f"❌ Команда '{team1_name}' не найдена.\nПопробуй написать на английском.")
        return
    if not t2:
        await message.answer(f"❌ Команда '{team2_name}' не найдена.\nПопробуй написать на английском.")
        return
    if t1["name"] == t2["name"]:
        await message.answer("❌ Укажи две РАЗНЫЕ команды!")
        return

    analysis = build_analysis(t1, t2, matches_df)
    await message.answer(analysis)

# =====================
# ЗАПУСК
# =====================
async def run_bot():
    print("🚀 Запускаю бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    # Бот в фоновом потоке [citation:11][citation:7]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_bot())

    print(f"🌐 Flask сервер на порту {port}")
    app.run(host="0.0.0.0", port=port)