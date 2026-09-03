from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")


# =========================
# מחירון
# =========================

PRICES = {
    ("ירושלים", "תל אביב"): 240,
    ("בית שמש", "תל אביב"): 220,
    ("ירושלים", "עמנואל"): 350,
    ("בית שמש", "עמנואל"): 350,
    ("עמנואל", "בני ברק"): 250,
    ("ראש העין", "ירושלים"): 220,
    ("ירושלים", "אלעד"): 220,
    ("ירושלים", "בני ברק"): 220,
    ("ירושלים", "ראשון לציון"): 200,
    ("ירושלים", "נס ציונה"): 200,
    ("ירושלים", "אשקלון"): 300,
    ("ירושלים", "רמת גן"): 220,
    ("ירושלים", "נתניה"): 350,
    ("ירושלים", "חדרה"): 400,
    ("ירושלים", "בית שמש"): 150,
    ("ירושלים", "ביתר"): 120,
}


CITIES = [
    "ראשון לציון",
    "ראש העין",
    "תל אביב",
    "בית שמש",
    "בני ברק",
    "נס ציונה",
    "רמת גן",
    "ירושלים",
    "עמנואל",
    "אלעד",
    "אשקלון",
    "נתניה",
    "חדרה",
    "ביתר",
]


# =========================
# עמוד ראשי
# =========================

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp bot is running", 200


# =========================
# אימות Webhook של WhatsApp
# =========================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


# =========================
# זיהוי מסלול
# =========================

def find_route(text):
    found = []

    for city in CITIES:
        position = text.find(city)

        if position != -1:
            found.append((position, city))

    found.sort()

    if len(found) < 2:
        return None, None

    origin = found[0][1]
    destination = found[1][1]

    return origin, destination


# =========================
# קבלת הודעות מ-WhatsApp
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]

        phone = message["from"]
        text = message["text"]["body"].strip()
        clean_text = text.lower().strip()

        # הודעת פתיחה
        if clean_text in ["hi", "hello", "היי", "הי", "שלום"]:
            send_message(
                phone,
                "היי 👋\n\n"
                "ברוכים הבאים לא.א שליחויות 🚚\n\n"
                "מאיפה לאיפה תרצה לבצע את המשלוח?\n\n"
                "לדוגמה: ירושלים לתל אביב"
            )

        # הלקוח אישר ורוצה שליח
        elif clean_text in ["כן", "כן תודה", "מעוניין", "מאשר"]:
            send_message(
                phone,
                "מעולה ✅🚚\n\n"
                "קיבלנו את האישור שלך.\n"
                "אנחנו מתחילים לחפש עבורך שליח לביצוע המשלוח.\n\n"
                "נעדכן אותך ברגע שנמצא שליח מתאים."
            )

        # ניסיון לזהות מסלול
        else:
            origin, destination = find_route(text)

            if origin and destination:
                price = PRICES.get((origin, destination))

                if price:
                    send_message(
                        phone,
                        f"קיבלתי את המסלול שלך 🚚\n\n"
                        f"📍 מוצא: {origin}\n"
                        f"📍 יעד: {destination}\n"
                        f"💰 מחיר המשלוח: {price} ₪\n\n"
                        f"האם תרצה שנמצא עבורך שליח לביצוע המשלוח?\n\n"
                        f"השב כן ונתחיל לחפש עבורך שליח מיד."
                    )

                else:
                    send_message(
                        phone,
                        "קיבלתי את המסלול 🚚\n\n"
                        "אבל כרגע אין לי מחיר מוגדר למסלול הזה במחירון."
                    )

            else:
                send_message(
                    phone,
                    "לא הצלחתי לזהות את המסלול.\n\n"
                    "תרשום לי מאיפה לאיפה המשלוח.\n"
                    "לדוגמה: ירושלים לתל אביב"
                )

    except (KeyError, IndexError, TypeError):
        pass

    return "OK", 200


# =========================
# שליחת הודעה ל-WhatsApp
# =========================

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

    requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10
    )


# =========================
# הפעלת האפליקציה
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
