import asyncio
import os
import sys
import json
import pandas as pd
import random
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =====================
# ФАЙЛЫ
# =====================
USERS_FILE = "users.json"
DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
matches_file = os.path.join(DATA_PATH, "Matches.csv")
elo_file = os.path.join(DATA_PATH, "EloRatings.csv")

# =====================
# РЕФЕРАЛЬНЫЕ ССЫЛКИ
# =====================
REGISTER_URL = "https://lkfv.cc/a284"
DEPOSIT_URL = "https://lkfv.cc/a284"

# =====================
# ЗАГРУЗКА ДАННЫХ
# =====================
print("📥 Загружаю данные...")

if not os.path.exists(matches_file):
    print(f"❌ Файл {matches_file} не найден!")
    sys.exit(1)
if not os.path.exists(elo_file):
    print(f"❌ Файл {elo_file} не найден!")
    sys.exit(1)

try:
    matches_df = pd.read_csv(matches_file, low_memory=False)
    elo_df = pd.read_csv(elo_file, names=["Date", "Team", "Country", "Elo"], skiprows=1)
except Exception as e:
    print(f"❌ Ошибка загрузки данных: {e}")
    sys.exit(1)

team_elo = {row["Team"]: row["Elo"] for _, row in elo_df.iterrows()}
print(f"✅ Загружено матчей: {len(matches_df)}")
print(f"✅ Загружено команд с Elo: {len(team_elo)}")

# =====================
# БАЗА КОМАНД
# =====================
TEAMS_DB = {}
for team in set(matches_df["HomeTeam"].unique()).union(set(matches_df["AwayTeam"].unique())):
    if pd.isna(team):
        continue
    elo = team_elo.get(team, 1500)
    strength = max(50, min(99, int((elo - 1300) / 10)))
    TEAMS_DB[team.lower()] = {
        "name": team, "strength": strength,
        "attack": strength + random.randint(-5, 5),
        "defense": strength + random.randint(-5, 5),
        "form": strength + random.randint(-5, 5),
        "home_advantage": 5, "elo": elo
    }
print(f"✅ Добавлено команд: {len(TEAMS_DB)}")

SYNONYMS = {
    "зенит": "Zenit", "спартак": "Spartak Moscow", "цска": "CSKA Moscow",
    "динамо": "Dinamo Minsk", "динамо минск": "Dinamo Minsk", "батэ": "BATE Borisov",
    "шахтер": "Shakhtyor Soligorsk", "шахтёр": "Shakhtyor Soligorsk",
    "неман": "Neman Grodno", "торпедо": "Torpedo-BelAZ Zhodino", "локомотив": "Lokomotiv Moscow",
}

# =====================
# ПОЛЬЗОВАТЕЛИ
# =====================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(user_id: int):
    users = load_users()
    return users.get(str(user_id))

def update_user(user_id: int, data: dict):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def is_completed(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    return bool(user.get("completed"))

def create_user_if_not_exists(user_id: int):
    user = get_user(user_id)
    if not user:
        update_user(user_id, {
            "registered": False,
            "deposited": False,
            "completed": False
        })

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
        keyboard=[
            [KeyboardButton(text="/analyze")]
        ],
        resize_keyboard=True
    )

# =====================
# ТЕКСТЫ
# =====================
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
# ФУНКЦИИ АНАЛИЗА
# =====================
def find_team(name):
    name_lower = name.lower().strip()
    if name_lower in SYNONYMS:
        name_lower = SYNONYMS[name_lower].lower()
    if name_lower in TEAMS_DB:
        return TEAMS_DB[name_lower]
    for key, team in TEAMS_DB.items():
        if name_lower in key or key in name_lower:
            return team
    return None

def parse_teams(text):
    for sep in [" | ", " против ", " vs ", " — ", " - "]:
        if sep in text:
            parts = text.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    words = text.split()
    if len(words) >= 2:
        mid = len(words) // 2
        return " ".join(words[:mid]), " ".join(words[mid:])
    return None, None

def get_last_matches(team_name, count=5):
    team_matches = matches_df[(matches_df["HomeTeam"] == team_name) | (matches_df["AwayTeam"] == team_name)]
    if len(team_matches) == 0:
        return None
    team_matches = team_matches.sort_values("MatchDate", ascending=False).head(count)
    return team_matches

def get_head_to_head(t1_name, t2_name):
    h2h = matches_df[
        ((matches_df["HomeTeam"] == t1_name) & (matches_df["AwayTeam"] == t2_name)) |
        ((matches_df["HomeTeam"] == t2_name) & (matches_df["AwayTeam"] == t1_name))
    ]
    return h2h.sort_values("MatchDate", ascending=False)

