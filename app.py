from flask import Flask, request
import requests
import os
import re
import time

app = Flask(__name__)

# =========================================================
# הגדרות
# =========================================================

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

# אפשר להגדיר ב-Render משתנה ADMIN_PHONE.
# אם לא הגדרת - הוא ישתמש במספר הזה.
ADMIN_PHONE = os.environ.get(
    "ADMIN_PHONE",
    "972553155049"
)

GRAPH_VERSION = "v23.0"

SESSIONS = {}

# מניעת עיבוד כפול של אותה הודעה
PROCESSED_MESSAGES = {}
MESSAGE_CACHE_SECONDS = 60 * 60


# =========================================================
# מחירון
# =========================================================

PRICES = {
    ("ירושלים", "תל אביב"): 240,
    ("בית שמש", "תל אביב"): 220,
    ("ירושלים", "עמנואל"): 350,
    ("בית שמש", "עמנואל"): 350,
    ("עמנואל", "בני ברק"): 250,
    ("ראש העין", "ירושלים"): 220,
    ("ירושלים", "אלעד"): 220,
    ("ירושלים", "בני ברק"): 220,
    ("ירושלים", "בית שמש"): 200,
    ("ירושלים", "אשקלון"): 300,
    ("ירושלים", "רמת גן"): 220,
    ("ירושלים", "נתניה"): 350,
    ("ירושלים", "חדרה"): 400,
}

CITIES = [
    "ראשון לציון",
    "ראש העין",
    "פתח תקווה",
    "תל אביב",
    "בית שמש",
    "בני ברק",
    "רמת גן",
    "ירושלים",
    "נתניה",
    "אלעד",
    "אשקלון",
    "עמנואל",
    "חדרה",
]

# שמות חלופיים שאנשים עלולים לכתוב
CITY_ALIASES = {
    "תא": "תל אביב",
    "ת״א": "תל אביב",
    'ת"א': "תל אביב",
    "תל-אביב": "תל אביב",
    "פ״ת": "פתח תקווה",
    'פ"ת': "פתח תקווה",
    "ראשלצ": "ראשון לציון",
    'ראשל"צ': "ראשון לציון",
    "רשלצ": "ראשון לציון",
}


# =========================================================
# כלי עזר
# =========================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text).strip().lower()

    # החלפת סימני דרך ברווחים
    text = text.replace("→", " ")
    text = text.replace("->", " ")
    text = text.replace("–", " ")
    text = text.replace("-", " ")
    text = text.replace(",", " ")
    text = text.replace("/", " ")

    # החלפת שמות חלופיים
    for alias, city in CITY_ALIASES.items():
        text = text.replace(alias.lower(), city.lower())

    # מחיקת רווחים כפולים
    text = re.sub(r"\s+", " ", text).strip()

    return text


def cleanup_message_cache():
    now = time.time()

    old_ids = [
        message_id
        for message_id, timestamp in PROCESSED_MESSAGES.items()
        if now - timestamp > MESSAGE_CACHE_SECONDS
    ]

    for message_id in old_ids:
        PROCESSED_MESSAGES.pop(message_id, None)


def already_processed(message_id):
    if not message_id:
        return False

    cleanup_message_cache()

    if message_id in PROCESSED_MESSAGES:
        return True

    PROCESSED_MESSAGES[message_id] = time.time()

    return False


def get_api_url():
    return (
        f"https://graph.facebook.com/"
        f"{GRAPH_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


# =========================================================
# פונקציית שליחה מרכזית
# =========================================================

def send_payload(payload):
    if not ACCESS_TOKEN:
        print("ERROR: WHATSAPP_ACCESS_TOKEN is missing")
        return False

    if not PHONE_NUMBER_ID:
        print("ERROR: WHATSAPP_PHONE_NUMBER_ID is missing")
        return False

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            get_api_url(),
            headers=headers,
            json=payload,
            timeout=15,
        )

        print(
            "WHATSAPP SEND:",
            response.status_code,
            response.text
        )

        return response.ok

    except requests.RequestException as e:
        print("WHATSAPP REQUEST ERROR:", str(e))
        return False

    except Exception as e:
        print("WHATSAPP UNKNOWN ERROR:", str(e))
        return False


# =========================================================
# שליחת טקסט
# =========================================================

def send_message(phone, text):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": text
        },
    }

    return send_payload(payload)


# =========================================================
# שליחת כפתורים
# =========================================================

