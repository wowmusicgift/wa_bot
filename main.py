from flask import Flask, request
import requests
from openai import OpenAI
import os
import threading
import time

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

conversation_history = {}
last_message_time = {}
pending_timers = {}

DELAY_SECONDS = 10

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
    text = message.get("text", "").strip()

    if not text:
        return "ok"

    user_id = str(chat_id)

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

    # отменяем предыдущий таймер, если он был
    if user_id in pending_timers:
        pending_timers[user_id].cancel()

    # запускаем новый таймер
    timer = threading.Timer(DELAY_SECONDS, process_delayed_reply, args=(user_id, chat_id))
    timer.start()
    pending_timers[user_id] = timer

    return "ok"

def process_delayed_reply(user_id, chat_id):
    # Проверяем, прошло ли 10 секунд с последнего сообщения
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

Вы не задаёте лишних вопросов. Если клиент уже указал, кому будет поздравление или на какой повод — не повторяйте этот вопрос снова.

Уточняйте:
– Какой повод? 🎉
– Кому именно? 💌
– Что именно нужно: песня, стих, поздравление? 🎶
– Какие чувства хочется передать? ❤️
– Есть ли особенные слова или моменты? 📝

Если клиент интересуется ценой — сначала уточните, из какой он страны (например: “Подскажите, пожалуйста, вы из Казахстана или Таджикистана? Это нужно для расчёта стоимости 😊”). Затем сообщите:
– Для Казахстана 🇰🇿 цена — 6490 тенге;
– Для Таджикистана 🇹🇯 — 169 сомони.

Если спрашивают, когда будет готово — сообщите: “Мы создаём песню в течение дня 🎶”

Если клиент долго не отвечает — можно вежливо напомнить, не навязчиво.

Вы не выдаёте себя за ИИ — вы настоящая команда авторов.
"""
    }

    full_history = [system_prompt] + user_history

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

def send_message(chat_id, text):
    try:
        response = requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": text
        })
        print("📨 Ответ Telegram:", response.status_code, response.text)
    except Exception as e:
        print("❌ Ошибка отправки в Telegram:", e)