def get_team_stats(team_name, use_last=5):
    team_matches = get_last_matches(team_name, use_last)
    if team_matches is None or len(team_matches) == 0:
        return None
    
    wins = draws = losses = goals_for = goals_against = 0
    over25_count = over35_count = btts_count = total_matches = 0
    odds_sum = {"home": 0, "draw": 0, "away": 0, "over25": 0, "under25": 0}
    odds_count = 0
    
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
        if gf + ga > 3.5:
            over35_count += 1
        if gf > 0 and ga > 0:
            btts_count += 1
        
        if not pd.isna(row.get("OddHome")):
            odds_sum["home"] += row["OddHome"]
            odds_sum["draw"] += row["OddDraw"]
            odds_sum["away"] += row["OddAway"]
            odds_sum["over25"] += row.get("Over25", 0)
            odds_sum["under25"] += row.get("Under25", 0)
            odds_count += 1
    
    if total_matches == 0:
        return None
    
    return {
        "matches": total_matches, "wins": wins, "draws": draws, "losses": losses,
        "win_rate": wins/total_matches, "draw_rate": draws/total_matches,
        "lose_rate": losses/total_matches,
        "goals_for": goals_for, "goals_against": goals_against,
        "avg_goals_for": goals_for/total_matches,
        "avg_goals_against": goals_against/total_matches,
        "over25_rate": over25_count/total_matches,
        "over35_rate": over35_count/total_matches,
        "btts_rate": btts_count/total_matches,
        "avg_odds": {
            "home": odds_sum["home"] / odds_count if odds_count > 0 else 0,
            "draw": odds_sum["draw"] / odds_count if odds_count > 0 else 0,
            "away": odds_sum["away"] / odds_count if odds_count > 0 else 0,
            "over25": odds_sum["over25"] / odds_count if odds_count > 0 else 0,
            "under25": odds_sum["under25"] / odds_count if odds_count > 0 else 0,
        } if odds_count > 0 else None
    }

def get_h2h_stats(t1_name, t2_name):
    h2h = get_head_to_head(t1_name, t2_name)
    if len(h2h) == 0:
        return None
    
    t1_wins = t2_wins = draws = 0
    goals_t1 = goals_t2 = 0
    over25_count = 0
    btts_count = 0
    
    for _, row in h2h.iterrows():
        if row["HomeTeam"] == t1_name:
            gf, ga = row["FTHome"], row["FTAway"]
        else:
            gf, ga = row["FTAway"], row["FTHome"]
        if pd.isna(gf) or pd.isna(ga):
            continue
        goals_t1 += gf
        goals_t2 += ga
        if gf > ga:
            t1_wins += 1
        elif gf == ga:
            draws += 1
        else:
            t2_wins += 1
        if gf + ga > 2.5:
            over25_count += 1
        if gf > 0 and ga > 0:
            btts_count += 1
    
    total = len(h2h)
    return {
        "matches": total,
        "t1_wins": t1_wins,
        "t2_wins": t2_wins,
        "draws": draws,
        "t1_win_rate": t1_wins / total,
        "t2_win_rate": t2_wins / total,
        "draw_rate": draws / total,
        "goals_t1": goals_t1,
        "goals_t2": goals_t2,
        "avg_goals_t1": goals_t1 / total,
        "avg_goals_t2": goals_t2 / total,
        "over25_rate": over25_count / total,
        "btts_rate": btts_count / total
    }

