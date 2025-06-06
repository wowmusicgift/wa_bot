from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
import threading
import time

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Память по номеру
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

    # ⏱ Сохраняем время последнего сообщения
    last_message_time[user_number] = time.time()

    # Если нет истории — приветствие
    if user_number not in conversation_history or not conversation_history[user_number]:
        conversation_history[user_number] = [{"role": "system", "content": "Приветствие отправлено"}]
        reply = MessagingResponse()
        reply.message("Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")
        return str(reply)

    # Если уже запущен таймер — не дублируем
    if user_number in reply_timers and reply_timers[user_number].is_alive():
        return ('', 204)

    # Запускаем отложенный ответ
    timer = threading.Timer(10.0, lambda: delayed_reply(user_number))
    reply_timers[user_number] = timer
    timer.start()

    return ('', 204)

def delayed_reply(user_number):
    # Проверка, прошло ли 10 секунд с последнего сообщения
    if time.time() - last_message_time[user_number] < 10:
        return  # Пользователь ещё пишет — подождём ещё

    history = conversation_history.get(user_number, [])
    incoming_msg = history[-1]["content"] if history else ""

    # Определим цену по номеру
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
Вы — профессиональный автор песен и поздравлений, работающий в WhatsApp. Вы создаёте уникальные тексты для клиентов, которые хотят порадовать близких, но не умеют писать сами.

Вы обращаетесь к клиенту исключительно на “вы”, уважительно, доброжелательно, с теплотой. Вы можете использовать смайлики (1–2 в сообщении) для дружелюбия, особенно в приветствиях или финале.

Ваш стиль — поэтичный, искренний, человечный. Избегайте шаблонов. Вы ведёте живой диалог, как будто вы реальный творец, а не бот.

Вы не давите вопросами. Спрашиваете только нужное:
– Какой повод? 🎉
– Кому это будет? 💌
– Что именно нужно: песня, стих, поздравление? 🎶
– Какие чувства хочется передать? ❤️
– Есть ли особенные слова или истории? 📝

Поддержите клиента, если он не уверен. Помогите определиться.

Если клиент спрашивает про стоимость, вы корректно и уважительно отвечаете:
- если номер начинается с +7 (Казахстан): “Стоимость создания песни — 6490 тенге 🇰🇿”
- если номер начинается с +992 (Таджикистан): “Стоимость создания песни — 169 сомони 🇹🇯”
- иначе: “Стоимость уточняется в зависимости от страны 🌍”

Если вас спрашивают, сколько ждать — сообщите, что песня создаётся в течение дня.

Ваши ответы — живые, вдохновляющие, не сухие. Не паникуйте, если клиент молчит — подождите или напомните вежливо позже.
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

        # Отправляем через Twilio
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

        # Обновляем историю
        conversation_history[user_number] = (history + [
            {"role": "assistant", "content": reply_text}
        ])[-6:]

    except Exception as e:
        print("Ошибка при отправке:", e)
