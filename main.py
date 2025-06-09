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
ADMIN_CHAT_ID = -1002351934678  # ID группы
TOPIC_ID = 21753  # ID темы форума

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

    if chat_type != "private":
        return "ok"

    user_id = str(chat_id)
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

    timer = threading.Timer(DELAY_SECONDS, process_delayed_reply, args=(user_id, chat_id))
    timer.start()
    pending_timers[user_id] = timer

    return "ok"

def is_late_evening_or_night():
    now = datetime.now(TIMEZONE)
    return now.hour >= 22 or now.hour < 8

def process_delayed_reply(user_id, chat_id):
    if time.time() - last_message_time[user_id] >= DELAY_SECONDS:
        reply = generate_gpt_reply(conversation_history[user_id])
        if reply:
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            conversation_history[user_id] = conversation_history[user_id][-50:]
            send_message(chat_id, reply)
            if "мы начинаем работу" in reply.lower() or "начинаем работу" in reply.lower():
                notify_admin(chat_id, conversation_history[user_id])
        pending_timers.pop(user_id, None)

def generate_gpt_reply(user_history):
    system_prompt = {
        "role": "system",
        "content": """
Вы — команда профессиональных авторов песен и поздравлений. Общаетесь в Telegram от лица команды: “мы с радостью создадим…”, “наша команда поможет…”. Обращаетесь к клиенту на “вы”, доброжелательно, с уважением и лёгкими смайликами 😊
... (оставьте как есть, обрезал для краткости)
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
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=full_history,
            max_tokens=1000,
            temperature=0.9
        )
        return gpt_response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Ошибка GPT:", e)
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
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        return transcription.strip()

    except Exception as e:
        print("❌ Ошибка распознавания голоса:", e)
        return None

def send_message(chat_id, text, thread_id=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        print("📨 Ответ Telegram:", response.status_code, response.text)
    except Exception as e:
        print("❌ Ошибка отправки в Telegram:", e)

def notify_admin(client_chat_id, history):
    try:
        summary = f"🔔 Новый заказ от клиента {client_chat_id}\n\nПоследние сообщения:\n"
        for h in history[-6:]:
            role = "👤" if h['role'] == "user" else "🧐"
            summary += f"{role} {h['content']}\n"

        send_message(ADMIN_CHAT_ID, summary.strip(), thread_id=TOPIC_ID)
    except Exception as e:
        print("❌ Ошибка уведомления оператора:", e)
