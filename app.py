import os
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


@app.get("/")
def home():
    return "WhatsApp Bot is running", 200


@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge or "", 200

    return "Verification failed", 403


@app.post("/webhook")
def receive_webhook():
    data = request.get_json(silent=True) or {}

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]

        if message.get("type") == "text":
            text = message["text"]["body"]
            send_message(sender, f"קיבלתי את ההודעה שלך: {text}")
    except (KeyError, IndexError, TypeError):
        pass

    return "OK", 200


def send_message(to, text):
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    requests.post(url, headers=headers, json=payload, timeout=20)

@app.route("/privacy", methods=["GET"])
def privacy():
    return """
    <h1>Privacy Policy</h1>
    <p>AB deliverise bot uses WhatsApp to receive and respond to customer messages.</p>
    <p>We do not sell or share users' personal information with third parties.</p>
    <p>Information is used only to provide the messaging service requested by the user.</p>
    <p>For privacy questions, please contact the business directly.</p>
    """, 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
