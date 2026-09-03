from flask import Flask, request
import requests
import os

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
ADMIN_PHONE = "972553155049"
SESSIONS = {}

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

        if message.get("type") == "interactive":
            button_id = message["interactive"]["button_reply"]["id"]
            text = ""
            clean_text = ""
        else:
            button_id = None
            text = message["text"]["body"].strip()
            clean_text = text.lower().strip()      
        if button_id == "talk_to_agent":
            send_message(
                phone,
                "✅ בקשתך נשלחה לנציג.\n\n"
                "נציג יחזור אליך בהקדם."
            )

            send_message(
                ADMIN_PHONE,
                f"👤 בקשה לנציג\n\n"
                f"לקוח מספר: {phone}\n"
                f"מבקש לדבר עם נציג."
            )     
    # הודעת פתיחה
        elif clean_text in ["hi", "hello", "היי", "הי", "שלום"]:
            send_message(
                phone,
                "היי 👋\n\n"
                "ברוכים הבאים לא.א שליחויות 🚚\n\n"
                "מאיפה לאיפה תרצה לבצע את המשלוח?\n\n"
                "לדוגמה: ירושלים לתל אביב"
            )

        # הלקוח אישר ורוצה שליח
        elif clean_text in ["כן", "כן תודה", "מעוניין", "מאשר"]:
            SESSIONS[phone]["status"] = "waiting_for_details"    
            send_message(
                phone,
                       "מעולה 🚚\n\n"
                "כדי שנוכל להתחיל לחפש עבורך שליח, אנא שלח בהודעה אחת את הפרטים הבאים:\n\n"
                "📍 כתובת איסוף – רחוב ומספר בית\n"
                "📍 כתובת מסירה – רחוב ומספר בית\n"
                "📞 מספר הטלפון של איש הקשר בנקודת המסירה\n\n"
                "אנא שלח את כל הפרטים בהודעה אחת."        
            )
            
        elif clean_text in ["לא", "לא תודה", "לא מעוניין"]:
            send_message(
                phone,
                "אין בעיה 😊\n\n"
                "תודה שפנית לא.א שליחויות 🚚\n"
                "אם תרצה לבצע משלוח אחר, פשוט שלח לי מאיפה לאיפה."
            )
        elif phone in SESSIONS and SESSIONS[phone].get("status") == "waiting_for_details":
            order = SESSIONS[phone]

            send_message(
                ADMIN_PHONE,
                f"🚚 הזמנה חדשה!\n\n"
                f"📱 מספר הלקוח: {phone}\n"
                f"📍 מסלול: {order['origin']} → {order['destination']}\n"
                f"💰 מחיר: {order['price']} ₪\n\n"
                f"📦 פרטי האיסוף והמסירה:\n{text}"
            )

            send_message(
                phone,
                "✅ קיבלנו את כל פרטי המשלוח.\n\n"
                "אנחנו מתחילים לחפש עבורך שליח 🚚\n"
                "השליח יצור איתך קשר ברגע שיימצא."
            )

            del SESSIONS[phone]
        elif any(word in clean_text for word in ["כמה זמן", "מתי", "איפה", "נו", "עדכון", "יש עדכון", "מה קורה", "מה עם המשלוח", "השליח"]):
            send_agent_button(phone)    
        # ניסיון לזהות מסלול
        else:
            origin, destination = find_route(text)

            if origin and destination:
                price = PRICES.get((origin, destination)) or PRICES.get((destination, origin))
                if price:
                    SESSIONS[phone] = {"origin": origin, "destination": destination, "price": price, "status": "quoted"}
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

def send_agent_button(phone):
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "🚚 ההזמנה שלך בטיפול.\n\nאנחנו מחפשים עבורך שליח כרגע.\nברגע שיימצא שליח מתאים, הוא יצור איתך קשר.\nתודה על הסבלנות 🙏"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "talk_to_agent",
                            "title": "👤 דבר עם נציג"
                        }
                    }
                ]
            }
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