def calc_probs(t1, t2):
    s1, s2 = get_team_stats(t1["name"]), get_team_stats(t2["name"])
    h2h = get_h2h_stats(t1["name"], t2["name"])
    
    if h2h:
        p1_h2h = h2h["t1_win_rate"]
        p2_h2h = h2h["t2_win_rate"]
        pd_h2h = h2h["draw_rate"]
    else:
        p1_h2h = 0.33
        p2_h2h = 0.33
        pd_h2h = 0.34
    
    if s1 and s2:
        p1_form = s1["win_rate"] * 0.6 + s2["lose_rate"] * 0.4
        p2_form = s2["win_rate"] * 0.6 + s1["lose_rate"] * 0.4
        pd_form = s1["draw_rate"] * 0.5 + s2["draw_rate"] * 0.5
    else:
        p1_form = 0.33
        p2_form = 0.33
        pd_form = 0.34
    
    p1 = p1_h2h * 0.6 + p1_form * 0.4
    p2 = p2_h2h * 0.6 + p2_form * 0.4
    pd_ = pd_h2h * 0.6 + pd_form * 0.4
    
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
    
    if h2h:
        over25 = int(h2h["over25_rate"] * 100 * 0.5 + ((s1["over25_rate"] if s1 else 0.5) * 0.25 + (s2["over25_rate"] if s2 else 0.5) * 0.25) * 100)
        btts = int(h2h["btts_rate"] * 100 * 0.5 + ((s1["btts_rate"] if s1 else 0.5) * 0.25 + (s2["btts_rate"] if s2 else 0.5) * 0.25) * 100)
    else:
        over25 = int(((s1["over25_rate"] if s1 else 0.5) * 0.5 + (s2["over25_rate"] if s2 else 0.5) * 0.5) * 100)
        btts = int(((s1["btts_rate"] if s1 else 0.5) * 0.5 + (s2["btts_rate"] if s2 else 0.5) * 0.5) * 100)
    
    over35 = max(10, over25 - 20)
    over25 = max(10, min(85, over25))
    over35 = max(10, min(80, over35))
    btts = max(10, min(80, btts))
    
    value = None
    if s1 and s1.get("avg_odds") and s2 and s2.get("avg_odds"):
        avg_odds = s1["avg_odds"]
        fair_home = 1 / (p1 / 100) if p1 > 0 else 0
        fair_draw = 1 / (pd_ / 100) if pd_ > 0 else 0
        fair_away = 1 / (p2 / 100) if p2 > 0 else 0
        
        if avg_odds["home"] > fair_home * 1.1 and avg_odds["home"] > 0:
            value = f"🔹 Валуй: Победа {t1['name']} (кф {avg_odds['home']:.2f} > честный {fair_home:.2f})"
        elif avg_odds["away"] > fair_away * 1.1 and avg_odds["away"] > 0:
            value = f"🔹 Валуй: Победа {t2['name']} (кф {avg_odds['away']:.2f} > честный {fair_away:.2f})"
    
    return p1, pd_, p2, over25, over35, btts, value, h2h

def generate_factors(t1, t2, p1, pd_, p2, over25, over35, btts, s1, s2, h2h, value=None):
    factors = []
    under25 = 100 - over25
    
    if p1 > p2 and p1 > pd_:
        factors.append(f"🔹 {t1['name']} — фаворит ({p1}%)")
    elif p2 > p1 and p2 > pd_:
        factors.append(f"🔹 {t2['name']} — фаворит ({p2}%)")
    else:
        factors.append("🔹 Матч равный, вероятна ничья")
    
    if h2h:
        factors.append(f"🔹 Личные встречи: {h2h['matches']} матчей")
        factors.append(f"🔹 {t1['name']} выиграл {h2h['t1_wins']}, {t2['name']} выиграл {h2h['t2_wins']}, ничьих {h2h['draws']}")
        factors.append(f"🔹 Средний тотал в личных встречах: {h2h['avg_goals_t1'] + h2h['avg_goals_t2']:.2f}")
    
    avg_total = (s1["avg_goals_for"] + s2["avg_goals_for"]) if s1 and s2 else 2.5
    if avg_total >= 3.0:
        factors.append(f"🔹 Высокая результативность (средний тотал {avg_total:.2f})")
    elif avg_total >= 2.5:
        factors.append(f"🔹 Средняя результативность (средний тотал {avg_total:.2f})")
    else:
        factors.append(f"🔹 Низкая результативность (средний тотал {avg_total:.2f})")
    
    if over25 >= 65:
        factors.append(f"🔹 Тотал больше 2.5 — высокая вероятность ({over25}%)")
    elif under25 >= 65:
        factors.append(f"🔹 Тотал меньше 2.5 — высокая вероятность ({under25}%)")
    else:
        factors.append(f"🔹 Тотал 2.5 — неопределённость ({over25}% / {under25}%)")
    
    if btts >= 60:
        factors.append(f"🔹 Обе забьют — высокая вероятность ({btts}%)")
    elif btts <= 40:
        factors.append(f"🔹 Обе забьют — низкая вероятность ({btts}%)")
    else:
        factors.append(f"🔹 Обе забьют — неопределённость ({btts}%)")
    
    if t1.get("elo") and t2.get("elo"):
        elo_diff = t1["elo"] - t2["elo"]
        if abs(elo_diff) > 100:
            leader = t1["name"] if elo_diff > 0 else t2["name"]
            factors.append(f"🔹 {leader} значительно выше по Elo ({abs(elo_diff):.0f} очков)")
    
    if value:
        factors.append(value)
    
    return "\n".join(factors)

