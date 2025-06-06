from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
import threading
import time

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Память по пользователям
conversation_history = {}
last_message_time = {}
reply_timers = {}

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!"

@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    user_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()

    if not incoming_msg:
        return str(MessagingResponse().message("Здравствуйте! Напишите что-нибудь 🎵"))

    # Сохраняем время последнего сообщения
    last_message_time[user_number] = time.time()

    # Сохраняем сообщение в историю
    if user_number not in conversation_history:
        conversation_history[user_number] = []

    conversation_history[user_number].append({"role": "user", "content": incoming_msg})
    conversation_history[user_number] = conversation_history[user_number][-50:]  # до 50 реплик

    # Приветствие только один раз
    if len([m for m in conversation_history[user_number] if m["role"] == "assistant"]) == 0:
        reply = MessagingResponse()
        reply.message("Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")
        return str(reply)

    # Если уже есть активный таймер — не запускаем второй
    if user_number in reply_timers and reply_timers[user_number].is_alive():
        return ('', 204)

    # Запуск отложенного ответа через 10 секунд
    timer = threading.Timer(10.0, lambda: delayed_reply(user_number))
    reply_timers[user_number] = timer
    timer.start()

    return ('', 204)

def delayed_reply(user_number):
    # Если клиент всё ещё печатает — не отвечаем
    if time.time() - last_message_time[user_number] < 10:
        return

    history = conversation_history.get(user_number, [])

    # Определяем цену по номеру
    if user_number.startswith("whatsapp:+7"):
        price_info = "Стоимость создания песни — 6490 тенге 🇰🇿"
    elif user_number.startswith("whatsapp:+992"):
        price_info = "Стоимость создания песни — 169 сомони 🇹🇯"
    else:
        price_info = "Стоимость уточняется в зависимости от страны 🌍"

    # Системный промт
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

        # Отправка через Twilio API
        from twilio.rest import Client as TwilioClient
        twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
        whatsapp_from = os.environ.get("TWILIO_WHATSAPP_NUMBER")

        twilio = TwilioClient(twilio_sid, twilio_token)
        twilio.messages.create(
            from_=whatsapp_from,
            to=user_number,
            body=reply_text
        )

        # Сохраняем ответ в историю
        conversation_history[user_number].append({"role": "assistant", "content": reply_text})
        conversation_history[user_number] = conversation_history[user_number][-50:]

    except Exception as e:
        print("Ошибка при отправке:", e)
