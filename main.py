import os
import json
import threading
import time
from datetime import datetime

import requests
from flask import Flask, request, render_template_string
import openai
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Flask app
app = Flask(__name__)

# API ключи и настройки
openai.api_key = os.environ.get("OPENAI_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"

ADMIN_CHAT_ID = "-4877024070"
TIMEZONE = pytz.timezone("Asia/Almaty")
conversation_history = {}
last_message_time = {}
pending_timers = {}
DELAY_SECONDS = 10

# Google Sheets
SHEET_ID = "16PtWH2dcR5bIeIQeBxsr8nOePKO7p6LMveKLse1N40s"
if not os.path.exists("credentials.json"):
    creds_env = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_env:
        with open("credentials.json", "w") as f:
            f.write(creds_env)

@app.route("/")
def home():
    return "🤖 WhatsApp бот работает!"

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token and challenge and token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
        return "Ошибка верификации", 403

    data = request.get_json()
    print("📥 Получено сообщение:", json.dumps(data, indent=2, ensure_ascii=False))
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")
        if messages:
            msg = messages[0]
            wa_id = msg["from"]
            text = msg["text"]["body"].strip()
            handle_user_message(wa_id, text)
    except Exception as e:
        print("Ошибка обработки сообщения:", e)
    return "ok", 200

def handle_user_message(user_id, text):
    if text.lower() == "memory_clean":
        conversation_history[user_id] = []
        last_message_time[user_id] = time.time()
        send_message(user_id, "История очищена. Можем начать заново 😊")
        return

    if user_id not in conversation_history:
        conversation_history[user_id] = []
        send_message(user_id, "Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")

    conversation_history[user_id].append({"role": "user", "content": text})
    conversation_history[user_id] = conversation_history[user_id][-50:]
    last_message_time[user_id] = time.time()

    if user_id in pending_timers:
        pending_timers[user_id].cancel()

    timer = threading.Timer(DELAY_SECONDS, process_delayed_reply, args=(user_id,))
    timer.start()
    pending_timers[user_id] = timer

def process_delayed_reply(user_id):
    if time.time() - last_message_time[user_id] >= DELAY_SECONDS:
        reply = generate_gpt_reply(conversation_history[user_id])
        if reply:
            conversation_history[user_id].append({"role": "assistant", "content": reply})
            conversation_history[user_id] = conversation_history[user_id][-50:]
            send_message(user_id, reply)

            # Проверка: если GPT сказал, что начинаем работу
            trigger_phrases = ["начинаем работу", "приступаем", "отправим отрывки", "в течение дня всё будет"]
            triggered = any(phrase in reply.lower() for phrase in trigger_phrases)

            # Проверим, что флаг ещё не установлен
            started_flag = any(msg.get("started") for msg in conversation_history[user_id] if isinstance(msg, dict))

            if triggered and not started_flag:
                # Установим флаг и вызовем notify_admin
                conversation_history[user_id].append({"started": True})
                notify_admin(user_id, conversation_history[user_id])

        pending_timers.pop(user_id, None)

def send_message(to, text, platform="whatsapp"):
    try:
        if platform == "whatsapp":
            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            }
            # Универсальная замена номера с +77 на 87
            if to.startswith("77"):
                to = "787" + to[2:]
                
            print("CORRECT WA_ID: ", to)
            data = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text}
            }
            response = requests.post(WHATSAPP_API_URL, headers=headers, json=data)
            print("Ответ WhatsApp:", response.status_code, response.text)

        elif platform == "telegram":
            TELEGRAM_API_URL = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
            data = {
                "chat_id": to,
                "text": text
            }
            response = requests.post(TELEGRAM_API_URL, json=data)
            print("Ответ Telegram:", response.status_code, response.text)

    except Exception as e:
        print(f"Ошибка отправки ({platform}):", e)



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
    full_history = [system_prompt] + user_history
    try:
        gpt_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=full_history,
            max_tokens=1000,
            temperature=0.9
        )
        return gpt_response.choices[0].message.content.strip()
    except Exception as e:
        print("Ошибка GPT:", e)
        return "Извините, произошла ошибка. Попробуйте ещё раз позже."


def notify_admin(client_chat_id, history):
    try:
        print("🚀 notify_admin активирован")

        # Составляем краткое сообщение с последними 6 сообщениями
        summary = f"🔔 Новый заказ от клиента {client_chat_id}\n\n"
        for h in history[-6:]:
            if isinstance(h, dict) and "role" in h and "content" in h:
                role = "👤" if h["role"] == "user" else "🤖"
                summary += f"{role} {h['content']}\n"

        # Отправляем уведомление в Telegram
        send_message(ADMIN_CHAT_ID, summary.strip(), platform="telegram")

        # Запись в Google Таблицу
        append_order_to_google_sheet(client_chat_id, history)

        # Генерация текста песни
        song_text = generate_song_text(history)
        if song_text:
            send_message(ADMIN_CHAT_ID, f"🎵 Готовый текст песни:\n\n{song_text}", platform="telegram")

    except Exception as e:
        print("Ошибка уведомления оператора:", e)
        

def append_order_to_google_sheet(client_chat_id, history):
    try:
        print("Запись в Google Таблицу...")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        sheet_client = gspread.authorize(creds)
        sheet = sheet_client.open_by_key(SHEET_ID).get_worksheet(0)
        user_msgs = [h['content'] for h in history[-6:] if h['role'] == 'user']
        now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        row = [client_chat_id, now, " / ".join(user_msgs)]
        sheet.append_row(row)
        print("✅ Заказ записан.")
    except Exception as e:
        print("Ошибка записи в таблицу:", e)

def generate_song_text(history):
    try:
        prompt = {
            "role": "system",
            "content": """Вы — профессиональный автор песен. На основе истории клиента напишите текст песни с обозначениями частей: [Verse 1], [Chorus], [Verse 2], [Bridge], [Final]."""
        }
        messages = [h for h in history if h["role"] == "user"]
        result = openai.chat.completions.create(
            model="gpt-4o",
            messages=[prompt] + messages,
            max_tokens=1200,
            temperature=0.85
        )
        return result.choices[0].message.content.strip()
    except Exception as e:
        print("Ошибка генерации песни:", e)
        return None

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset='UTF-8'><title>Админка</title></head>
<body>
<h1>Активные клиенты</h1>
{% for uid, hist in history_dict.items() %}
  <div style='border:1px solid #ccc; padding:10px; margin-bottom:20px;'>
    <h2>Клиент: {{ uid }}</h2>
    <div>
      {% for msg in hist %}
        <p><b>{{ '👤' if msg.role == 'user' else '🤖' }}:</b> {{ msg.content }}</p>
      {% endfor %}
    </div>
  </div>
{% endfor %}
</body>
</html>
"""

@app.route("/admin")
def admin():
    return render_template_string(ADMIN_TEMPLATE, history_dict=conversation_history)