def send_buttons(phone, body_text, buttons):
    """
    buttons = [
        ("id1", "כותרת 1"),
        ("id2", "כותרת 2")
    ]

    WhatsApp מאפשר עד 3 כפתורי Reply.
    """

    button_objects = []

    for button_id, title in buttons[:3]:
        button_objects.append({
            "type": "reply",
            "reply": {
                "id": button_id,
                "title": title[:20]
            }
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": button_objects
            }
        }
    }

    return send_payload(payload)


# =========================================================
# תפריט
# =========================================================

def send_main_menu(phone):
    send_buttons(
        phone,
        "🚚 א.א שליחויות והפצה\n\n"
        "איך אפשר לעזור לך?",
        [
            ("new_delivery", "📦 הזמנת משלוח"),
            ("check_price", "💰 בדיקת מחיר"),
            ("talk_to_agent", "👤 דבר עם נציג"),
        ]
    )


# =========================================================
# נציג
# =========================================================

def request_agent(phone, reason="הלקוח ביקש לדבר עם נציג"):
    send_message(
        phone,
        "✅ קיבלתי את הבקשה.\n\n"
        "העברתי אותה לנציג אנושי 👤\n"
        "נציג יחזור אליך בהקדם."
    )

    send_message(
        ADMIN_PHONE,
        "👤 בקשת נציג חדשה\n\n"
        f"📱 מספר הלקוח: {phone}\n"
        f"📝 סיבה: {reason}"
    )


# =========================================================
# מציאת מסלול
# =========================================================

def find_route(text):
    clean = normalize_text(text)

    found = []

    # מחפשים לפי מיקום בטקסט
    for city in CITIES:
        position = clean.find(city.lower())

        if position != -1:
            found.append((position, city))

    found.sort(key=lambda x: x[0])

    # מניעת כפילות
    unique_cities = []

    for _, city in found:
        if city not in unique_cities:
            unique_cities.append(city)

    if len(unique_cities) < 2:
        return None, None

    return unique_cities[0], unique_cities[1]


def get_price(origin, destination):
    price = PRICES.get((origin, destination))

    if price is None:
        price = PRICES.get((destination, origin))

    return price


# =========================================================
# הצעת מחיר
# =========================================================

def send_quote(phone, origin, destination, price):
    SESSIONS[phone] = {
        "status": "quoted",
        "origin": origin,
        "destination": destination,
        "price": price,
        "updated": time.time(),
    }

    send_buttons(
        phone,
        "🚚 קיבלתי את המסלול שלך!\n\n"
        f"📍 מוצא: {origin}\n"
        f"📍 יעד: {destination}\n"
        f"💰 מחיר המשלוח: {price} ₪\n\n"
        "רוצה להזמין את המשלוח?",
        [
            ("confirm_delivery", "✅ כן, להזמין"),
            ("cancel_delivery", "❌ לא כרגע"),
            ("talk_to_agent", "👤 נציג"),
        ]
    )


# =========================================================
# התחלת הזמנה
# =========================================================

def start_delivery_details(phone):
    current = SESSIONS.get(phone, {})

    SESSIONS[phone] = {
        **current,
        "status": "waiting_for_details",
        "updated": time.time(),
    }

    send_message(
        phone,
        "מעולה 👍\n\n"
        "שלח לי עכשיו בהודעה אחת את פרטי המשלוח:\n\n"
        "📍 כתובת איסוף – עיר, רחוב ומספר\n"
        "📍 כתובת מסירה – עיר, רחוב ומספר\n"
        "📞 מספר טלפון של איש הקשר\n"
        "👤 שם איש הקשר, אם יש\n"
        "📦 מה מעבירים, אם חשוב לציין\n\n"
        "לדוגמה:\n"
        "איסוף: ירושלים, יפו 10\n"
        "מסירה: תל אביב, דיזנגוף 20\n"
        "טלפון: 05X-XXXXXXX\n"
        "שם: ישראל"
    )


# =========================================================
# שמירת הזמנה
# =========================================================

def finish_delivery(phone, details):
    order = SESSIONS.get(phone, {})

    origin = order.get("origin", "לא צוין")
    destination = order.get("destination", "לא צוין")
    price = order.get("price", "לא נקבע")

    admin_text = (
        "📦 הזמנה חדשה!\n\n"
        f"📱 לקוח: {phone}\n"
        f"📍 מסלול: {origin} → {destination}\n"
        f"💰 מחיר: {price} ₪\n\n"
        "📋 פרטי המשלוח:\n"
        f"{details}"
    )

    send_message(
        ADMIN_PHONE,
        admin_text
    )

    send_message(
        phone,
        "✅ ההזמנה התקבלה!\n\n"
        "העברתי את הפרטים לצוות א.א שליחויות 🚚\n"
        "נעדכן אותך בהמשך לגבי השליח.\n\n"
        "תודה שבחרת בנו 🙏"
    )

    SESSIONS.pop(phone, None)


