from flask import Flask, request
import requests
from openai import OpenAI
import os
import threading
import time
from datetime import datetime
import pytz

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
ADMIN_CHAT_ID = "-1002351934678"

conversation_history = {}
last_message_time = {}
pending_timers = {}

DELAY_SECONDS = 10
TIMEZONE = pytz.timezone("Asia/Almaty")

@app.route("/")
def home():
    return "🤖 Telegram бот работает!"

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "ok"

    message = data["message"]
    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]

    # 🚫 Бот отвечает только в личных чатах
    if chat_type != "private":
        return "ok"

    user_id = str(chat_id)
    text = ""

    # Обработка голосового
    if "voice" in message:
        duration = message["voice"].get("duration", 0)
        if duration > 300:
            send_message(chat_id, "Ваше голосовое сообщение довольно длинное 😅 Чтобы всё прошло точно и быстро и мы ничего не упустили, могли бы вы его чуть сократить или повторить ключевое в короткой форме?")
            return "ok"

        file_id = message["voice"]["file_id"]
        text = transcribe_voice(file_id)
        if not text:
            return "ok"

    elif "text" in message:
        text = message["text"].strip()

    if not text:
        return "ok"

    if text.lower() == "memory_clean":
        conversation_history[user_id] = []
        last_message_time[user_id] = time.time()
        send_message(chat_id, "История очищена. Можем начать заново 😊")
        return "ok"

    if user_id not in conversation_history:
        conversation_history[user_id] = []
        send_message(chat_id, "Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")

    conversation_history[user_id].append({"role": "user", "content": text})
    conversation_history[user_id] = conversation_history[user_id][-50:]
    last_message_time[user_id] = time.time()

    if user_id in pending_timers:
        pending_timers[user_id].cancel()

    timer = threading.Timer(DELAY_SECONDS, process_delayed_reply, args=(user_id, chat_id))
    timer.start()
    pending_timers[user_id] = timer

    return "ok"

# Дополнить оставшуюся часть кода могу сразу, когда скажешь :)
