from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!"

@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    response = MessagingResponse()
    msg = response.message()

    if incoming_msg:
        try:
            gpt_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": incoming_msg}],
                max_tokens=500,
                temperature=0.7
            )
            reply_text = gpt_response.choices[0].message.content
            msg.body(reply_text)
        except Exception as e:
            msg.body("Ошибка: " + str(e))
    else:
        msg.body("Привет! Напиши мне что-нибудь — я сгенерирую ответ :)")

    return str(response)
