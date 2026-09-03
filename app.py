from flask import Flask, request
import requests
import os
import re
import time
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

# =========================================================
# הגדרות
# =========================================================

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

ADMIN_PHONE = os.environ.get(
    "ADMIN_PHONE",
    "972553155049"
)

GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v23.0"
)

BUSINESS_NAME = "א.א שליחויות והפצה"

SESSIONS = {}
ORDERS = {}
LAST_ORDER_BY_PHONE = {}
PROCESSED_MESSAGES = {}

MESSAGE_CACHE_SECONDS = 3600


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

CITY_ALIASES = {
    "תא": "תל אביב",
    'ת"א': "תל אביב",
    "ת״א": "תל אביב",
    "תל-אביב": "תל אביב",

    'פ"ת': "פתח תקווה",
    "פ״ת": "פתח תקווה",

    'ראשל"צ': "ראשון לציון",
    "ראשלצ": "ראשון לציון",
    "רשלצ": "ראשון לציון",
}


# =========================================================
# סטטוסים להזמנות
# =========================================================

STATUS_TEXT = {
    "new": "📋 ההזמנה התקבלה",
    "waiting_driver": "🔎 מחפשים שליח",
    "driver_assigned": "🚚 נמצא שליח",
    "on_way_pickup": "🚗 השליח בדרך לאיסוף",
    "picked_up": "📦 המשלוח נאסף",
    "on_way_destination": "🛣️ המשלוח בדרך ליעד",
    "delivered": "✅ המשלוח נמסר",
    "cancelled": "❌ המשלוח בוטל",
}

HEBREW_STATUS_TO_CODE = {
    "התקבלה": "new",
    "מחפשים שליח": "waiting_driver",
    "מחפש שליח": "waiting_driver",
    "נמצא שליח": "driver_assigned",
    "בדרך לאיסוף": "on_way_pickup",
    "נאסף": "picked_up",
    "בדרך ליעד": "on_way_destination",
    "נמסר": "delivered",
    "בוטל": "cancelled",
}


# =========================================================
# כלי עזר
# =========================================================

