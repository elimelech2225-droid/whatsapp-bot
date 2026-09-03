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
PRICES = {
    ("ירושלים", "תל אביב"): 240,
    ("בית שמש", "תל אביב"): 220,
    ("ירושלים", "ראשון לציון"): 200,
    ("ירושלים", "בת ים"): 200,
    ("ירושלים", "נס ציונה"): 200,
    ("ירושלים", "עמנואל"): 350,
    ("ירושלים", "נתניה"): 350,
    ("ירושלים", "בית שמש"): 150,
    ("ירושלים", "ביתר"): 120,
    ("ירושלים", "ראש העין"): 220,
    ("ירושלים", "אלעד"): 220,
    ("ירושלים", "אשקלון"): 300,
    ("ירושלים", "אשדוד"): 220,
    ("בית שמש", "אשקלון"): 250,
}
def parse_route(text):
    text = text.strip()

    for word in ["משלוח", "צריך", "צריכה", "הזמנה", "דחוף", "בבקשה"]:
        text = text.replace(word, " ")

    text = text.replace(",", " ")
    text = " ".join(text.split())

    cities = [
        "ירושלים",
        "תל אביב",
        "בית שמש",
        "ראשון לציון",
        "בת ים",
        "נס ציונה",
        "עמנואל",
        "נתניה",
        "ביתר",
        "ראש העין",
        "אלעד",
        "אשקלון",
        "אשדוד",
    ]

    found = []

    for city in cities:
        if city in text:
            found.append((text.find(city), city))

    found.sort()

    if len(found) >= 2:
        return found[0][1], found[1][1]

    return None, None
@app.post("/webhook")
def receive_webhook():
    data = request.get_json(silent=True) or {}

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]

        if message.get("type") == "text":
            text = message["text"]["body"].strip()
        if text.lower() in ["היי", "הי", "שלום", "אהלן", "הלו"]:
            send_message(
                sender,
                "היי 😊 ברוכים הבאים!\nמאיפה לאיפה תרצה את המשלוח?\nלדוגמה: ירושלים לתל אביב"
            )
            return "OK", 200
        origin, destination = parse_route(text)

        if origin and destination:       
                origin = origin.strip()
                destination = destination.strip()

                price = PRICES.get((origin, destination)) or PRICES.get((destination, origin))
                price_text = f"{price} ₪" if price else "עדיין אין מחיר למסלול הזה"
        
                send_message(
            sender,
            f"קיבלתי בקשת משלוח:\n"
            f"מוצא: {origin}\n"
            f"יעד: {destination}\n"
            f"מחיר: {price_text}"
        )    
        else:
                send_message(
                    sender,
                    "כדי להזמין משלוח, רשום למשל:\nמשלוח מירושלים לתל אביב"
                )

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

    response = requests.post(url, headers=headers, json=payload, timeout=20)
    print("META STATUS:", response.status_code)
    print("META RESPONSE:", response.text)
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
