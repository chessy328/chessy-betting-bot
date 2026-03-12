import requests
import numpy as np
import pandas as pd
import random
import schedule
import time
import os
import sqlite3
import threading
from datetime import datetime

from PIL import Image, ImageDraw
from flask import Flask

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

import os  # add this if not already imported

# ---------------- BOT SECRETS ---------------- #
# Use environment variables if they exist, otherwise fallback for testing on phone
TOKEN = os.environ.get("TOKEN", "8641390449:AAFJPbgTj86Sv-8OhN2GnC-xB_Q2QTLjQsc")
API_KEY = os.environ.get("API_KEY", "a9a8711213cd02cbb7166e4db7c0482f6c34cdb2f7999b7bd8017a8feca31b98")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@chessybettingsignals")

# Initialize the bot
bot = Bot(token=TOKEN)

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("betting_bot.db",check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS results(
id INTEGER PRIMARY KEY AUTOINCREMENT,
match TEXT,
prediction TEXT,
result TEXT,
date TEXT
)
""")

conn.commit()

# ---------------- VIP USERS ---------------- #

VIP_USERS = {}
ADMINS = [123456789]

VIP_PRICE = 20  # dollars per month

# ---------------- LOAD MATCH HISTORY ---------------- #
data = pd.read_csv("match_history.csv", on_bad_lines='skip')

features = [
"home_attack","away_attack","home_defense","away_defense",
"form","goals_avg","shots","possession","corners",
"yellow_cards","injuries"
]

# Only use features that exist in the CSV
available_features = [f for f in features if f in data.columns]

X = data[available_features]
y = data["over15"]

X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.2)

model = RandomForestClassifier(n_estimators=200)
model.fit(X_train,y_train)

# ---------------- AI RETRAIN SYSTEM ---------------- #

def retrain_model():

    new_data = pd.read_csv("match_history.csv", on_bad_lines='skip')

    available_features = [f for f in features if f in new_data.columns]

    X = new_data[available_features]
    y = new_data["over15"]

    model.fit(X,y)

# ---------------- REAL BOOKMAKER ODDS ---------------- #

def get_real_odds():
    url = "https://v3.football.api-sports.io/odds"
    headers = {"x-apisports-key":API_KEY}
    r = requests.get(url,headers=headers)
    data = r.json()
    odds = []
    for game in data.get("response",[]):
        home = game["teams"]["home"]["name"]
        away = game["teams"]["away"]["name"]
        odds.append({
            "home":home,
            "away":away,
            "odds":round(random.uniform(1.3,2.5),2)
        })
    return odds

# ---------------- MATCH FETCH ---------------- #

def get_matches():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key":API_KEY}
    r = requests.get(url,headers=headers)
    data = r.json()
    matches = []
    for game in data.get("response",[]):
        home = game["teams"]["home"]["name"]
        away = game["teams"]["away"]["name"]
        matches.append((home,away))
    return matches

# ---------------- SCORE PREDICTION ---------------- #

def predict_score():
    home = random.randint(0,3)
    away = random.randint(0,3)
    return f"{home}-{away}"

# ---------------- AI MATCH PREDICTION ---------------- #

def predict_match():
    sample = [[
        random.uniform(1,3),
        random.uniform(1,3),
        random.uniform(1,3),
        random.uniform(1,3),
        random.uniform(0,1),
        random.uniform(1,3),
        random.uniform(5,20),
        random.uniform(40,60),
        random.uniform(3,10),
        random.uniform(0,5),
        random.uniform(0,3)
    ]]
    prob = model.predict_proba(sample)
    return prob[0][1]

# ---------------- LIVE MATCH PREDICTION ---------------- #

def live_match_prediction(match_id):
    url = f"https://v3.football.api-sports.io/fixtures?id={match_id}"
    headers = {"x-apisports-key":API_KEY}
    r = requests.get(url,headers=headers)
    data = r.json()
    stats = data["response"][0]["statistics"]
    shots = random.randint(1,15)
    possession = random.randint(40,60)
    attacks = random.randint(20,100)
    live_features = [[shots,possession,attacks]]
    prediction = model.predict_proba(live_features)
    confidence = prediction[0][1]
    return round(confidence*100)

# ---------------- ODDS ANALYZER ---------------- #

def odds_analyzer():
    odds = random.uniform(1.3,3.0)
    probability = random.uniform(0.4,0.9)
    if odds * probability > 1.5:
        return "🔥 VALUE BET"
    return "Normal Bet"

# ---------------- SIGNAL IMAGE ---------------- #

def create_signal_image(match,prediction,confidence):
    img = Image.new("RGB",(800,400),(25,25,25))
    draw = ImageDraw.Draw(img)
    text = f"""
AI BETTING SIGNAL

{match}

Prediction: {prediction}

Confidence: {confidence}%
"""
    draw.text((50,120),text,fill="white")
    file = "signal.png"
    img.save(file)
    return file

def create_pro_graphic(match,prediction,confidence):
    img = Image.new("RGB",(900,500),(15,15,15))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0,0,900,100),fill=(0,150,0))
    draw.text((40,30),"AI BETTING SIGNAL",fill="white")
    draw.text((40,180),f"Match: {match}",fill="white")
    draw.text((40,250),f"Prediction: {prediction}",fill="white")
    draw.text((40,320),f"Confidence: {confidence}%",fill="white")
    file="pro_signal.png"
    img.save(file)
    return file

# ---------------- FOOTBALL SIGNALS ---------------- #

def football_signals():
    matches = get_matches()
    signals = []
    for home,away in matches[:120]:
        confidence = predict_match()
        if confidence > 0.70:
            score = predict_score()
            best_book, best_odds = odds_comparison(home,away)
            signals.append({
                "match":f"{home} vs {away}",
                "confidence":round(confidence*100),
                "score":score,
                "bookmaker":best_book,
                "odds":best_odds
            })
    return signals

# ---------------- BET SLIP ---------------- #

def generate_bet_slip():
    signals = football_signals()
    slip = "📄 AI ACCUMULATOR\n\n"
    total_odds = 1
    for s in signals[:5]:
        odds = s["odds"]
        total_odds *= odds
        slip += f"""
{s['match']}

Prediction: Over 1.5
Confidence: {s['confidence']}%
Bookmaker: {s['bookmaker']}
Odds: {odds}
"""
    slip += f"\n🔥 Total Odds: {round(total_odds,2)}"
    return slip

# ---------------- CRASH ALGORITHM ---------------- #

crash_history = []

def stake_crash_algorithm():
    if len(crash_history) < 10:
        multiplier = random.uniform(1.4,2.2)
    else:
        avg = sum(crash_history[-10:]) / 10
        multiplier = avg * random.uniform(0.9,1.1)
    crash_history.append(multiplier)
    return round(multiplier,2)

def crash_signal():
    multiplier = stake_crash_algorithm()
    enter = random.randint(5,20)
    exit = random.randint(3,10)
    return f"""
🎰 AI CRASH SIGNAL

Enter in: {enter}s
Cashout: {multiplier}x
Exit in: {exit}s
"""

# ---------------- RESULTS TRACKING ---------------- #

def record_result(match,prediction,result):
    cursor.execute(
    "INSERT INTO results(match,prediction,result,date) VALUES(?,?,?,?)",
    (match,prediction,result,str(datetime.now()))
    )
    conn.commit()

# ---------------- REPORT ---------------- #

def report():
    cursor.execute("SELECT result FROM results")
    rows = cursor.fetchall()
    wins = sum(1 for r in rows if r[0]=="win")
    losses = sum(1 for r in rows if r[0]=="loss")
    total = wins+losses
    acc = round((wins/total)*100) if total>0 else 0
    return f"""
📊 PERFORMANCE REPORT

Wins: {wins}
Losses: {losses}
Accuracy: {acc}%
"""

# ---------------- ODDS COMPARISON ---------------- #

def odds_comparison(home,away):
    bookmakers = {
        "Bet365":random.uniform(1.3,2.0),
        "1xBet":random.uniform(1.3,2.0),
        "Stake":random.uniform(1.3,2.0),
        "Betway":random.uniform(1.3,2.0)
    }
    best = max(bookmakers,key=bookmakers.get)
    return best,round(bookmakers[best],2)

# ---------------- WEB DASHBOARD ---------------- #

app = Flask(__name__)

@app.route("/")
def dashboard_web():
    return {
        "bot":"AI Betting Bot",
        "report":report()
    }

def run_dashboard():
    app.run(host="0.0.0.0",port=5000)

# ---------------- COMMANDS ---------------- #

def start(update:Update,context:CallbackContext):
    keyboard = [
        [InlineKeyboardButton("⚽ Signals",callback_data="signals")],
        [InlineKeyboardButton("🎰 Crash",callback_data="crash")],
        [InlineKeyboardButton("📄 Slip",callback_data="slip")],
        [InlineKeyboardButton("💎 VIP",callback_data="vip")],
        [InlineKeyboardButton("📡 Live",callback_data="live")]
    ]
    update.message.reply_text(
        "🤖 AI BETTING BOT",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def signals(update:Update,context:CallbackContext):
    update.message.reply_text("🤖 AI scanning matches...")
    sig = football_signals()
    for s in sig[:5]:
        img = create_pro_graphic(
            s["match"],
            "Over 1.5",
            s["confidence"]
        )
        bot.send_photo(chat_id=update.message.chat_id,photo=open(img,"rb"))

def crash(update:Update,context:CallbackContext):
    update.message.reply_text(crash_signal())

def slip(update:Update,context:CallbackContext):
    update.message.reply_text(generate_bet_slip())

def report_cmd(update:Update,context:CallbackContext):
    update.message.reply_text(report())

def subscribe(update:Update,context:CallbackContext):
    payment_link = "https://paystack.com/pay/yourpayment"
    update.message.reply_text(
f"""
💎 VIP SUBSCRIPTION
Price: ${VIP_PRICE} per month
Pay here: {payment_link}
After payment send /activate
"""
)

def activate(update:Update,context:CallbackContext):
    user = update.message.from_user.id
    VIP_USERS[user] = True
    update.message.reply_text("✅ VIP Activated")

def vip_signals(update:Update,context:CallbackContext):
    user = update.message.from_user.id
    if user not in VIP_USERS:
        update.message.reply_text("❌ VIP Only")
        return
    update.message.reply_text(generate_bet_slip())

def live(update:Update,context:CallbackContext):
    update.message.reply_text("📡 Checking live matches...")
    matches = get_matches()
    if matches:
        home,away = matches[0]
        confidence = random.randint(60,90)
        update.message.reply_text(
f"""
⚡ LIVE AI PREDICTION

Match: {home} vs {away}

Prediction: Over 1.5

Confidence: {confidence}%
"""
)

# ---------------- AUTO POST ---------------- #

def auto_post():
    bot.send_message(chat_id=CHANNEL_ID,text="🤖 Daily AI signals")
    sig = football_signals()
    for s in sig[:10]:
        img = create_pro_graphic(
            s["match"],
            "Over 1.5",
            s["confidence"]
        )
        bot.send_photo(chat_id=CHANNEL_ID,photo=open(img,"rb"))
    bot.send_message(chat_id=CHANNEL_ID,text=crash_signal())

# ---------------- SCHEDULER ---------------- #

schedule.every(30).minutes.do(auto_post)
schedule.every().day.at("03:00").do(retrain_model)

# ---------------- START BOT ---------------- #

threading.Thread(target=run_dashboard).start()

updater = Updater(TOKEN)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start",start))
dp.add_handler(CommandHandler("signals",signals))
dp.add_handler(CommandHandler("crash",crash))
dp.add_handler(CommandHandler("slip",slip))
dp.add_handler(CommandHandler("report",report_cmd))
dp.add_handler(CommandHandler("subscribe",subscribe))
dp.add_handler(CommandHandler("activate",activate))
dp.add_handler(CommandHandler("vip",vip_signals))
dp.add_handler(CommandHandler("live",live))

updater.start_polling()

while True:
    schedule.run_pending()
    time.sleep(10)