# =====================
# ФОРМАТИРОВАНИЕ МАТЧЕЙ (СПИСКАМИ)
# =====================
def format_h2h_list(t1_name, t2_name, limit=10):
    h2h = get_head_to_head(t1_name, t2_name).head(limit)
    if len(h2h) == 0:
        return "❌ Нет личных встреч"
    
    lines = ["📅 Последние личные встречи:"]
    for i, (_, row) in enumerate(h2h.iterrows(), 1):
        date = row["MatchDate"][:10] if pd.notna(row["MatchDate"]) else "—"
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        score = f"{int(row['FTHome'])}:{int(row['FTAway'])}" if pd.notna(row["FTHome"]) else "—"
        odd_h = f"{row['OddHome']:.2f}" if pd.notna(row.get("OddHome")) else "—"
        odd_d = f"{row['OddDraw']:.2f}" if pd.notna(row.get("OddDraw")) else "—"
        odd_a = f"{row['OddAway']:.2f}" if pd.notna(row.get("OddAway")) else "—"
        lines.append(f"{i}) {date} {home} {score} {away} | Кф: {odd_h} / {odd_d} / {odd_a}")
    
    return "\n".join(lines)

def format_last_matches_list(team_name, limit=5):
    matches = get_last_matches(team_name, limit)
    if matches is None or len(matches) == 0:
        return f"❌ Нет матчей для {team_name}"
    
    lines = [f"📅 Последние {len(matches)} матчей {team_name}:"]
    for i, (_, row) in enumerate(matches.iterrows(), 1):
        date = row["MatchDate"][:10] if pd.notna(row["MatchDate"]) else "—"
        if row["HomeTeam"] == team_name:
            opponent = row["AwayTeam"]
            gf, ga = row["FTHome"], row["FTAway"]
            result = "🏠 Победа" if gf > ga else ("🏠 Ничья" if gf == ga else "🏠 Пораж.")
        else:
            opponent = row["HomeTeam"]
            gf, ga = row["FTAway"], row["FTHome"]
            result = "✈️ Победа" if gf > ga else ("✈️ Ничья" if gf == ga else "✈️ Пораж.")
        
        score = f"{int(gf)}:{int(ga)}" if pd.notna(gf) else "—"
        total = ">2.5" if gf + ga > 2.5 else "<2.5"
        lines.append(f"{i}) {date} vs {opponent} {score} {result} | Тотал: {total}")
    
    return "\n".join(lines)

