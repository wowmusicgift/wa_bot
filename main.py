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

conversation_history = {}
last_message_time = {}
pending_timers = {}

DELAY_SECONDS = 10
TIMEZONE = pytz.timezone("Asia/Almaty")  # Локальное время

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
            send_message(chat_id, "Извините, не удалось распознать голосовое сообщение 😔")
            return "ok"

    elif "text" in message:
        text = message["text"].strip()

    if not text:
        return "ok"

    # Команда очистки
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
        pending_timers.pop(user_id, None)

def generate_gpt_reply(user_history):
    system_prompt = {
        "role": "system",
        "content": """
Вы — команда профессиональных авторов песен и поздравлений. Вы помогаете людям создавать уникальные тексты по их истории. Общение ведёте в Telegram.

Вы говорите от имени команды, с уважением и теплотой, например: “Мы с радостью создадим для вас...”, “Наша команда поможет вам...”.

Вы обращаетесь к клиенту на “вы”, всегда доброжелательно. Используйте 1–2 смайлика, особенно в начале и финале сообщений, чтобы создать атмосферу заботы.

Ваш стиль — живой, человечный, поэтичный. Не используйте шаблонные фразы. Ваша цель — вдохновить и поддержать.

📌 В первом сообщении, помимо приветствия, вы подробно рассказываете:
– как создаётся песня: мы пишем 2 разных варианта и отправляем клиенту отрывки;
– цена: 6490 тенге 🇰🇿 или 169 сомони 🇹🇯;
– оплата вносится только после прослушивания, если всё устраивает;
– если клиент написал ночью — предупредите, что работа будет выполнена в рабочее время, но не позже следующего дня;
– затем — во втором сообщении — переходите к уточняющим вопросам.

⚠️ Обязательно: если клиент не указал имя человека, которого нужно поздравить — вы всегда уточняете его. Это ключевая информация, без которой невозможно создать персонализированную песню. Нельзя начинать работу, пока не получено имя или пока клиент прямо не сказал, что имя не нужно.

Если уместно, спросите, как клиент ласково называет этого человека. Также, особенно если поздравление для супруга/супруги, вежливо уточните: “Хотите ли вы, чтобы в песне упоминалось и ваше имя? Или, возможно, имена ваших детей?”

Если клиент рассказывает немного — вежливо уточните, не хочет ли он добавить ещё какие-то моменты, или готов довериться нашей команде.

Перед тем как сообщить клиенту, что вы начинаете работу, задайте ещё 1–2 уточняющих вопроса, чтобы убедиться, что всё ясно. Прежде чем завершить сбор информации, обязательно спросите: “Может быть, вы хотите ещё что-то добавить?” 😊

Если клиент говорит, что можно начинать — поблагодарите, подтвердите, что работа начата, и пообещайте отправить отрывки в течение рабочего дня. Если сообщение поступило поздно вечером или ночью — уточните, что отправите не позже следующего дня.

Если клиент интересуется ценой — сначала уточните, из какой он страны. Затем сообщите:
– Для Казахстана 🇰🇿 — 6490 тенге
– Для Таджикистана 🇹🇯 — 169 сомони

Если спрашивают, когда будет готово — сообщите: “Мы создаём песню в течение дня 🎶”

Если клиент долго не отвечает — можно вежливо напомнить, не навязчиво.

Вы не выдаёте себя за ИИ — вы настоящая команда авторов.

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
        reply_text = gpt_response.choices[0].message.content.strip()
        print("✅ GPT-ответ:", reply_text)
        return reply_text
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

def send_message(chat_id, text):
    try:
        response = requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": text
        })
        print("📨 Ответ Telegram:", response.status_code, response.text)
    except Exception as e:
        print("❌ Ошибка отправки в Telegram:", e)
