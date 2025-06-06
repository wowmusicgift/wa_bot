from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os

app = Flask(__name__)

# Места для хранения контекста
user_context = {}

@app.route("/", methods=["GET"])
def index():
    return "Сервер работает!"

@app.route("/webhook", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    response = MessagingResponse()
    msg = response.message()

    # Проверка контекста для клиента
    if sender not in user_context:
        user_context[sender] = {'stage': 'start', 'data': {}}

    # Получение текущего состояния клиента
    user_data = user_context[sender]

    if incoming_msg:
        try:
            if user_data['stage'] == 'start':
                # Начало разговора, задаем наводящие вопросы
                reply_text = "Здравствуйте! 😊 Чем можем помочь? Например, хотите поздравить кого-то?"
                user_data['stage'] = 'collect_info'  # Переход к следующей стадии
            elif user_data['stage'] == 'collect_info':
                # Собираем информацию
                if 'name' not in user_data['data']:
                    user_data['data']['name'] = incoming_msg
                    reply_text = "Отлично! Как зовут того, кого поздравляем?"
                elif 'recipient_name' not in user_data['data']:
                    user_data['data']['recipient_name'] = incoming_msg
                    reply_text = "Отлично! Расскажите немного о человеке: например, когда вы познакомились?"
                elif 'story' not in user_data['data']:
                    user_data['data']['story'] = incoming_msg
                    reply_text = "Хорошо! Какие пожелания хотите передать? 😊"
                elif 'wishes' not in user_data['data']:
                    user_data['data']['wishes'] = incoming_msg
                    reply_text = "Спасибо! Мы начнем работать над песней и отправим вам отрывки."
                    user_data['stage'] = 'waiting_payment'  # Переход к стадии ожидания оплаты
            elif user_data['stage'] == 'waiting_payment':
                # Проверка оплаты
                reply_text = "Пожалуйста, подтвердите оплату, и мы начнем работать над песней."
            else:
                reply_text = "Я не понял ваш запрос. Пожалуйста, уточните."

            msg.body(reply_text)

        except Exception as e:
            msg.body("Ошибка: " + str(e))

    else:
        msg.body("Привет! Напишите мне что-нибудь — я сгенерирую ответ :)")

    return str(response)