def normalize_text(text):
    if not text:
        return ""

    text = str(text).lower().strip()

    for symbol in [
        "→", "->", "–", "-", ",", "/", "|"
    ]:
        text = text.replace(symbol, " ")

    for alias, city in CITY_ALIASES.items():
        text = text.replace(
            alias.lower(),
            city.lower()
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def now_israel():
    return datetime.now(
        ZoneInfo("Asia/Jerusalem")
    )


def cleanup_message_cache():
    now = time.time()

    expired = []

    for message_id, created in PROCESSED_MESSAGES.items():
        if now - created > MESSAGE_CACHE_SECONDS:
            expired.append(message_id)

    for message_id in expired:
        PROCESSED_MESSAGES.pop(
            message_id,
            None
        )


def is_duplicate(message_id):
    if not message_id:
        return False

    cleanup_message_cache()

    if message_id in PROCESSED_MESSAGES:
        return True

    PROCESSED_MESSAGES[message_id] = time.time()

    return False


def api_url():
    return (
        f"https://graph.facebook.com/"
        f"{GRAPH_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


def create_order_id():
    number = int(time.time() * 1000) % 1000000

    return f"AA-{number:06d}"


def location_to_text(location):
    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if latitude is None or longitude is None:
        return ""

    return (
        f"מיקום שנשלח בוואטסאפ:\n"
        f"https://maps.google.com/?q="
        f"{latitude},{longitude}"
    )


# =========================================================
# שליחה לוואטסאפ
# =========================================================

def send_payload(payload):
    if not ACCESS_TOKEN:
        print(
            "ERROR: WHATSAPP_ACCESS_TOKEN missing"
        )
        return False

    if not PHONE_NUMBER_ID:
        print(
            "ERROR: WHATSAPP_PHONE_NUMBER_ID missing"
        )
        return False

    headers = {
        "Authorization":
            f"Bearer {ACCESS_TOKEN}",

        "Content-Type":
            "application/json",
    }

    try:
        response = requests.post(
            api_url(),
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

    except Exception as e:
        print(
            "WHATSAPP SEND ERROR:",
            str(e)
        )

        return False


def send_message(phone, text):
    return send_payload({
        "messaging_product":
            "whatsapp",

        "to":
            phone,

        "type":
            "text",

        "text": {
            "body":
                text
        }
    })


def send_buttons(
    phone,
    text,
    buttons
):
    button_list = []

    for button_id, title in buttons[:3]:

        button_list.append({
            "type": "reply",

            "reply": {
                "id":
                    button_id,

                "title":
                    title[:20]
            }
        })

    return send_payload({
        "messaging_product":
            "whatsapp",

        "to":
            phone,

        "type":
            "interactive",

        "interactive": {
            "type":
                "button",

            "body": {
                "text":
                    text
            },

            "action": {
                "buttons":
                    button_list
            }
        }
    })


# =========================================================
# פתיחה ותפריט
# =========================================================

def send_welcome(phone):

    send_message(
        phone,

        "👋 היי!\n\n"
        "ברוכים הביא ל-א.א שליחויות והפצה\n\n"
        "🚚 אני כאן כדי להפוך את הזמנת "
        "המשלוח לפשוטה ומהירה.\n\n"
        "אפשר לבדוק מחיר, להזמין משלוח, "
        "לעקוב אחרי הזמנה או לדבר עם נציג."
    )

    send_main_menu(phone)


def send_main_menu(phone):

    send_buttons(
        phone,

        "מה תרצה לעשות?",

        [
            (
                "new_delivery",
                "📦 משלוח חדש"
            ),

            (
                "check_price",
                "💰 בדיקת מחיר"
            ),

            (
                "more_options",
                "⚙️ אפשרויות"
            ),
        ]
    )


def send_more_options(phone):

    send_buttons(
        phone,

        "עוד אפשרויות:",

        [
            (
                "track_order",
                "📍 מעקב משלוח"
            ),

            (
                "repeat_order",
                "🔁 הזמנה חוזרת"
            ),

            (
                "talk_to_agent",
                "👤 נציג"
            ),
        ]
    )


# =========================================================
# מעבר לנציג
# =========================================================

def request_agent(
    phone,
    reason="הלקוח ביקש נציג"
):

    send_message(
        phone,

        "✅ הבקשה התקבלה.\n\n"
        "העברתי את הפנייה לנציג אנושי 👤\n"
        "נציג יחזור אליך בהקדם."
    )

    send_message(
        ADMIN_PHONE,

        "👤 בקשת נציג חדשה\n\n"
        f"📱 לקוח: {phone}\n"
        f"📝 סיבה: {reason}"
    )


# =========================================================
# מסלול ומחיר
# =========================================================

def find_route(text):
    clean = normalize_text(text)

    found = []

    for city in CITIES:

        position = clean.find(
            city.lower()
        )

        if position != -1:

            found.append(
                (
                    position,
                    city
                )
            )

    found.sort(
        key=lambda item: item[0]
    )

    unique = []

    for _, city in found:

        if city not in unique:
            unique.append(city)

    if len(unique) < 2:
        return None, None

    return (
        unique[0],
        unique[1]
    )


def get_price(
    origin,
    destination
):

    price = PRICES.get(
        (
            origin,
            destination
        )
    )

    if price is None:

        price = PRICES.get(
            (
                destination,
                origin
            )
        )

    return price


def send_quote(
    phone,
    origin,
    destination,
    price
):

    SESSIONS[phone] = {
        "status":
            "quoted",

        "origin":
            origin,

        "destination":
            destination,

        "price":
            price,

        "misunderstandings":
            0,

        "updated":
            time.time()
    }

    send_buttons(
        phone,

        "🚚 קיבלתי את המסלול שלך!\n\n"
        f"📍 מוצא: {origin}\n"
        f"📍 יעד: {destination}\n"
        f"💰 מחיר המשלוח: {price} ₪\n\n"
        "רוצה להזמין?",

        [
            (
                "confirm_delivery",
                "✅ כן, להזמין"
            ),

            (
                "urgent_delivery",
                "⚡ דחוף"
            ),

            (
                "cancel_delivery",
                "❌ לא כרגע"
            ),
        ]
    )


def handle_unknown_price(
    phone,
    origin,
    destination
):

    SESSIONS[phone] = {
        "status":
            "manual_price",

        "origin":
            origin,

        "destination":
            destination,

        "updated":
            time.time()
    }

    send_message(
        phone,

        "🚚 זיהיתי את המסלול:\n\n"
        f"📍 {origin} → {destination}\n\n"
        "אין לי מחיר אוטומטי למסלול הזה.\n"
        "העברתי בקשת מחיר לנציג 👤"
    )

    send_message(
        ADMIN_PHONE,

        "💰 בקשת מחיר חדשה\n\n"
        f"📱 לקוח: {phone}\n"
        f"📍 מסלול: {origin} → {destination}"
    )


# =========================================================
# בניית הזמנה שלב אחרי שלב
# =========================================================

def start_order(phone):

    current = SESSIONS.get(
        phone,
        {}
    )

    current["status"] = (
        "pickup_address"
    )

    current["updated"] = time.time()

    SESSIONS[phone] = current

    send_message(
        phone,

        "📍 מאיפה אוספים?\n\n"
        "שלח עיר, רחוב ומספר בית.\n\n"
        "אפשר גם לשלוח 📍 מיקום "
        "ישירות מוואטסאפ."
    )


def ask_dropoff(phone):

    SESSIONS[phone]["status"] = (
        "dropoff_address"
    )

    send_message(
        phone,

        "📍 ולאן מוסרים?\n\n"
        "שלח עיר, רחוב ומספר בית.\n\n"
        "אפשר גם לשלוח מיקום."
    )


def ask_recipient_name(phone):

    SESSIONS[phone]["status"] = (
        "recipient_name"
    )

    send_message(
        phone,

        "👤 מה השם של האדם "
        "שמקבל את המשלוח?"
    )


def ask_recipient_phone(phone):

    SESSIONS[phone]["status"] = (
        "recipient_phone"
    )

    send_message(
        phone,

        "📞 מה מספר הטלפון "
        "של המקבל?"
    )


def ask_package(phone):

    SESSIONS[phone]["status"] = (
        "package"
    )

    send_buttons(
        phone,

        "📦 מה שולחים?",

        [
            (
                "package_envelope",
                "✉️ מעטפה"
            ),

            (
                "package_box",
                "📦 חבילה"
            ),

            (
                "package_other",
                "📝 משהו אחר"
            ),
        ]
    )


def ask_time(phone):

    SESSIONS[phone]["status"] = (
        "delivery_time"
    )

    send_buttons(
        phone,

        "🕐 מתי תרצה שהמשלוח יתבצע?",

        [
            (
                "time_now",
                "🚚 עכשיו"
            ),

            (
                "time_today",
                "🕐 היום"
            ),

            (
                "time_other",
                "📅 זמן אחר"
            ),
        ]
    )


def ask_notes(phone):

    SESSIONS[phone]["status"] = (
        "notes"
    )

    send_message(
        phone,

        "📝 יש משהו שחשוב שהשליח ידע?\n\n"
        "לדוגמה:\n"
        "קומה 4\n"
        "אין מעלית\n"
        "חבילה שבירה\n"
        "להתקשר לפני שמגיעים\n\n"
        "אם אין, כתוב: אין"
    )


# =========================================================
# סיכום הזמנה
# =========================================================

def send_order_summary(phone):

    order = SESSIONS.get(
        phone,
        {}
    )

    summary = (
        "📋 סיכום ההזמנה\n\n"

        f"📍 איסוף:\n"
        f"{order.get('pickup_address', '-')}\n\n"

        f"📍 מסירה:\n"
        f"{order.get('dropoff_address', '-')}\n\n"

        f"👤 מקבל: "
        f"{order.get('recipient_name', '-')}\n"

        f"📞 טלפון: "
        f"{order.get('recipient_phone', '-')}\n\n"

        f"📦 משלוח: "
        f"{order.get('package', '-')}\n"

        f"🕐 מועד: "
        f"{order.get('delivery_time', '-')}\n"

        f"📝 הערות: "
        f"{order.get('notes', '-')}\n"
    )

    if order.get("price"):

        summary += (
            f"\n💰 מחיר: "
            f"{order['price']} ₪\n"
        )

    if order.get("urgent"):

        summary += (
            "\n⚡ סומן כמשלוח דחוף\n"
        )

    summary += (
        "\nהכול נכון?"
    )

    SESSIONS[phone]["status"] = (
        "confirmation"
    )

    send_buttons(
        phone,

        summary,

        [
            (
                "final_confirm",
                "✅ אשר הזמנה"
            ),

            (
                "edit_order",
                "✏️ שנה פרטים"
            ),

            (
                "cancel_delivery",
                "❌ ביטול"
            ),
        ]
    )


# =========================================================
# עריכת פרטים
# =========================================================

def send_edit_menu(phone):

    send_buttons(
        phone,

        "מה תרצה לשנות?",

        [
            (
                "edit_pickup",
                "📍 איסוף"
            ),

            (
                "edit_dropoff",
                "📍 מסירה"
            ),

            (
                "edit_more",
                "⚙️ עוד פרטים"
            ),
        ]
    )


def send_edit_more(phone):

    send_buttons(
        phone,

        "מה עוד תרצה לשנות?",

        [
            (
                "edit_phone",
                "📞 טלפון"
            ),

            (
                "edit_time",
                "🕐 זמן"
            ),

            (
                "edit_notes",
                "📝 הערות"
            ),
        ]
    )


# =========================================================
# אישור סופי
# =========================================================

def confirm_order(phone):

    session = SESSIONS.get(
        phone,
        {}
    )

    order_id = create_order_id()

    order = copy.deepcopy(
        session
    )

    order["order_id"] = order_id
    order["customer_phone"] = phone
    order["status"] = "waiting_driver"

    order["created_at"] = (
        now_israel()
        .strftime(
            "%d/%m/%Y %H:%M"
        )
    )

    ORDERS[order_id] = order

    LAST_ORDER_BY_PHONE[
        phone
    ] = order_id

    send_message(
        phone,

        "✅ ההזמנה נקלטה בהצלחה!\n\n"
        f"🔢 מספר הזמנה: {order_id}\n"
        "🔎 סטטוס: מחפשים שליח\n\n"
        "שמור את מספר ההזמנה "
        "למעקב בהמשך."
    )

    admin_message = (
        "📦 הזמנה חדשה!\n\n"

        f"🔢 הזמנה: {order_id}\n"
        f"📱 לקוח: {phone}\n\n"

        f"📍 איסוף:\n"
        f"{order.get('pickup_address', '-')}\n\n"

        f"📍 מסירה:\n"
        f"{order.get('dropoff_address', '-')}\n\n"

        f"👤 מקבל: "
        f"{order.get('recipient_name', '-')}\n"

        f"📞 טלפון: "
        f"{order.get('recipient_phone', '-')}\n\n"

        f"📦 משלוח: "
        f"{order.get('package', '-')}\n"

        f"🕐 מועד: "
        f"{order.get('delivery_time', '-')}\n"

        f"📝 הערות: "
        f"{order.get('notes', '-')}\n"
    )

    if order.get("price"):

        admin_message += (
            f"\n💰 מחיר: "
            f"{order['price']} ₪"
        )

    if order.get("urgent"):

        admin_message += (
            "\n⚡ דחוף!"
        )

    send_message(
        ADMIN_PHONE,
        admin_message
    )

    SESSIONS.pop(
        phone,
        None
    )


# =========================================================
# מעקב
# =========================================================

def send_tracking(phone, order_id):

    order = ORDERS.get(order_id)

    if not order:

        send_message(
            phone,

            "לא מצאתי הזמנה עם המספר הזה 🤔\n\n"
            "בדוק שמספר ההזמנה כתוב נכון.\n"
            "לדוגמה: AA-123456"
        )

        return

    if (
        order.get("customer_phone")
        != phone
        and phone != ADMIN_PHONE
    ):
        send_message(
            phone,
            "לא מצאתי הזמנה מתאימה."
        )

        return

    status_code = order.get(
        "status",
        "new"
    )

    status = STATUS_TEXT.get(
        status_code,
        status_code
    )

    send_message(
        phone,

        "📍 מעקב משלוח\n\n"
        f"🔢 הזמנה: {order_id}\n"
        f"{status}\n\n"
        f"📍 איסוף: "
        f"{order.get('pickup_address', '-')}\n"

        f"📍 מסירה: "
        f"{order.get('dropoff_address', '-')}"
    )


# =========================================================
# עדכון סטטוס על ידי המנהל
# =========================================================

def handle_admin_command(
    text
):
    clean = text.strip()

    match = re.match(
        r"^סטטוס\s+"
        r"(AA-\d+)\s+(.+)$",
        clean,
        re.IGNORECASE
    )

    if not match:
        return False

    order_id = (
        match
        .group(1)
        .upper()
    )

    wanted_status = (
        match
        .group(2)
        .strip()
    )

    if order_id not in ORDERS:

        send_message(
            ADMIN_PHONE,
            "❌ מספר הזמנה לא נמצא."
        )

        return True

    code = HEBREW_STATUS_TO_CODE.get(
        wanted_status
    )

    if not code:

        send_message(
            ADMIN_PHONE,

            "לא זיהיתי את הסטטוס.\n\n"
            "אפשר למשל:\n"
            "התקבלה\n"
            "מחפשים שליח\n"
            "נמצא שליח\n"
            "בדרך לאיסוף\n"
            "נאסף\n"
            "בדרך ליעד\n"
            "נמסר\n"
            "בוטל"
        )

        return True

    ORDERS[
        order_id
    ]["status"] = code

    customer = ORDERS[
        order_id
    ].get(
        "customer_phone"
    )

    status_text = STATUS_TEXT.get(
        code,
        code
    )

    send_message(
        ADMIN_PHONE,

        "✅ הסטטוס עודכן.\n"
        f"{order_id}\n"
        f"{status_text}"
    )

    if customer:

        send_message(
            customer,

            "🔔 עדכון לגבי המשלוח שלך\n\n"
            f"🔢 {order_id}\n"
            f"{status_text}"
        )

    return True


# =========================================================
# הודעה שלא הובנה
# =========================================================

def handle_unknown(phone):

    session = SESSIONS.setdefault(
        phone,
        {}
    )

    count = (
        session.get(
            "misunderstandings",
            0
        )
        + 1
    )

    session[
        "misunderstandings"
    ] = count

    if count >= 2:

        session[
            "misunderstandings"
        ] = 0

        send_buttons(
            phone,

            "נראה שלא הצלחתי להבין אותך 🙂\n"
            "אפשר לבחור מה לעשות:",

            [
                (
                    "main_menu",
                    "🏠 תפריט"
                ),

                (
                    "talk_to_agent",
                    "👤 נציג"
                ),

                (
                    "check_price",
                    "💰 מחיר"
                ),
            ]
        )

    else:

        send_message(
            phone,

            "לא לגמרי הבנתי 🙂\n\n"
            "אפשר לכתוב:\n"
            "תפריט\n"
            "משלוח חדש\n"
            "בדיקת מחיר\n"
            "מעקב\n"
            "נציג"
        )


# =========================================================
# דף ראשי
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "WhatsApp bot is running",
        200
    )


# =========================================================
# אימות Webhook
# =========================================================

@app.route(
    "/webhook",
    methods=["GET"]
)
def verify_webhook():

    mode = request.args.get(
        "hub.mode"
    )

    token = request.args.get(
        "hub.verify_token"
    )

    challenge = request.args.get(
        "hub.challenge"
    )

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
    ):
        return challenge, 200

    return (
        "Verification failed",
        403
    )


# =========================================================
# Webhook הודעות
# =========================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:

        entry = data.get(
            "entry",
            []
        )

        if not entry:
            return "OK", 200

        changes = (
            entry[0]
            .get(
                "changes",
                []
            )
        )

        if not changes:
            return "OK", 200

        value = (
            changes[0]
            .get(
                "value",
                {}
            )
        )

        # הודעות סטטוס כגון read/delivered
        if "messages" not in value:
            return "OK", 200

        messages = value.get(
            "messages",
            []
        )

        if not messages:
            return "OK", 200

        message = messages[0]

        message_id = (
            message.get("id")
        )

        if is_duplicate(
            message_id
        ):

            print(
                "DUPLICATE IGNORED:",
                message_id
            )

            return "OK", 200

        phone = message.get(
            "from"
        )

        if not phone:
            return "OK", 200

        message_type = (
            message.get(
                "type"
            )
        )

        text = ""
        button_id = None
        location_text = None

        # =====================================
        # טקסט
        # =====================================

        if message_type == "text":

            text = (
                message
                .get(
                    "text",
                    {}
                )
                .get(
                    "body",
                    ""
                )
                .strip()
            )

        # =====================================
        # כפתור
        # =====================================

        elif message_type == "interactive":

            interactive = (
                message.get(
                    "interactive",
                    {}
                )
            )

            if (
                interactive.get("type")
                == "button_reply"
            ):

                button = (
                    interactive
                    .get(
                        "button_reply",
                        {}
                    )
                )

                button_id = (
                    button.get("id")
                )

                text = (
                    button.get(
                        "title",
                        ""
                    )
                )

        # =====================================
        # מיקום
        # =====================================

        elif message_type == "location":

            location = (
                message.get(
                    "location",
                    {}
                )
            )

            location_text = (
                location_to_text(
                    location
                )
            )

        else:

            send_message(
                phone,

                "כרגע אני יודע לעבוד עם "
                "טקסט ומיקום 📍\n\n"
                "כתוב 'תפריט' כדי להמשיך."
            )

            return "OK", 200

        clean = normalize_text(
            text
        )

        print(
            "INCOMING:",
            phone,
            message_type,
            clean
        )

        # =====================================
        # פקודות מנהל
        # =====================================

        if (
            phone == ADMIN_PHONE
            and text
        ):

            if handle_admin_command(
                text
            ):
                return "OK", 200


        # =====================================
        # פקודות כלליות בכל רגע
        # =====================================

        if clean in [
            "היי",
            "הי",
            "שלום",
            "אהלן",
            "הלו",
            "hi",
            "hello",
            "start",
        ]:

            SESSIONS.pop(
                phone,
                None
            )

            send_welcome(phone)

            return "OK", 200


        if clean in [
            "תפריט",
            "ראשי",
            "בית",
            "menu",
        ]:

            send_main_menu(phone)

            return "OK", 200


        if clean in [
            "עזרה",
            "help",
        ]:

            send_message(
                phone,

                "ℹ️ עזרה\n\n"
                "אפשר לכתוב בכל רגע:\n"
                "• תפריט\n"
                "• ביטול\n"
                "• נציג\n"
                "• מעקב\n\n"
                "או פשוט לכתוב מסלול כמו:\n"
                "ירושלים תל אביב"
            )

            return "OK", 200


        if clean in [
            "ביטול",
            "בטל",
            "לבטל",
            "cancel",
        ]:

            SESSIONS.pop(
                phone,
                None
            )

            send_message(
                phone,

                "✅ הפעולה בוטלה.\n\n"
                "כשתרצה להתחיל מחדש, "
                "כתוב 'תפריט'."
            )

            return "OK", 200


        # =====================================
        # כפתורים
        # =====================================

        if button_id == "main_menu":

            send_main_menu(phone)

            return "OK", 200


        if button_id == "more_options":

            send_more_options(phone)

            return "OK", 200


        if button_id == "talk_to_agent":

            request_agent(phone)

            return "OK", 200


        if button_id == "new_delivery":

            SESSIONS[phone] = {
                "status":
                    "waiting_route",

                "updated":
                    time.time()
            }

            send_message(
                phone,

                "📦 מצוין.\n\n"
                "כתוב את המסלול שלך.\n"
                "לדוגמה:\n"
                "ירושלים תל אביב"
            )

            return "OK", 200


        if button_id == "check_price":

            SESSIONS[phone] = {
                "status":
                    "waiting_route",

                "updated":
                    time.time()
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

            start_order(phone)

            return "OK", 200


        if button_id == "urgent_delivery":

            session = SESSIONS.get(
                phone,
                {}
            )

            session["urgent"] = True
            SESSIONS[phone] = session

            send_message(
                phone,

                "⚡ סימנתי שהמשלוח דחוף.\n"
                "נמשיך לפרטי ההזמנה."
            )

            start_order(phone)

            return "OK", 200


        if button_id == "cancel_delivery":

            SESSIONS.pop(
                phone,
                None
            )

            send_message(
                phone,

                "אין בעיה 🙂\n"
                "ההזמנה בוטלה.\n\n"
                "כתוב 'תפריט' מתי שתרצה."
            )

            return "OK", 200


        # =====================================
        # מעקב
        # =====================================

        if (
            button_id == "track_order"
            or clean == "מעקב"
        ):

            SESSIONS[phone] = {
                "status":
                    "tracking"
            }

            send_message(
                phone,

                "📍 שלח לי את מספר ההזמנה.\n"
                "לדוגמה:\n"
                "AA-123456"
            )

            return "OK", 200


        # =====================================
        # הזמנה חוזרת
        # =====================================

        if button_id == "repeat_order":

            last_id = (
                LAST_ORDER_BY_PHONE
                .get(phone)
            )

            if not last_id:

                send_message(
                    phone,

                    "עדיין אין לי הזמנה קודמת "
                    "שאפשר לשכפל 🙂"
                )

                return "OK", 200

            old = ORDERS.get(
                last_id
            )

            if not old:

                send_message(
                    phone,

                    "לא הצלחתי למצוא את "
                    "ההזמנה הקודמת."
                )

                return "OK", 200

            new_session = {
                "origin":
                    old.get("origin"),

                "destination":
                    old.get(
                        "destination"
                    ),

                "price":
                    old.get("price"),

                "pickup_address":
                    old.get(
                        "pickup_address"
                    ),

                "dropoff_address":
                    old.get(
                        "dropoff_address"
                    ),

                "package":
                    old.get("package"),

                "status":
                    "recipient_name",

                "updated":
                    time.time()
            }

            SESSIONS[
                phone
            ] = new_session

            send_message(
                phone,

                "🔁 העתקתי את פרטי "
                "המשלוח האחרון.\n\n"
                "רק נוודא מחדש את "
                "פרטי המקבל."
            )

            ask_recipient_name(
                phone
            )

            return "OK", 200


        # =====================================
        # עריכה
        # =====================================

        if button_id == "edit_order":

            send_edit_menu(phone)

            return "OK", 200


        if button_id == "edit_more":

            send_edit_more(phone)

            return "OK", 200


        if button_id == "edit_pickup":

            SESSIONS[
                phone
            ]["status"] = "edit_pickup"

            send_message(
                phone,
                "שלח את כתובת האיסוף החדשה."
            )

            return "OK", 200


        if button_id == "edit_dropoff":

            SESSIONS[
                phone
            ]["status"] = "edit_dropoff"

            send_message(
                phone,
                "שלח את כתובת המסירה החדשה."
            )

            return "OK", 200


        if button_id == "edit_phone":

            SESSIONS[
                phone
            ]["status"] = "edit_phone"

            send_message(
                phone,
                "שלח את מספר הטלפון החדש."
            )

            return "OK", 200


        if button_id == "edit_time":

            ask_time(phone)

            return "OK", 200


        if button_id == "edit_notes":

            ask_notes(phone)

            return "OK", 200


        # =====================================
        # אריזה
        # =====================================

        if button_id in [
            "package_envelope",
            "package_box",
            "package_other",
        ]:

            if button_id == "package_envelope":
                SESSIONS[
                    phone
                ]["package"] = "מעטפה"

                ask_time(phone)

            elif button_id == "package_box":
                SESSIONS[
                    phone
                ]["package"] = "חבילה"

                ask_time(phone)

            else:
                SESSIONS[
                    phone
                ]["status"] = "package_other"

                send_message(
                    phone,
                    "כתוב בקצרה מה מעבירים."
                )

            return "OK", 200


        # =====================================
        # זמן
        # =====================================

        if button_id == "time_now":

            SESSIONS[
                phone
            ]["delivery_time"] = "עכשיו"

            ask_notes(phone)

            return "OK", 200


        if button_id == "time_today":

            SESSIONS[
                phone
            ]["status"] = "time_today"

            send_message(
                phone,

                "🕐 באיזו שעה היום?\n"
                "לדוגמה: 16:30"
            )

            return "OK", 200


        if button_id == "time_other":

            SESSIONS[
                phone
            ]["status"] = "time_other"

            send_message(
                phone,

                "📅 כתוב תאריך ושעה.\n"
                "לדוגמה:\n"
                "מחר 10:30"
            )

            return "OK", 200


        # =====================================
        # אישור סופי
        # =====================================

        if button_id == "final_confirm":

            confirm_order(phone)

            return "OK", 200


        # =====================================
        # מצב נוכחי
        # =====================================

        session = SESSIONS.get(
            phone,
            {}
        )

        state = session.get(
            "status"
        )


        # =====================================
        # קבלת מיקום
        # =====================================

        if location_text:

            if state in [
                "pickup_address",
                "edit_pickup"
            ]:

                session[
                    "pickup_address"
                ] = location_text

                SESSIONS[phone] = session

                if state == "edit_pickup":
                    send_order_summary(phone)
                else:
                    ask_dropoff(phone)

                return "OK", 200


            if state in [
                "dropoff_address",
                "edit_dropoff"
            ]:

                session[
                    "dropoff_address"
                ] = location_text

                SESSIONS[phone] = session

                if state == "edit_dropoff":
                    send_order_summary(phone)
                else:
                    ask_recipient_name(phone)

                return "OK", 200


            send_message(
                phone,

                "📍 קיבלתי את המיקום.\n"
                "כרגע לא ביקשתי מיקום 🙂"
            )

            return "OK", 200


        # =====================================
        # מעקב לפי מספר הזמנה
        # =====================================

        if state == "tracking":

            order_id = text.strip().upper()

            send_tracking(
                phone,
                order_id
            )

            SESSIONS.pop(
                phone,
                None
            )

            return "OK", 200


        # =====================================
        # שלב כתובת איסוף
        # =====================================

        if state in [
            "pickup_address",
            "edit_pickup"
        ]:

            session[
                "pickup_address"
            ] = text

            if state == "edit_pickup":
                send_order_summary(phone)
            else:
                ask_dropoff(phone)

            return "OK", 200


        # =====================================
        # כתובת מסירה
        # =====================================

        if state in [
            "dropoff_address",
            "edit_dropoff"
        ]:

            session[
                "dropoff_address"
            ] = text

            if state == "edit_dropoff":
                send_order_summary(phone)
            else:
                ask_recipient_name(phone)

            return "OK", 200


        # =====================================
        # שם מקבל
        # =====================================

        if state == "recipient_name":

            session[
                "recipient_name"
            ] = text

            ask_recipient_phone(phone)

            return "OK", 200


        # =====================================
        # טלפון
        # =====================================

        if state in [
            "recipient_phone",
            "edit_phone"
        ]:

            digits = re.sub(
                r"\D",
                "",
                text
            )

            if len(digits) < 9:

                send_message(
                    phone,

                    "המספר נראה קצר מדי 🤔\n"
                    "שלח שוב מספר טלפון מלא."
                )

                return "OK", 200

            session[
                "recipient_phone"
            ] = text

            if state == "edit_phone":
                send_order_summary(phone)
            else:
                ask_package(phone)

            return "OK", 200


        # =====================================
        # סוג חבילה ידני
        # =====================================

        if state == "package_other":

            session[
                "package"
            ] = text

            ask_time(phone)

            return "OK", 200


        # =====================================
        # זמן
        # =====================================

        if state in [
            "time_today",
            "time_other"
        ]:

            session[
                "delivery_time"
            ] = text

            ask_notes(phone)

            return "OK", 200


        # =====================================
        # הערות
        # =====================================

        if state == "notes":

            session[
                "notes"
            ] = text

            send_order_summary(phone)

            return "OK", 200


        # =====================================
        # מילים לנציג
        # =====================================

        agent_words = [
            "נציג",
            "שירות לקוחות",
            "בן אדם",
            "לדבר עם מישהו",
            "לדבר עם נציג",
            "טלפון של נציג",
        ]

        if any(
            word in clean
            for word in agent_words
        ):

            request_agent(
                phone,
                f"הלקוח כתב: {text}"
            )

            return "OK", 200


        # =====================================
        # כן אחרי הצעת מחיר
        # =====================================

        if clean in [
            "כן",
            "להזמין",
            "רוצה להזמין",
            "כן תודה",
            "מאשר",
        ]:

            if state == "quoted":

                start_order(phone)

            else:

                SESSIONS[
                    phone
                ] = {
                    "status":
                        "waiting_route"
                }

                send_message(
                    phone,

                    "מעולה 👍\n"
                    "כתוב את המסלול שלך.\n"
                    "לדוגמה:\n"
                    "ירושלים תל אביב"
                )

            return "OK", 200


        # =====================================
        # ניסיון לזהות מסלול
        # =====================================

        origin, destination = (
            find_route(text)
        )

        if (
            origin
            and destination
        ):

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


        # =====================================
        # אם חיכה למסלול
        # =====================================

        if state == "waiting_route":

            send_message(
                phone,

                "לא הצלחתי לזהות שתי ערים 🤔\n\n"
                "נסה לכתוב רק:\n"
                "ירושלים תל אביב\n\n"
                "או כתוב 'נציג'."
            )

            return "OK", 200


        # =====================================
        # לא הבין
        # =====================================

        handle_unknown(phone)

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
