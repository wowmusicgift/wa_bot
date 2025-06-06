from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os
import time

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Память по пользователю
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

    # Получаем историю по номеру
    history = conversation_history.get(user_number, [])

    # 🏷️ Определим страну и цену
    if user_number.startswith('whatsapp:+7'):
        price_info = "Стоимость создания песни — 6490 тенге 🇰🇿"
    elif user_number.startswith('whatsapp:+992'):
        price_info = "Стоимость создания песни — 169 сомони 🇹🇯"
    else:
        price_info = "Стоимость уточняется в зависимости от страны 🌍"

    # ⏳ Если это первое сообщение — приветствие
    if not history:
        msg.body(f"Добрый день! ☺️ Чем можем помочь? Хотите кого-то поздравить? 😁\n\n{price_info}")
        # Продолжим только на второе сообщение
        conversation_history[user_number] = []
        return str(response)

    # 🧠 Системный промт
    system_prompt = {
        "role": "system",
        "content": """
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

Если клиент просит цену — укажите: 6490 тенге 🇰🇿 или 169 сомони 🇹🇯. Если страна другая — скажите, что цена уточняется.

Ваши ответы — живые, вдохновляющие, не сухие. Не паникуйте, если клиент молчит — подождите или напомните вежливо позже.
"""
    }

    # Формируем сообщения для GPT
    messages = [system_prompt] + history + [{"role": "user", "content": incoming_msg}]

    try:
        # ⏱️ Можно имитировать "размышление"
        time.sleep(1.5)

        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.9
        )
        reply_text = gpt_response.choices[0].message.content.strip()
        msg.body(reply_text)

        # Обновляем историю
        updated_history = (history + [
            {"role": "user", "content": incoming_msg},
            {"role": "assistant", "content": reply_text}
        ])[-6:]
        conversation_history[user_number] = updated_history

    except Exception as e:
        msg.body("Произошла ошибка: " + str(e))

    return str(response)