# =====================
# HANDLERS
# =====================
@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    create_user_if_not_exists(user_id)
    
    if is_completed(user_id):
        await message.answer(
            "🎉 Добро пожаловать обратно!\n"
            "Напиши /analyze Команда1 | Команда2\n\n"
            "Пример:\n"
            "/analyze Zenit | Spartak Moscow"
        )
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
        await message.answer(
            "⚠️ Сначала пройди регистрацию и депозит.",
            reply_markup=step1_keyboard()
        )
        return
    
    text = message.text.replace("/analyze", "").strip()
    if not text:
        await message.answer("Напиши так: /analyze Команда1 | Команда2")
        return
    
    team1_name, team2_name = parse_teams(text)
    if not team1_name or not team2_name:
        await message.answer("❌ Не могу распознать команды.\nИспользуй формат:\n/analyze Команда1 | Команда2")
        return
    
    t1 = find_team(team1_name)
    t2 = find_team(team2_name)
    
    if not t1:
        last_matches = get_last_matches(team1_name, 10)
        if last_matches is not None and len(last_matches) > 0:
            t1 = {
                "name": team1_name,
                "strength": 70,
                "attack": 70,
                "defense": 70,
                "form": 70,
                "home_advantage": 5,
                "elo": 1500
            }
            await message.answer(f"⚠️ Команда '{team1_name}' не найдена в базе, но есть {len(last_matches)} матчей в истории.")
        else:
            await message.answer(f"❌ Команда '{team1_name}' не найдена и нет истории матчей.")
            return
    
    if not t2:
        last_matches = get_last_matches(team2_name, 10)
        if last_matches is not None and len(last_matches) > 0:
            t2 = {
                "name": team2_name,
                "strength": 70,
                "attack": 70,
                "defense": 70,
                "form": 70,
                "home_advantage": 5,
                "elo": 1500
            }
            await message.answer(f"⚠️ Команда '{team2_name}' не найдена в базе, но есть {len(last_matches)} матчей в истории.")
        else:
            await message.answer(f"❌ Команда '{team2_name}' не найдена и нет истории матчей.")
            return
    
    if t1["name"] == t2["name"]:
        await message.answer("❌ Укажи две РАЗНЫЕ команды!")
        return
    
    p1, pd_, p2, over25, over35, btts, value, h2h = calc_probs(t1, t2)
    s1, s2 = get_team_stats(t1["name"]), get_team_stats(t2["name"])
    
    # Все рынки с процентами
    all_markets = [
        ("Победа " + t1["name"], p1),
        ("Ничья", pd_),
        ("Победа " + t2["name"], p2),
        ("Тотал больше 2.5", over25),
        ("Тотал больше 3.5", over35),
        ("Обе забьют (BTTS)", btts)
    ]
    
    # Сортируем по убыванию вероятности
    sorted_markets = sorted(all_markets, key=lambda x: x[1], reverse=True)
    
    # Первый прогноз (самый вероятный)
    best = sorted_markets[0]
    
    # Второй прогноз (второй по вероятности, если его вероятность >= 50%)
    second = None
    if len(sorted_markets) > 1 and sorted_markets[1][1] >= 50:
        second = sorted_markets[1]
    
    # Формируем сигналы для вывода
    signals = []
    for market, prob in all_markets:
        if prob >= 70:
            signals.append((market, prob))
    
    if not signals:
        signal_text = f"⚠️ Нет явных сигналов (макс. {best[1]}%)"
    else:
        best_signal = max(signals, key=lambda x: x[1])
        signal_text = f"✅ {best_signal[0]} — {best_signal[1]}%"
    
    # Дополнительный прогноз
    second_text = ""
    if second:
        second_text = f"\n📌 Дополнительный прогноз: {second[0]} — {second[1]}%"
    else:
        second_text = "\n📌 Дополнительный прогноз: нет (все рынки < 50%)"
    
    factors = generate_factors(t1, t2, p1, pd_, p2, over25, over35, btts, s1, s2, h2h, value)
    
    h2h_text = ""
    if h2h:
        h2h_text = f"""
📊 ЛИЧНЫЕ ВСТРЕЧИ (всего {h2h['matches']} матчей)
▫️ Побед {t1['name']}: {h2h['t1_wins']} | Ничьих: {h2h['draws']} | Побед {t2['name']}: {h2h['t2_wins']}
▫️ Голы: {t1['name']} {h2h['goals_t1']:.1f} — {h2h['goals_t2']:.1f} {t2['name']}
▫️ Тотал > 2.5: {int(h2h['over25_rate'] * 100)}% | Обе забьют: {int(h2h['btts_rate'] * 100)}%
"""
    
    h2h_list = format_h2h_list(t1["name"], t2["name"], 10)
    last_list1 = format_last_matches_list(t1["name"], 5)
    last_list2 = format_last_matches_list(t2["name"], 5)
    
    stats_text = ""
    if s1 and s2:
        stats_text = f"""
📊 ПОСЛЕДНИЕ 5 МАТЧЕЙ (статистика)
▫️ {t1['name']}
   • Матчей: {s1['matches']} | Побед: {s1['wins']} | Ничьих: {s1['draws']} | Поражений: {s1['losses']}
   • Голов: за {s1['goals_for']:.1f} / пропущено {s1['goals_against']:.1f}
   • Тотал > 2.5: {int(s1['over25_rate'] * 100)}% | Обе забьют: {int(s1['btts_rate'] * 100)}%

▫️ {t2['name']}
   • Матчей: {s2['matches']} | Побед: {s2['wins']} | Ничьих: {s2['draws']} | Поражений: {s2['losses']}
   • Голов: за {s2['goals_for']:.1f} / пропущено {s2['goals_against']:.1f}
   • Тотал > 2.5: {int(s2['over25_rate'] * 100)}% | Обе забьют: {int(s2['btts_rate'] * 100)}%
"""
    
    await message.answer(f"""
⚽️ AI-Анализ матча
{t1['name']} — {t2['name']}

📊 % СОБЫТИЙ
▫️ Тотал больше 2.5: {over25}%
▫️ Тотал больше 3.5: {over35}%
▫️ Обе забьют (BTTS): {btts}%
▫️ Победа {t1['name']}: {p1}%
▫️ Ничья: {pd_}%
▫️ Победа {t2['name']}: {p2}%

🎯 ПРОГНОЗЫ
🔹 Основной: {best[0]} — {best[1]}%
{second_text}

🔍 КЛЮЧЕВЫЕ ФАКТОРЫ
{factors}

{h2h_text}

{h2h_list}

{last_list1}

{last_list2}

{stats_text}

⚠️ Риски: Прогноз основан на исторических данных. Травмы, составы и мотивация не учтены.
""")

async def main():
    print("🚀 Бот запущен!")
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}. Переподключаюсь через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())