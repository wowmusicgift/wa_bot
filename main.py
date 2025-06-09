from flask import Flask, request
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Бот работает!"

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if data:
        print("📦 Входящее сообщение:")
        print(data)

        if "message" in data:
            chat_info = data["message"].get("chat", {})
            chat_id = chat_info.get("id")
            title = chat_info.get("title", "—")
            print(f"🔍 chat_id: {chat_id}, title: {title}")

    return "ok"
