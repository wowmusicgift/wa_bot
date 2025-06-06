from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Простая память: история диалога (можно заменить на базу позже)
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
        msg.body("Здравствуйте! Напишите мне что-нибудь — я постараюсь ответить творчески.")
        return str(response)

    # Получаем историю для пользователя
    history = conversation_history.get(user_number, [])
    
    # Формируем сообщения для GPT
    messages = [
        {"role": "system", "content": (
            "Вы — креативный, поэтичный AI-автор, создающий песни, поздравления и тексты. "
            "Вы обращаетесь к пользователю исключительно на 'вы'. "
            "Ваш стиль — душевный, эмоциональный, искренний, вы пишете красиво и с уважением."
        )}
    ] + history + [{"role": "user", "content": incoming_msg}]

    try:
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.9
        )
        reply_text = gpt_response.choices[0].message.content.strip()
        msg.body(reply_text)

        # Обновляем память (максимум 6 последних сообщений)
        updated_history = (history + [{"role": "user", "content": incoming_msg},
                                      {"role": "assistant", "content": reply_text}])[-6:]
        conversation_history[user_number] = updated_history

    except Exception as e:
        msg.body("Произошла ошибка: " + str(e))

    return str(response)