# =========================================================
# מסלול שאין לו מחיר
# =========================================================

def handle_unknown_price(phone, origin, destination):
    SESSIONS[phone] = {
        "status": "waiting_for_manual_price",
        "origin": origin,
        "destination": destination,
        "updated": time.time(),
    }

    send_message(
        phone,
        "🚚 זיהיתי את המסלול:\n\n"
        f"📍 {origin} → {destination}\n\n"
        "אין לי כרגע מחיר אוטומטי למסלול הזה.\n"
        "העברתי בקשת מחיר לנציג 👤"
    )

    send_message(
        ADMIN_PHONE,
        "💰 בקשת מחיר חדשה\n\n"
        f"📱 לקוח: {phone}\n"
        f"📍 מסלול: {origin} → {destination}\n\n"
        "אין מחיר למסלול הזה במחירון של הבוט."
    )


# =========================================================
# מסך בריאות
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp bot is running", 200


# =========================================================
# אימות Webhook
# =========================================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


# =========================================================
# קבלת הודעות
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    try:
        entry = data.get("entry", [])

        if not entry:
            return "OK", 200

        changes = entry[0].get("changes", [])

        if not changes:
            return "OK", 200

        value = changes[0].get("value", {})

        # delivered / read / sent וכו'
        if "messages" not in value:
            return "OK", 200

        messages = value.get("messages", [])

        if not messages:
            return "OK", 200

        message = messages[0]

        message_id = message.get("id")

        # Meta לפעמים שולחת Webhook שוב
        if already_processed(message_id):
            print("DUPLICATE MESSAGE IGNORED:", message_id)
            return "OK", 200

        phone = message.get("from")

        if not phone:
            return "OK", 200

        message_type = message.get("type")

        button_id = None
        text = ""

        # =====================================
        # הודעת טקסט
        # =====================================

        if message_type == "text":
            text = (
                message
                .get("text", {})
                .get("body", "")
                .strip()
            )

        # =====================================
        # לחיצה על כפתור
        # =====================================

        elif message_type == "interactive":
            interactive = message.get("interactive", {})

            if interactive.get("type") == "button_reply":
                button_reply = interactive.get(
                    "button_reply",
                    {}
                )

                button_id = button_reply.get("id")

                text = button_reply.get(
                    "title",
                    ""
                )

        else:
            send_message(
                phone,
                "כרגע אני יודע לקבל הודעת טקסט 🙂\n"
                "אפשר לכתוב לי 'תפריט'."
            )

            return "OK", 200

        clean_text = normalize_text(text)

        print(
            "INCOMING:",
            phone,
            message_type,
            clean_text
        )


        # =================================================
        # לחיצות כפתור
        # =================================================

        if button_id == "talk_to_agent":
            request_agent(phone)
            return "OK", 200


        if button_id == "new_delivery":
            SESSIONS[phone] = {
                "status": "waiting_for_route",
                "updated": time.time(),
            }

            send_message(
                phone,
                "📦 מצוין.\n\n"
                "שלח לי את המסלול שלך.\n"
                "לדוגמה:\n"
                "ירושלים תל אביב"
            )

            return "OK", 200


        if button_id == "check_price":
            SESSIONS[phone] = {
                "status": "waiting_for_route",
                "updated": time.time(),
            }

            send_message(
                phone,
                "💰 בשמחה.\n\n"
                "כתוב את שתי הערים במסלול.\n"
                "לדוגמה:\n"
                "ירושלים → תל אביב"
            )

            return "OK", 200


        if button_id == "confirm_delivery":
            start_delivery_details(phone)
            return "OK", 200


        if button_id == "cancel_delivery":
            SESSIONS.pop(phone, None)

            send_message(
                phone,
                "אין בעיה 🙂\n"
                "המשלוח לא הוזמן.\n\n"
                "כשתרצה, פשוט כתוב 'תפריט'."
            )

            return "OK", 200


        # =================================================
        # פקודות שאפשר לכתוב בכל רגע
        # =================================================

        if clean_text in [
            "תפריט",
            "עזרה",
            "אפשרויות",
            "menu",
        ]:
            send_main_menu(phone)
            return "OK", 200


        if clean_text in [
            "ביטול",
            "בטל",
            "לבטל",
            "cancel",
        ]:
            SESSIONS.pop(phone, None)

            send_message(
                phone,
                "✅ ביטלתי את הפעולה הנוכחית.\n\n"
                "כתוב 'תפריט' כדי להתחיל מחדש."
            )

            return "OK", 200


        # =================================================
        # נציג
        # =================================================

        agent_words = [
            "נציג",
            "נציג שירות",
            "אדם",
            "בן אדם",
            "שירות לקוחות",
            "לדבר עם נציג",
            "רוצה נציג",
            "טלפון",
        ]

        if any(
            word in clean_text
            for word in agent_words
        ):
            request_agent(
                phone,
                reason=f"הודעת הלקוח: {text}"
            )

            return "OK", 200


        # =================================================
        # פתיחה
        # =================================================

        if clean_text in [
            "היי",
            "הי",
            "שלום",
            "אהלן",
            "הלו",
            "בוקר טוב",
            "ערב טוב",
            "hi",
            "hello",
        ]:
            send_message(
                phone,
                "היי 👋\n"
                "ברוכים הבאים לא.א שליחויות והפצה 🚚\n\n"
                "אני העוזר האוטומטי שלנו.\n"
                "אני יכול לבדוק מחיר, לפתוח הזמנה "
                "או להעביר אותך לנציג."
            )

            send_main_menu(phone)

            return "OK", 200


        # =================================================
        # לקוח נמצא בשלב שליחת פרטי הזמנה
        # =================================================

        session = SESSIONS.get(phone, {})

        if (
            session.get("status")
            == "waiting_for_details"
        ):
            if len(text.strip()) < 8:
                send_message(
                    phone,
                    "חסרים לי קצת פרטים 🙂\n\n"
                    "שלח בבקשה כתובת איסוף, "
                    "כתובת מסירה ומספר טלפון."
                )

                return "OK", 200

            finish_delivery(
                phone,
                text
            )

            return "OK", 200


        # =================================================
        # כן / אישור
        # =================================================

        if clean_text in [
            "כן",
            "כן תודה",
            "מעוניין",
            "כן מעוניין",
            "להזמין",
            "רוצה",
            "רוצה להזמין",
            "בצע",
        ]:
            if session.get("status") == "quoted":
                start_delivery_details(phone)

            else:
                SESSIONS[phone] = {
                    "status": "waiting_for_route",
                    "updated": time.time(),
                }

                send_message(
                    phone,
                    "מעולה 👍\n"
                    "כתוב לי את המסלול שלך.\n\n"
                    "לדוגמה:\n"
                    "ירושלים תל אביב"
                )

            return "OK", 200


        # =================================================
        # לא
        # =================================================

        if clean_text in [
            "לא",
            "לא תודה",
            "לא מעוניין",
        ]:
            SESSIONS.pop(phone, None)

            send_message(
                phone,
                "אין בעיה 🙂\n"
                "אם תרצה בהמשך, פשוט כתוב 'תפריט'."
            )

            return "OK", 200


        # =================================================
        # ניסיון לזהות מסלול
        # =================================================

        origin, destination = find_route(text)

        if origin and destination:
            price = get_price(
                origin,
                destination
            )

            if price is not None:
                send_quote(
                    phone,
                    origin,
                    destination,
                    price
                )

            else:
                handle_unknown_price(
                    phone,
                    origin,
                    destination
                )

            return "OK", 200


        # =================================================
        # חיכה למסלול ולא קיבל שתי ערים
        # =================================================

        if session.get("status") == "waiting_for_route":
            send_message(
                phone,
                "לא הצלחתי לזהות שתי ערים 🤔\n\n"
                "נסה לכתוב רק את המסלול, למשל:\n"
                "ירושלים תל אביב\n\n"
                "או כתוב 'נציג'."
            )

            return "OK", 200


        # =================================================
        # ברירת מחדל חכמה
        # =================================================

        send_buttons(
            phone,
            "לא הייתי בטוח למה התכוונת 🙂\n"
            "בחר מה תרצה לעשות:",
            [
                ("check_price", "💰 בדיקת מחיר"),
                ("new_delivery", "📦 משלוח חדש"),
                ("talk_to_agent", "👤 נציג"),
            ]
        )

        return "OK", 200

    except Exception as e:
        print(
            "WEBHOOK ERROR:",
            type(e).__name__,
            str(e)
        )

        return "OK", 200


# =========================================================
# הפעלת האפליקציה
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
