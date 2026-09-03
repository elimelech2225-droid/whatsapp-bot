from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")


@app.route("/", methods=["GET"])
def home():
    return "WhatsApp bot is running", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone = message["from"]
        text = message["text"]["body"].strip()

        if text.lower() in ["hi", "היי", "הי", "שלום"]:
            send_message(
                phone,
                "היי 👋\n"
                "ברוכים הבאים ל א.א שליחויות 🚚\n\n"
                "מאיפה לאיפה תרצה לבצע את המשלוח?\n"
                "לדוגמה: ירושלים לתל אביב"
            )
        else:
            prices = {
                "ירושלים תל אביב": 240,
                "בית שמש תל אביב": 220,
                "ירושלים עמנואל": 350,
                "בית שמש עמנואל": 350,
                "עמנואל בני ברק": 250,
                "ראש העין ירושלים": 220,
                "ירושלים אלעד": 220,
                "ירושלים בני ברק": 220,
                "ירושלים ראשון לציון": 200,
                "ירושלים נס ציונה": 200,
                "ירושלים אשקלון": 300,
                "ירושלים רמת גן": 220,
                "ירושלים נתניה": 350,
                "ירושלים חדרה": 400,
                "ירושלים בית שמש": 150,
                "ירושלים ביתר": 120
            }

            route = text.replace("לתל אביב", "תל אביב").strip()
            price = prices.get(route)

            if price:
                send_message(
                    phone,
                    f"קיבלתי את המסלול שלך 🚚\n\n"
                    f"📍 המסלול: {text}\n"
                    f"💰 מחיר המשלוח: {price} ₪\n\n"
                    f"האם תרצה שנמצא עבורך שליח לביצוע המשלוח?\n"
                    f"השב כן ונתחיל לחפש עבורך שליח מיד."
                )
            else:
                send_message(
                    phone,
                    "לא מצאתי מחיר למסלול הזה במחירון.\n"
                    "נסה לרשום למשל: ירושלים לתל אביב"
                )           
           
    return "OK", 200


def send_message(phone, text):
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": text
        }
    }

    requests.post(url, headers=headers, json=payload, timeout=10)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
