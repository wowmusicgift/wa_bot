import os
import json
import threading
import time
from datetime import datetime

import requests
from flask import Flask, request
import openai
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Создаем credentials.json из переменной окружения
if not os.path.exists("credentials.json"):
    creds_env = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_env:
        with open("credentials.json", "w") as f:
            f.write(creds_env)

# Устанавливаем ключ OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
ADMIN_CHAT_ID = "-1002351934678"
ADMIN_TOPIC_ID = 21753

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
    chat_type = message["chat"].get("type")

    if chat_type != "private":
        return "ok"

    user_id = str(chat_id)
    username = message["from"].get("username", "—")
    text = ""

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

    timer = threading.Timer(DELAY_SECONDS, process_delayed_reply, args=(user_id, chat_id, username))
    timer.start()
    pending_timers[user_id] = timer

    return "ok"


def is_late_evening_or_night():
    now = datetime.now(TIMEZONE)
    return now.hour >= 22 or now.hour < 8


def process_delayed_reply(user_id, chat_id, username):
    if time.time() - last_message_time[user_id] >= DELAY_SECONDS:
        reply = generate_gpt_reply(conversation_history[user_id])
        if reply:
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            conversation_history[user_id] = conversation_history[user_id][-50:]
            send_message(chat_id, reply)
            if "мы начинаем работу" in reply.lower() or "начинаем работу" in reply.lower():
                notify_admin(chat_id, username, conversation_history[user_id])
        pending_timers.pop(user_id, None)


def generate_gpt_reply(user_history):
    system_prompt = {
        "role": "system",
        "content": """
Вы — команда профессиональных авторов песен и поздравлений. Общаетесь в Telegram от лица команды: “мы с радостью создадим…”, “наша команда поможет…”. Обращаетесь к клиенту на “вы”, доброжелательно, с уважением и лёгкими смайликами 😊

Ваш стиль — живой, человечный. Пишите просто и по делу, без лишних шаблонов. Не перегружайте клиента — сообщения должны быть короткими и понятными.

📌 В первом сообщении:
– приветствуйте клиента и расскажите, как проходит работа;
– укажите: цена — 6490 тенге 🇰🇿 или 169 сомони 🇹🇯;
– создаются 2 варианта песни, отправляются отрывки;
– оплата — только после прослушивания, если всё устраивает;
– если клиент написал ночью — скажите, что работа будет готова в рабочее время, но не позже следующего дня.

💬 Во втором сообщении переходите к уточняющим вопросам.

⚠️ Важно: ни в коем случае нельзя сообщать клиенту о начале работы, если он не сообщил имя того, кому посвящается песня, или как можно назвать человека (если песня посвящается человеку), или прямо не сказал о том, что никак называть его или её в песне не нужно!

⚠️ Важно: ни в коем случае нельзя сообщать клиенту о начале работы, если он не сообщил повод для поздравления, создания песни или прямо не сказал о том, что песня без повода (простое пожелание или вообще посвящена не человеку)!

Если уместно — уточните, как клиент ласково называет этого человека. Если песня для близких, можно вежливо спросить, хочет ли клиент, чтобы в тексте упоминались его имя или имена детей.

Если информации мало — уточните, не хочет ли клиент что-то добавить или предпочитает довериться вам.

Перед тем как сказать, что работа началась — задайте ещё 1–2 коротких вопроса. В конце обязательно спросите: “Может быть, вы хотите ещё что-то добавить?”

Когда клиент ответил, что можно начинать — скажите, что начинаете работу и отправите отрывки в течение дня. Если он писал ночью — напомните, что всё будет не позже следующего дня.

Если клиент интересуется ценой — сначала уточните страну. Потом сообщите:
– 🇰🇿 6490 тенге
– 🇹🇯 169 сомони

Если долго нет ответа — можно вежливо напомнить.  
Вы не ИИ — вы настоящая команда.
"""
    }

    full_history = [system_prompt]

    if is_late_evening_or_night():
        full_history.append({
            "role": "system",
            "content": "Клиент написал ночью. Напомните, что песня будет готова в рабочее время, не позже следующего дня."
        })

    full_history += user_history

    try:
        gpt_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=full_history,
            max_tokens=1000,
            temperature=0.9
        )
        return gpt_response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ GPT error:", e)
        return "Извините, произошла ошибка. Попробуйте ещё раз позже."


def transcribe_voice(file_id):
    try:
        file_info = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        ).json()
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

        response = requests.get(file_url)
        temp_path = "/tmp/voice.ogg"
        with open(temp_path, "wb") as f:
            f.write(response.content)

        with open(temp_path, "rb") as audio_file:
            transcription = openai.Audio.transcribe("whisper-1", audio_file)
        return transcription["text"].strip()

    except Exception as e:
        print("❌ Ошибка распознавания голоса:", e)
        return None


def send_message(chat_id, text, thread_id=None):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        if thread_id:
            payload["message_thread_id"] = thread_id
        response = requests.post(TELEGRAM_API_URL, json=payload)
        print("📨 Ответ Telegram:", response.status_code, response.text)
    except Exception as e:
        print("❌ Ошибка отправки в Telegram:", e)


def notify_admin(client_chat_id, username, history):
    try:
        summary = f"🔔 Новый заказ от клиента {client_chat_id} (@{username})\n\nПоследние сообщения:\n"
        for h in history[-6:]:
            role = "👤" if h['role'] == "user" else "🤖"
            summary += f"{role} {h['content']}\n"
        send_message(ADMIN_CHAT_ID, summary.strip(), thread_id=ADMIN_TOPIC_ID)
        append_order_to_google_sheet(client_chat_id, username, history)
    except Exception as e:
        print("❌ Ошибка уведомления оператора:", e)


def append_order_to_google_sheet(client_chat_id, username, history):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)

        sheet = client.open("Telegram Заказы").worksheet("Лист1")
        last_msgs = [h['content'] for h in history[-6:] if h['role'] == 'user']
        now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

        row = [str(client_chat_id), f"@{username}", now, " / ".join(last_msgs)]
        sheet.append_row(row)
        print("✅ Заказ записан в Google Таблицу.")
    except Exception as e:
        print("❌ Ошибка записи в Google Таблицу:", e)
