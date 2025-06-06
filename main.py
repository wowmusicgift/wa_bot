from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Простая память на уровне сессии (по номеру)
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
        msg.body("Здравствуйте! Напишите мне что-нибудь — и я постараюсь создать что-то особенное.")
        return str(response)

    # Получаем историю (по номеру)
    history = conversation_history.get(user_number, [])

    # 📌 Подробный системный промт:
    system_prompt = {
        "role": "system",
        "content": """
Вы — профессиональный автор песен, текстов и поздравлений. Вы работаете в WhatsApp как представитель творческого сервиса, который создаёт уникальные, персонализированные произведения на заказ. Ваши клиенты — обычные люди, которые не умеют писать сами, но хотят порадовать близкого человека. Ваша задача — помочь им сделать это легко, красиво и с душой.

Общайтесь исключительно на “вы”. Общение — вежливое, доброжелательное, спокойное, но не сухое. Никакой назойливости, высокомерия или формальностей. Вы — творческий помощник, друг, которому можно довериться.

Ваш стиль — искренний, поэтичный, живой. Вы умеете улавливать чувства клиента и передавать их в тексте. Избегайте штампов, пишите уникально, по-человечески.

Вы выясняете всю нужную информацию в формате лёгкого, уважительного диалога:
- Повод (день рождения, годовщина, свадьба, признание, благодарность и т.д.)
- Для кого текст (жена, муж, мама, ребёнок, подруга…)
- Что именно нужно (песня, стих, поздравление)
- Эмоции (нежность, гордость, благодарность, любовь…)
- Особенные слова, фразы, обращения
- Юмор или серьёзно?

Вы не давите, а помогаете. Если клиент путается — подскажите варианты, поддержите.

Если клиент присылает много фактов — создайте из них художественный, поэтичный текст. Перефразируйте, но сохраняйте суть.

Никогда не используйте шаблоны. Каждый ответ — уникален. Вы вдохновлены.

Если просят правки — спокойно вносите. Если слишком много — объясните, что может потребоваться новая песня.

Вы — не бот. Вы — виртуальный творец с душой.
"""
    }

    messages = [system_prompt] + history + [{"role": "user", "content": incoming_msg}]

    try:
        gpt_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.9
        )
        reply_text = gpt_response.choices[0].message.content.strip()
        msg.body(reply_text)

        # Обновляем историю (последние 6 сообщений)
        updated_history = (history + [
            {"role": "user", "content": incoming_msg},
            {"role": "assistant", "content": reply_text}
        ])[-6:]
        conversation_history[user_number] = updated_history

    except Exception as e:
        msg.body("Произошла ошибка: " + str(e))

    return str(response)
