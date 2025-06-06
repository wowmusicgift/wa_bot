from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
import threading
import time

from twilio.rest import Client as TwilioClient

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

conversation_history = {}
last_message_time = {}
reply_timers = {}
user_greeted = {}

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!"

@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    user_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()

    if not incoming_msg:
        return str(MessagingResponse().message("Пожалуйста, напишите что-нибудь 😊"))

    # Очистка памяти
    if incoming_msg.lower() == "memory_clean":
        conversation_history[user_number] = []
        user_greeted[user_number] = False
        reply = MessagingResponse()
        reply.message("История диалога очищена. Можем начать заново 😊")
        return str(reply)

    last_message_time[user_number] = time.time()

    if user_number not in conversation_history:
        conversation_history[user_number] = []

    # Приветствие, если не отправлено
    if not user_greeted.get(user_number, False):
        user_greeted[user_number] = True
        reply = MessagingResponse()
        reply.message("Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")
        return str(reply)

    # Сохраняем входящее сообщение
    conversation_history[user_number].append({"role": "user", "content": incoming_msg})
    conversation_history[user_number] = conversation_history[user_number][-50:]

    # Запускаем таймер, если он не активен
    if user_number not in reply_timers or not reply_timers[user_number].is_alive():
        timer = threading.Timer(10.0, lambda: delayed_reply(user_number))
        reply_timers[user_number] = timer
        timer.start()

    return ('', 204)

def delayed_reply(user_number):
    if time.time() - last_message_time[user_number] < 10:
        return

    history = conversation_history.get(user_number, [])

    # Определение цены
    if user_number.startswith("whatsapp:+7"):
        price_info = "Стоимость создания песни — 6490 тенге 🇰🇿"
    elif user_number.startswith("whatsapp:+992"):
        price_info = "Стоимость создания песни — 169 сомони 🇹🇯"
    else:
        price_info = "Стоимость уточняется в зависимости от страны 🌍"

    system_prompt = {
        "role": "system",
        "content": f"""
Вы — команда профессиональных авторов песен и поздравлений. Вы помогаете людям создавать уникальные тексты по их истории. Общение ведёте в WhatsApp.

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

Если клиент спрашивает про цену — отвечайте:
- Казахстан (+7): {price_info}
- Таджикистан (+992): {price_info}
- Другие страны: “Стоимость уточняется в зависимости от страны 🌍”

Если спрашивают, когда будет готово — сообщите: “Мы создаём песню в течение дня 🎶”

Если клиент долго не отвечает — можно вежливо напомнить, не навязчиво.

Вы не выдаёте себя за ИИ — вы настоящая команда авторов.
"""
    }

    messages = [system_prompt] + history

    try:
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.9
        )

        reply_text = gpt_response.choices[0].message.content.strip()

        twilio = TwilioClient(
            os.environ.get("TWILIO_ACCOUNT_SID"),
            os.environ.get("TWILIO_AUTH_TOKEN")
        )

        twilio.messages.create(
            from_=os.environ.get("TWILIO_WHATSAPP_NUMBER"),
            to=user_number,
            body=reply_text
        )

        # Сохраняем ответ
        conversation_history[user_number].append({"role": "assistant", "content": reply_text})
        conversation_history[user_number] = conversation_history[user_number][-50:]

    except Exception as e:
        print("❌ Ошибка при ответе:", e)
