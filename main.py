from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
import time

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Память по номеру
conversation_history = {}

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!"

@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    user_number = request.values.get('From', '')
    incoming_msg = request.values.get('Body', '').strip()
    response = MessagingResponse()
    msg = response.message()

    if not incoming_msg:
        msg.body("Здравствуйте! Напишите мне что-нибудь — и я постараюсь помочь 🎵")
        return str(response)

    # Определим страну по номеру
    if user_number.startswith('whatsapp:+7'):
        price_info = "Стоимость создания песни — 6490 тенге 🇰🇿"
    elif user_number.startswith('whatsapp:+992'):
        price_info = "Стоимость создания песни — 169 сомони 🇹🇯"
    else:
        price_info = "Стоимость уточняется в зависимости от страны 🌍"

    # История сообщений
    history = conversation_history.get(user_number, [])

    # Приветствие только один раз
    if not history:
        msg.body("Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁")
        conversation_history[user_number] = [{"role": "system", "content": "Приветствие отправлено"}]
        return str(response)

    # Системный промт с логикой цены
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

Если клиент спрашивает про стоимость или пишет что-то вроде “сколько стоит” или “цена”, вы корректно и уважительно отвечаете:
- если номер начинается с +7 (Казахстан) — скажите: “Стоимость создания песни — 6490 тенге 🇰🇿”
- если номер начинается с +992 (Таджикистан) — скажите: “Стоимость создания песни — 169 сомони 🇹🇯”
- если номер другой — скажите: “Стоимость уточняется в зависимости от страны 🌍”

Вы не предлагаете прайс заранее, только если вас об этом спросят.

Ваши ответы — живые, вдохновляющие, не сухие. Не паникуйте, если клиент молчит — подождите или напомните вежливо позже.
"""
    }

    messages = [system_prompt] + history + [{"role": "user", "content": incoming_msg}]

    try:
        time.sleep(1.5)  # Небольшая пауза перед ответом

        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.9
        )
        reply_text = gpt_response.choices[0].message.content.strip()
        msg.body(reply_text)

        updated_history = (history + [
            {"role": "user", "content": incoming_msg},
            {"role": "assistant", "content": reply_text}
        ])[-6:]  # Ограничиваем длину истории
        conversation_history[user_number] = updated_history

    except Exception as e:
        msg.body("Произошла ошибка: " + str(e))

    return str(response)
