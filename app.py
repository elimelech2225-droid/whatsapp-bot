from flask import Flask, request
import requests
import os
import re
import time
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

# =========================================================
# הגדרות
# =========================================================

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "972553155049")

GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v23.0"
)

DB_PATH = os.environ.get(
    "DB_PATH",
    "bot.db"
)


# =========================================================
# מחירון
# =========================================================

PRICES = {
    ("ירושלים", "תל אביב"): 240,
    ("בית שמש", "תל אביב"): 220,

    # המחיר שתיקנת
    ("ירושלים", "בית שמש"): 150,

    ("ירושלים", "עמנואל"): 350,
    ("בית שמש", "עמנואל"): 350,
    ("עמנואל", "בני ברק"): 250,
    ("ראש העין", "ירושלים"): 220,
    ("ירושלים", "אלעד"): 220,
    ("ירושלים", "בני ברק"): 220,
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
    "תלאביב": "תל אביב",
    "תל-אביב": "תל אביב",

    'פ"ת': "פתח תקווה",
    "פ״ת": "פתח תקווה",
    "פתח תקוה": "פתח תקווה",

    'ראשל"צ': "ראשון לציון",
    "ראשלצ": "ראשון לציון",
    "רשלצ": "ראשון לציון",

    "ירושליים": "ירושלים",
    "ביתשמש": "בית שמש",
    "בניברק": "בני ברק",
    "ראשהעין": "ראש העין",
}


# =========================================================
# סטטוסים
# =========================================================

STATUS_TEXT = {
    "waiting_driver": "🔎 מחפשים שליח",
    "driver_assigned": "🚚 נמצא שליח",
    "on_way_pickup": "🚗 השליח בדרך לאיסוף",
    "picked_up": "📦 המשלוח נאסף",
    "on_way_destination": "🛣️ המשלוח בדרך ליעד",
    "delivered": "✅ המשלוח נמסר",
    "cancel_requested": "⏳ בקשת הביטול הועברה לנציג",
    "cancelled": "❌ המשלוח בוטל",
}

ADMIN_STATUS = {
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
# זיהוי הודעות חכמות
# =========================================================

GREETING_PHRASES = [
    "היי",
    "הי",
    "שלום",
    "אהלן",
    "הלו",
    "בוקר טוב",
    "צהריים טובים",
    "ערב טוב",
    "hi",
    "hello",
]

MENU_PHRASES = [
    "תפריט",
    "תפריט ראשי",
    "ראשי",
    "אפשרויות",
    "מה אפשר לעשות",
    "עזרה",
]

AGENT_PHRASES = [
    "נציג",
    "נציג שירות",
    "שירות לקוחות",
    "בן אדם",
    "מישהו אמיתי",
    "נציג אנושי",
    "לדבר עם נציג",
    "לדבר עם מישהו",
    "רוצה נציג",
    "תעביר לנציג",
    "תעביר אותי לנציג",
]

BACK_TO_BOT_PHRASES = [
    "חזרה לבוט",
    "תחזיר לבוט",
    "תחזיר אותי לבוט",
    "חזרה לתפריט",
]

CANCEL_PHRASES = [
    "ביטול",
    "לבטל",
    "בטל",
    "תבטל",
    "תבטלו",
    "אפשר לבטל",
    "רוצה לבטל",

    "לא צריך",
    "לא צריך משלוח",
    "אני לא צריך",
    "אני לא צריך משלוח",

    "בסוף לא",
    "בסוף לא צריך",
    "בסוף אני לא צריך",

    "עזוב",
    "עזבו",
    "עזוב את זה",

    "לא משנה",
    "לא רלוונטי",
    "כבר לא רלוונטי",

    "מצאתי שליח",
    "מצאתי שליח אחר",

    "הסתדרתי",
    "כבר הסתדרתי",

    "לא רוצה",
    "אני לא רוצה",
    "לא מעוניין",

    "תוותר",
    "וותר",
]

THANKS_PHRASES = [
    "תודה",
    "תודה רבה",
    "מעולה תודה",
    "סבבה תודה",
    "אחלה תודה",
]

PRICE_PHRASES = [
    "מחיר",
    "כמה עולה",
    "כמה זה עולה",
    "כמה יעלה",
    "עלות",
    "בדיקת מחיר",
    "מחירון",
]

TRACK_PHRASES = [
    "מעקב",
    "איפה המשלוח",
    "איפה השליח",
    "מה עם המשלוח",
    "סטטוס משלוח",
    "בדיקת משלוח",
]

NEW_DELIVERY_PHRASES = [
    "משלוח חדש",
    "רוצה משלוח",
    "צריך משלוח",
    "להזמין משלוח",
    "הזמנת משלוח",
    "אני צריך שליח",
    "צריך שליח",
]

URGENT_PHRASES = [
    "דחוף",
    "משלוח דחוף",
    "כמה שיותר מהר",
    "עכשיו דחוף",
]


# =========================================================
# בסיס נתונים
# =========================================================

def now_ts():
    return int(time.time())


def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=15
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with db() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                phone TEXT PRIMARY KEY,
                human_mode INTEGER DEFAULT 0,
                last_seen INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                phone TEXT PRIMARY KEY,
                state TEXT DEFAULT '',
                origin TEXT DEFAULT '',
                destination TEXT DEFAULT '',
                price INTEGER,
                urgent INTEGER DEFAULT 0,
                pickup_address TEXT DEFAULT '',
                dropoff_address TEXT DEFAULT '',
                recipient_name TEXT DEFAULT '',
                recipient_phone TEXT DEFAULT '',
                package TEXT DEFAULT '',
                delivery_time TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                misunderstandings INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                customer_phone TEXT NOT NULL,

                status TEXT NOT NULL
                    DEFAULT 'waiting_driver',

                origin TEXT DEFAULT '',
                destination TEXT DEFAULT '',

                price INTEGER,

                urgent INTEGER DEFAULT 0,

                pickup_address TEXT DEFAULT '',
                dropoff_address TEXT DEFAULT '',

                recipient_name TEXT DEFAULT '',
                recipient_phone TEXT DEFAULT '',

                package TEXT DEFAULT '',
                delivery_time TEXT DEFAULT '',
                notes TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                created_at INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_orders_phone_status

            ON orders(
                customer_phone,
                status,
                created_at DESC
            )
            """
        )


init_db()


# =========================================================
# כלי עזר
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    for symbol in [
        "→",
        "->",
        "–",
        "-",
        ",",
        "/",
        "|",
        ".",
        "!",
        "?",
    ]:

        text = text.replace(
            symbol,
            " "
        )

    for alias, city in sorted(
        CITY_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    ):

        text = text.replace(
            alias.lower(),
            city.lower()
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def phrase_matches(
    text,
    phrases
):

    clean = normalize_text(
        text
    )

    for phrase in phrases:

        phrase_clean = normalize_text(
            phrase
        )

        if clean == phrase_clean:
            return True

        if (
            len(phrase_clean) >= 5
            and phrase_clean in clean
        ):
            return True

    return False


def clean_phone(text):

    digits = re.sub(
        r"\D",
        "",
        text or ""
    )

    if digits.startswith("0"):

        return (
            "972"
            + digits[1:]
        )

    return digits


def display_phone(phone):

    if phone.startswith("972"):

        return (
            "0"
            + phone[3:]
        )

    return phone


# =========================================================
# לקוחות
# =========================================================

def customer_touch(phone):

    with db() as conn:

        conn.execute(
            """
            INSERT INTO customers(
                phone,
                last_seen
            )

            VALUES(
                ?,
                ?
            )

            ON CONFLICT(phone)
            DO UPDATE SET
                last_seen=excluded.last_seen
            """,

            (
                phone,
                now_ts()
            )
        )


def get_human_mode(phone):

    with db() as conn:

        row = conn.execute(
            """
            SELECT human_mode
            FROM customers
            WHERE phone=?
            """,

            (
                phone,
            )
        ).fetchone()

    if not row:
        return False

    return bool(
        row["human_mode"]
    )


def set_human_mode(
    phone,
    enabled
):

    customer_touch(
        phone
    )

    with db() as conn:

        conn.execute(
            """
            UPDATE customers
            SET human_mode=?
            WHERE phone=?
            """,

            (
                1 if enabled else 0,
                phone
            )
        )


# =========================================================
# מצב השיחה
# =========================================================

def get_session(phone):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE phone=?
            """,

            (
                phone,
            )
        ).fetchone()

    if not row:
        return {}

    return dict(row)


def save_session(
    phone,
    **fields
):

    current = get_session(
        phone
    )

    data = {
        "state":
            current.get(
                "state",
                ""
            ),

        "origin":
            current.get(
                "origin",
                ""
            ),

        "destination":
            current.get(
                "destination",
                ""
            ),

        "price":
            current.get(
                "price"
            ),

        "urgent":
            current.get(
                "urgent",
                0
            ),

        "pickup_address":
            current.get(
                "pickup_address",
                ""
            ),

        "dropoff_address":
            current.get(
                "dropoff_address",
                ""
            ),

        "recipient_name":
            current.get(
                "recipient_name",
                ""
            ),

        "recipient_phone":
            current.get(
                "recipient_phone",
                ""
            ),

        "package":
            current.get(
                "package",
                ""
            ),

        "delivery_time":
            current.get(
                "delivery_time",
                ""
            ),

        "notes":
            current.get(
                "notes",
                ""
            ),

        "misunderstandings":
            current.get(
                "misunderstandings",
                0
            ),

        "updated_at":
            now_ts(),
    }

    data.update(
        fields
    )

    with db() as conn:

        conn.execute(
            """
            INSERT INTO sessions(
                phone,
                state,
                origin,
                destination,
                price,
                urgent,
                pickup_address,
                dropoff_address,
                recipient_name,
                recipient_phone,
                package,
                delivery_time,
                notes,
                misunderstandings,
                updated_at
            )

            VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )

            ON CONFLICT(phone)
            DO UPDATE SET

                state=excluded.state,

                origin=excluded.origin,
                destination=excluded.destination,

                price=excluded.price,
                urgent=excluded.urgent,

                pickup_address=
                    excluded.pickup_address,

                dropoff_address=
                    excluded.dropoff_address,

                recipient_name=
                    excluded.recipient_name,

                recipient_phone=
                    excluded.recipient_phone,

                package=
                    excluded.package,

                delivery_time=
                    excluded.delivery_time,

                notes=
                    excluded.notes,

                misunderstandings=
                    excluded.misunderstandings,

                updated_at=
                    excluded.updated_at
            """,

            (
                phone,

                data["state"],

                data["origin"],
                data["destination"],

                data["price"],
                data["urgent"],

                data["pickup_address"],
                data["dropoff_address"],

                data["recipient_name"],
                data["recipient_phone"],

                data["package"],
                data["delivery_time"],
                data["notes"],

                data["misunderstandings"],
                data["updated_at"],
            )
        )


def clear_session(phone):

    with db() as conn:

        conn.execute(
            """
            DELETE FROM sessions
            WHERE phone=?
            """,

            (
                phone,
            )
        )


# =========================================================
# משלוחים
# =========================================================

def active_orders(phone):

    statuses = (
        "waiting_driver",
        "driver_assigned",
        "on_way_pickup",
        "picked_up",
        "on_way_destination",
        "cancel_requested",
    )

    placeholders = ",".join(
        ["?"]
        * len(statuses)
    )

    with db() as conn:

        rows = conn.execute(
            f"""
            SELECT *
            FROM orders

            WHERE customer_phone=?

            AND status IN (
                {placeholders}
            )

            ORDER BY created_at DESC
            """,

            (
                phone,
                *statuses
            )
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def last_completed_order(phone):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM orders

            WHERE customer_phone=?

            AND status IN(
                'delivered',
                'cancelled'
            )

            ORDER BY created_at DESC

            LIMIT 1
            """,

            (
                phone,
            )
        ).fetchone()

    if not row:
        return None

    return dict(row)


# =========================================================
# מניעת הודעה כפולה
# =========================================================

def is_duplicate(
    message_id
):

    if not message_id:
        return False

    with db() as conn:

        conn.execute(
            """
            DELETE FROM processed_messages
            WHERE created_at < ?
            """,

            (
                now_ts()
                - 86400,
            )
        )

        row = conn.execute(
            """
            SELECT 1
            FROM processed_messages
            WHERE message_id=?
            """,

            (
                message_id,
            )
        ).fetchone()

        if row:
            return True

        conn.execute(
            """
            INSERT INTO processed_messages(
                message_id,
                created_at
            )

            VALUES(
                ?,
                ?
            )
            """,

            (
                message_id,
                now_ts()
            )
        )

    return False


# =========================================================
# שליחה לוואטסאפ
# =========================================================

def api_url():

    return (
        "https://graph.facebook.com/"
        f"{GRAPH_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


def send_payload(payload):

    if (
        not ACCESS_TOKEN
        or not PHONE_NUMBER_ID
    ):

        print(
            "ERROR: missing WhatsApp credentials"
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


def send_message(
    phone,
    text
):

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

    items = []

    for (
        button_id,
        title
    ) in buttons[:3]:

        items.append({
            "type":
                "reply",

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
                    items
            }
        }
    })


# =========================================================
# תפריט
# =========================================================

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
                "my_delivery",
                "🚚 המשלוח שלי"
            ),
        ]
    )


def send_more_menu(phone):

    send_buttons(
        phone,

        "אפשרויות נוספות:",

        [
            (
                "repeat_delivery",
                "🔁 משלוח חוזר"
            ),

            (
                "talk_to_agent",
                "👤 דבר עם נציג"
            ),

            (
                "cancel_action",
                "❌ ביטול"
            ),
        ]
    )


# =========================================================
# פתיחה חכמה
# =========================================================

def send_welcome(phone):

    orders = active_orders(
        phone
    )

    if orders:

        amount = len(
            orders
        )

        send_message(
            phone,

            "👋 ברוכים הביא ל-א.א שליחויות והפצה\n\n"

            f"זיהיתי שכבר יש לך "
            f"{amount} "
            f"משלוח"
            f"{'ים' if amount > 1 else ''} "
            f"פעיל"
            f"{'ים' if amount > 1 else ''}."
        )

        send_buttons(
            phone,

            "מה תרצה לעשות עכשיו?",

            [
                (
                    "another_delivery",
                    "➕ משלוח נוסף"
                ),

                (
                    "my_delivery",
                    "🚚 המשלוח שלי"
                ),

                (
                    "more_options",
                    "⚙️ אפשרויות"
                ),
            ]
        )

        return

    send_message(
        phone,

        "👋 ברוכים הביא ל-א.א שליחויות והפצה\n\n"

        "אני כאן כדי לעזור לך לבדוק מחיר, "
        "להזמין משלוח ולעקוב אחרי משלוח קיים."
    )

    send_main_menu(
        phone
    )


# =========================================================
# מצב נציג
# =========================================================

def request_agent(
    phone,
    reason
):

    set_human_mode(
        phone,
        True
    )

    send_message(
        phone,

        "✅ העברתי את הפנייה לנציג אנושי 👤\n\n"

        "הבוט לא יתערב כרגע בשיחה.\n"

        "כדי לחזור לשירות האוטומטי כתוב:\n"
        "חזרה לבוט"
    )

    send_message(
        ADMIN_PHONE,

        "👤 בקשת נציג\n\n"

        f"📱 לקוח: "
        f"{display_phone(phone)}\n"

        f"📝 סיבה: "
        f"{reason}"
    )


# =========================================================
# מסלול
# =========================================================

def find_route(text):

    clean = normalize_text(
        text
    )

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

    found.sort()

    unique = []

    for _, city in found:

        if city not in unique:

            unique.append(
                city
            )

    if len(unique) < 2:

        return (
            None,
            None
        )

    return (
        unique[0],
        unique[1]
    )


def get_price(
    origin,
    destination
):

    return PRICES.get(
        (
            origin,
            destination
        ),

        PRICES.get(
            (
                destination,
                origin
            )
        )
    )


# =========================================================
# הצעת מחיר
# =========================================================

def send_quote(
    phone,
    origin,
    destination,
    price,
    urgent=False
):

    save_session(
        phone,

        state=
            "quoted",

        origin=
            origin,

        destination=
            destination,

        price=
            price,

        urgent=
            1 if urgent else 0,

        misunderstandings=
            0
    )

    urgent_text = ""

    if urgent:

        urgent_text = (
            "\n⚡ המשלוח סומן כדחוף."
        )

    send_buttons(
        phone,

        "🚚 קיבלתי את המסלול.\n\n"

        f"📍 {origin} → {destination}\n"

        f"💰 מחיר: {price} ₪"
        f"{urgent_text}\n\n"

        "רוצה לבצע את המשלוח?",

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
                "cancel_action",
                "❌ לא כרגע"
            ),
        ]
    )


# =========================================================
# שלבי הזמנה
# =========================================================

def start_order(phone):

    session = get_session(
        phone
    )

    save_session(
        phone,

        state=
            "pickup_address",

        origin=
            session.get(
                "origin",
                ""
            ),

        destination=
            session.get(
                "destination",
                ""
            ),

        price=
            session.get(
                "price"
            ),

        urgent=
            session.get(
                "urgent",
                0
            )
    )

    send_message(
        phone,

        "📍 מאיפה אוספים?\n\n"

        "שלח עיר, רחוב ומספר בית.\n"

        "אפשר גם לשלוח מיקום מוואטסאפ."
    )


def ask_dropoff(phone):

    save_session(
        phone,
        state="dropoff_address"
    )

    send_message(
        phone,

        "📍 ולאן מוסרים?\n\n"

        "שלח עיר, רחוב ומספר בית.\n"

        "אפשר גם לשלוח מיקום."
    )


def ask_recipient_name(phone):

    save_session(
        phone,
        state="recipient_name"
    )

    send_message(
        phone,

        "👤 מה השם של האדם שמקבל את המשלוח?"
    )


def ask_recipient_phone(phone):

    save_session(
        phone,
        state="recipient_phone"
    )

    send_message(
        phone,

        "📞 מה מספר הטלפון של המקבל?"
    )


def ask_package(phone):

    save_session(
        phone,
        state="package"
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

    save_session(
        phone,
        state="delivery_time"
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

    save_session(
        phone,
        state="notes"
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
# סיכום
# =========================================================

def send_order_summary(phone):

    session = get_session(
        phone
    )

    urgent_text = ""

    if session.get(
        "urgent"
    ):

        urgent_text = (
            "\n⚡ דחוף"
        )

    price_text = ""

    if (
        session.get(
            "price"
        )
        is not None
    ):

        price_text = (
            f"\n💰 מחיר: "
            f"{session.get('price')} ₪"
        )

    text = (
        "📋 סיכום המשלוח\n\n"

        f"📍 איסוף: "
        f"{session.get('pickup_address') or '-'}\n"

        f"📍 מסירה: "
        f"{session.get('dropoff_address') or '-'}\n"

        f"👤 מקבל: "
        f"{session.get('recipient_name') or '-'}\n"

        f"📞 טלפון: "
        f"{session.get('recipient_phone') or '-'}\n"

        f"📦 מה שולחים: "
        f"{session.get('package') or '-'}\n"

        f"🕐 מועד: "
        f"{session.get('delivery_time') or '-'}\n"

        f"📝 הערות: "
        f"{session.get('notes') or '-'}"

        f"{price_text}"
        f"{urgent_text}\n\n"

        "הכול נכון?"
    )

    save_session(
        phone,
        state="confirmation"
    )

    send_buttons(
        phone,

        text,

        [
            (
                "final_confirm",
                "✅ אשר משלוח"
            ),

            (
                "edit_order",
                "✏️ שנה פרטים"
            ),

            (
                "cancel_action",
                "❌ ביטול"
            ),
        ]
    )


# =========================================================
# אישור סופי
# =========================================================

def confirm_order(phone):

    session = get_session(
        phone
    )

    with db() as conn:

        conn.execute(
            """
            INSERT INTO orders(
                customer_phone,
                status,

                origin,
                destination,

                price,
                urgent,

                pickup_address,
                dropoff_address,

                recipient_name,
                recipient_phone,

                package,
                delivery_time,
                notes,

                created_at,
                updated_at
            )

            VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,

            (
                phone,

                "waiting_driver",

                session.get(
                    "origin",
                    ""
                ),

                session.get(
                    "destination",
                    ""
                ),

                session.get(
                    "price"
                ),

                session.get(
                    "urgent",
                    0
                ),

                session.get(
                    "pickup_address",
                    ""
                ),

                session.get(
                    "dropoff_address",
                    ""
                ),

                session.get(
                    "recipient_name",
                    ""
                ),

                session.get(
                    "recipient_phone",
                    ""
                ),

                session.get(
                    "package",
                    ""
                ),

                session.get(
                    "delivery_time",
                    ""
                ),

                session.get(
                    "notes",
                    ""
                ),

                now_ts(),
                now_ts()
            )
        )

    clear_session(
        phone
    )

    send_message(
        phone,

        "✅ המשלוח נקלט בהצלחה!\n\n"

        "🔎 כרגע אנחנו מחפשים שליח.\n"

        "נעדכן אותך כשהסטטוס ישתנה."
    )

    admin_text = (
        "📦 משלוח חדש!\n\n"

        f"📱 לקוח: "
        f"{display_phone(phone)}\n"

        f"📍 איסוף: "
        f"{session.get('pickup_address', '-')}\n"

        f"📍 מסירה: "
        f"{session.get('dropoff_address', '-')}\n"

        f"👤 מקבל: "
        f"{session.get('recipient_name', '-')}\n"

        f"📞 טלפון: "
        f"{session.get('recipient_phone', '-')}\n"

        f"📦 תוכן: "
        f"{session.get('package', '-')}\n"

        f"🕐 מועד: "
        f"{session.get('delivery_time', '-')}\n"

        f"📝 הערות: "
        f"{session.get('notes', '-')}\n"

        f"💰 מחיר: "
        f"{session.get('price') if session.get('price') is not None else 'לא נקבע'}"
    )

    if session.get(
        "urgent"
    ):

        admin_text += (
            "\n⚡ דחוף"
        )

    send_message(
        ADMIN_PHONE,
        admin_text
    )


# =========================================================
# הצגת משלוחים פעילים
# =========================================================

def send_my_deliveries(phone):

    orders = active_orders(
        phone
    )

    if not orders:

        send_message(
            phone,

            "כרגע אין לך משלוח פעיל 🙂"
        )

        send_main_menu(
            phone
        )

        return

    if len(orders) == 1:

        order = orders[0]

        send_message(
            phone,

            "🚚 המשלוח הפעיל שלך\n\n"

            f"{STATUS_TEXT.get(order['status'], order['status'])}\n"

            f"📍 איסוף: "
            f"{order['pickup_address'] or order['origin'] or '-'}\n"

            f"📍 מסירה: "
            f"{order['dropoff_address'] or order['destination'] or '-'}"
        )

        send_buttons(
            phone,

            "מה תרצה לעשות?",

            [
                (
                    "another_delivery",
                    "➕ משלוח נוסף"
                ),

                (
                    "cancel_active",
                    "❌ בקש ביטול"
                ),

                (
                    "more_options",
                    "⚙️ אפשרויות"
                ),
            ]
        )

        return

    lines = [
        f"יש לך {len(orders)} משלוחים פעילים:"
    ]

    for index, order in enumerate(
        orders[:5],
        1
    ):

        pickup = (
            order["pickup_address"]
            or order["origin"]
            or "איסוף"
        )

        dropoff = (
            order["dropoff_address"]
            or order["destination"]
            or "מסירה"
        )

        lines.append(
            f"\n{index}. "
            f"{STATUS_TEXT.get(order['status'], order['status'])}\n"
            f"{pickup} → {dropoff}"
        )

    lines.append(
        "\n\nכדי לבדוק משלוח מסוים, "
        "כתוב את המספר שלו ברשימה: 1, 2, 3..."
    )

    save_session(
        phone,
        state="choose_active_order"
    )

    send_message(
        phone,
        "\n".join(lines)
    )


# =========================================================
# ביטול משלוח פעיל
# =========================================================

def request_cancel_active(phone):

    orders = active_orders(
        phone
    )

    if not orders:

        send_message(
            phone,

            "אין כרגע משלוח פעיל לביטול."
        )

        return

    if len(orders) > 1:

        send_my_deliveries(
            phone
        )

        send_message(
            phone,

            "כתוב איזה משלוח תרצה לבטל "
            "לפי המספר ברשימה."
        )

        save_session(
            phone,
            state="choose_cancel_order"
        )

        return

    order = orders[0]

    with db() as conn:

        conn.execute(
            """
            UPDATE orders

            SET
                status='cancel_requested',
                updated_at=?

            WHERE id=?
            """,

            (
                now_ts(),
                order["id"]
            )
        )

    send_message(
        phone,

        "⏳ בקשת הביטול נשלחה לנציג.\n"

        "המשלוח לא מבוטל סופית "
        "עד שנציג מאשר."
    )

    send_message(
        ADMIN_PHONE,

        "🚨 בקשת ביטול משלוח\n\n"

        f"📱 לקוח: "
        f"{display_phone(phone)}\n"

        f"📍 "
        f"{order['pickup_address']} "
        f"→ "
        f"{order['dropoff_address']}"
    )


# =========================================================
# משלוח חוזר
# =========================================================

def repeat_last_delivery(phone):

    previous = last_completed_order(
        phone
    )

    if not previous:

        send_message(
            phone,

            "עדיין אין משלוח קודם "
            "שאפשר לשחזר."
        )

        return

    save_session(
        phone,

        state=
            "recipient_name",

        origin=
            previous.get(
                "origin",
                ""
            ),

        destination=
            previous.get(
                "destination",
                ""
            ),

        price=
            previous.get(
                "price"
            ),

        urgent=
            0,

        pickup_address=
            previous.get(
                "pickup_address",
                ""
            ),

        dropoff_address=
            previous.get(
                "dropoff_address",
                ""
            ),

        package=
            previous.get(
                "package",
                ""
            ),
    )

    send_message(
        phone,

        "🔁 העתקתי את כתובות המשלוח הקודם.\n"

        "נבדוק מחדש את פרטי המקבל."
    )

    ask_recipient_name(
        phone
    )


# =========================================================
# לא הבין
# =========================================================

def handle_unknown(phone):

    session = get_session(
        phone
    )

    count = (
        int(
            session.get(
                "misunderstandings",
                0
            )
        )
        + 1
    )

    save_session(
        phone,
        misunderstandings=count
    )

    if count >= 2:

        save_session(
            phone,
            misunderstandings=0
        )

        send_buttons(
            phone,

            "לא הצלחתי להבין אותך מספיק טוב 🙂\n"

            "בחר מה תרצה לעשות:",

            [
                (
                    "new_delivery",
                    "📦 משלוח חדש"
                ),

                (
                    "my_delivery",
                    "🚚 המשלוח שלי"
                ),

                (
                    "talk_to_agent",
                    "👤 נציג"
                ),
            ]
        )

        return

    send_message(
        phone,

        "לא לגמרי הבנתי 🙂\n\n"

        "אפשר לכתוב למשל:\n"

        "• כמה עולה ירושלים תל אביב\n"
        "• אני צריך משלוח\n"
        "• מה עם המשלוח שלי\n"
        "• בסוף לא צריך\n"
        "• נציג"
    )


# =========================================================
# פקודת מנהל
# =========================================================

def handle_admin_command(
    phone,
    text
):

    match = re.match(
        r"^סטטוס\s+"
        r"(\+?\d[\d\-\s]+)\s+(.+)$",

        text.strip()
    )

    if not match:

        return False

    customer_phone = clean_phone(
        match.group(1)
    )

    status_name = (
        match.group(2)
        .strip()
    )

    status_code = ADMIN_STATUS.get(
        status_name
    )

    if not status_code:

        send_message(
            phone,

            "לא זיהיתי סטטוס.\n\n"

            "אפשר:\n"

            "מחפשים שליח\n"
            "נמצא שליח\n"
            "בדרך לאיסוף\n"
            "נאסף\n"
            "בדרך ליעד\n"
            "נמסר\n"
            "בוטל"
        )

        return True

    orders = active_orders(
        customer_phone
    )

    if not orders:

        send_message(
            phone,

            "לא מצאתי משלוח פעיל "
            "ללקוח הזה."
        )

        return True

    order = orders[0]

    with db() as conn:

        conn.execute(
            """
            UPDATE orders

            SET
                status=?,
                updated_at=?

            WHERE id=?
            """,

            (
                status_code,
                now_ts(),
                order["id"]
            )
        )

    send_message(
        phone,

        "✅ הסטטוס עודכן ללקוח "
        f"{display_phone(customer_phone)}:\n"

        f"{STATUS_TEXT.get(status_code, status_code)}"
    )

    send_message(
        customer_phone,

        "🔔 עדכון לגבי המשלוח שלך\n\n"

        f"{STATUS_TEXT.get(status_code, status_code)}"
    )

    return True


# =========================================================
# מיקום
# =========================================================

def location_to_text(
    location
):

    latitude = location.get(
        "latitude"
    )

    longitude = location.get(
        "longitude"
    )

    if (
        latitude is None
        or longitude is None
    ):

        return ""

    return (
        "https://maps.google.com/?q="
        f"{latitude},{longitude}"
    )


# =========================================================
# דף בדיקה
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

        return (
            challenge,
            200
        )

    return (
        "Verification failed",
        403
    )


# =========================================================
# Webhook
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

        entries = data.get(
            "entry",
            []
        )

        if not entries:
            return "OK", 200

        changes = (
            entries[0]
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

        if "messages" not in value:

            return "OK", 200

        messages = value.get(
            "messages",
            []
        )

        if not messages:

            return "OK", 200

        message = messages[0]

        if is_duplicate(
            message.get("id")
        ):

            return "OK", 200

        phone = message.get(
            "from"
        )

        if not phone:

            return "OK", 200

        customer_touch(
            phone
        )

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
                interactive.get(
                    "type"
                )
                == "button_reply"
            ):

                button = (
                    interactive.get(
                        "button_reply",
                        {}
                    )
                )

                button_id = (
                    button.get(
                        "id"
                    )
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

            location_text = (
                location_to_text(
                    message.get(
                        "location",
                        {}
                    )
                )
            )


        else:

            send_message(
                phone,

                "כרגע אפשר לשלוח לי "
                "טקסט או מיקום 📍"
            )

            return "OK", 200


        clean = normalize_text(
            text
        )


        # =====================================
        # מנהל
        # =====================================

        if (
            phone == ADMIN_PHONE
            and text
            and handle_admin_command(
                phone,
                text
            )
        ):

            return "OK", 200


        # =====================================
        # חזרה מבוט לנציג
        # =====================================

        if phrase_matches(
            text,
            BACK_TO_BOT_PHRASES
        ):

            set_human_mode(
                phone,
                False
            )

            send_message(
                phone,

                "🤖 חזרנו לשירות האוטומטי."
            )

            send_main_menu(
                phone
            )

            return "OK", 200


        # =====================================
        # נציג אנושי מטפל
        # =====================================

        if get_human_mode(
            phone
        ):

            return "OK", 200


        # =====================================
        # בקשת נציג
        # =====================================

        if (
            phrase_matches(
                text,
                AGENT_PHRASES
            )
            or button_id
                == "talk_to_agent"
        ):

            request_agent(
                phone,

                f"הלקוח כתב: {text}"
            )

            return "OK", 200


        # =====================================
        # פתיחה
        # =====================================

        if phrase_matches(
            text,
            GREETING_PHRASES
        ):

            send_welcome(
                phone
            )

            return "OK", 200


        # =====================================
        # תפריט
        # =====================================

        if (
            phrase_matches(
                text,
                MENU_PHRASES
            )
            or button_id
                == "main_menu"
        ):

            send_main_menu(
                phone
            )

            return "OK", 200


        if button_id == "more_options":

            send_more_menu(
                phone
            )

            return "OK", 200


        # =====================================
        # פתיחת משלוח חדש
        # =====================================

        if (
            button_id in (
                "new_delivery",
                "another_delivery"
            )
            or phrase_matches(
                text,
                NEW_DELIVERY_PHRASES
            )
        ):

            orders = active_orders(
                phone
            )

            # אם כבר יש משלוח פעיל
            if (
                orders
                and button_id
                    != "another_delivery"
            ):

                amount = len(
                    orders
                )

                send_buttons(
                    phone,

                    f"כבר יש לך "
                    f"{amount} "
                    f"משלוח"
                    f"{'ים' if amount > 1 else ''} "
                    f"פעיל"
                    f"{'ים' if amount > 1 else ''}.\n\n"

                    "רוצה לפתוח משלוח נוסף?",

                    [
                        (
                            "another_delivery",
                            "➕ כן, נוסף"
                        ),

                        (
                            "my_delivery",
                            "🚚 בדוק קיים"
                        ),

                        (
                            "more_options",
                            "⚙️ אפשרויות"
                        ),
                    ]
                )

                return "OK", 200


            save_session(
                phone,

                state=
                    "waiting_route",

                urgent=
                    0,

                misunderstandings=
                    0
            )

            send_message(
                phone,

                "📦 מצוין.\n\n"

                "כתוב לי את המסלול, למשל:\n"

                "ירושלים תל אביב"
            )

            return "OK", 200


        # =====================================
        # בדיקת מחיר
        # =====================================

        if (
            button_id
                == "check_price"

            or phrase_matches(
                text,
                PRICE_PHRASES
            )
        ):

            origin, destination = (
                find_route(
                    text
                )
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

                    send_message(
                        phone,

                        f"📍 {origin} → {destination}\n\n"

                        "אין מחיר אוטומטי למסלול הזה.\n"

                        "העברתי בקשת מחיר לנציג."
                    )

                    send_message(
                        ADMIN_PHONE,

                        "💰 בקשת מחיר\n\n"

                        f"📱 "
                        f"{display_phone(phone)}\n"

                        f"📍 "
                        f"{origin} → {destination}"
                    )

                return "OK", 200


            save_session(
                phone,
                state="waiting_route"
            )

            send_message(
                phone,

                "💰 איזה מסלול תרצה לבדוק?\n"

                "לדוגמה:\n"

                "ירושלים תל אביב"
            )

            return "OK", 200


        # =====================================
        # המשלוח שלי
        # =====================================

        if (
            button_id
                == "my_delivery"

            or phrase_matches(
                text,
                TRACK_PHRASES
            )
        ):

            send_my_deliveries(
                phone
            )

            return "OK", 200


        # =====================================
        # משלוח חוזר
        # =====================================

        if button_id == "repeat_delivery":

            repeat_last_delivery(
                phone
            )

            return "OK", 200


        # =====================================
        # ביטול משלוח קיים
        # =====================================

        if button_id == "cancel_active":

            request_cancel_active(
                phone
            )

            return "OK", 200


        # =====================================
        # ביטול חכם
        # =====================================

        if (
            phrase_matches(
                text,
                CANCEL_PHRASES
            )
            or button_id
                == "cancel_action"
        ):

            session = get_session(
                phone
            )

            if session:

                clear_session(
                    phone
                )

                send_message(
                    phone,

                    "✅ אין בעיה, "
                    "ביטלתי את הפעולה הנוכחית.\n"

                    "לא נוצר משלוח חדש."
                )

            elif active_orders(
                phone
            ):

                request_cancel_active(
                    phone
                )

            else:

                send_message(
                    phone,

                    "אין כרגע פעולה או "
                    "משלוח פתוח לביטול 🙂"
                )

            return "OK", 200


        # =====================================
        # תודה
        # =====================================

        if phrase_matches(
            text,
            THANKS_PHRASES
        ):

            send_message(
                phone,

                "בשמחה 🙏\n"

                "תודה שבחרת בא.א שליחויות והפצה."
            )

            return "OK", 200


        # =====================================
        # אישור הצעת מחיר
        # =====================================

        if button_id == "confirm_delivery":

            start_order(
                phone
            )

            return "OK", 200


        # =====================================
        # דחוף
        # =====================================

        if (
            button_id
                == "urgent_delivery"

            or phrase_matches(
                text,
                URGENT_PHRASES
            )
        ):

            session = get_session(
                phone
            )

            if (
                session.get(
                    "state"
                )
                == "quoted"
            ):

                save_session(
                    phone,
                    urgent=1
                )

                send_message(
                    phone,

                    "⚡ סימנתי את המשלוח כדחוף."
                )

                start_order(
                    phone
                )

            else:

                save_session(
                    phone,

                    state=
                        "waiting_route",

                    urgent=
                        1
                )

                send_message(
                    phone,

                    "⚡ קיבלתי.\n"

                    "כתוב את המסלול של "
                    "המשלוח הדחוף."
                )

            return "OK", 200


        # =====================================
        # סוג חבילה
        # =====================================

        if button_id == "package_envelope":

            save_session(
                phone,
                package="מעטפה"
            )

            ask_time(
                phone
            )

            return "OK", 200


        if button_id == "package_box":

            save_session(
                phone,
                package="חבילה"
            )

            ask_time(
                phone
            )

            return "OK", 200


        if button_id == "package_other":

            save_session(
                phone,
                state="package_other"
            )

            send_message(
                phone,

                "📝 כתוב בקצרה מה מעבירים."
            )

            return "OK", 200


        # =====================================
        # זמן
        # =====================================

        if button_id == "time_now":

            save_session(
                phone,
                delivery_time="עכשיו"
            )

            ask_notes(
                phone
            )

            return "OK", 200


        if button_id == "time_today":

            save_session(
                phone,
                state="time_today"
            )

            send_message(
                phone,

                "🕐 באיזו שעה היום?\n"

                "לדוגמה: 16:30"
            )

            return "OK", 200


        if button_id == "time_other":

            save_session(
                phone,
                state="time_other"
            )

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

            confirm_order(
                phone
            )

            return "OK", 200


        # =====================================
        # עריכת הזמנה
        # =====================================

        if button_id == "edit_order":

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

            return "OK", 200


        if button_id == "edit_pickup":

            save_session(
                phone,
                state="edit_pickup"
            )

            send_message(
                phone,

                "שלח את כתובת האיסוף החדשה."
            )

            return "OK", 200


        if button_id == "edit_dropoff":

            save_session(
                phone,
                state="edit_dropoff"
            )

            send_message(
                phone,

                "שלח את כתובת המסירה החדשה."
            )

            return "OK", 200


        if button_id == "edit_more":

            send_buttons(
                phone,

                "מה תרצה לשנות?",

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

            return "OK", 200


        if button_id == "edit_phone":

            save_session(
                phone,
                state="edit_phone"
            )

            send_message(
                phone,

                "שלח את מספר הטלפון החדש."
            )

            return "OK", 200


        if button_id == "edit_time":

            ask_time(
                phone
            )

            return "OK", 200


        if button_id == "edit_notes":

            ask_notes(
                phone
            )

            return "OK", 200


        # =====================================
        # מצב השיחה הנוכחי
        # =====================================

        session = get_session(
            phone
        )

        state = session.get(
            "state"
        )


        # =====================================
        # מיקום
        # =====================================

        if location_text:

            if state in (
                "pickup_address",
                "edit_pickup"
            ):

                save_session(
                    phone,

                    pickup_address=
                        location_text
                )

                if state == "edit_pickup":

                    send_order_summary(
                        phone
                    )

                else:

                    ask_dropoff(
                        phone
                    )

                return "OK", 200


            if state in (
                "dropoff_address",
                "edit_dropoff"
            ):

                save_session(
                    phone,

                    dropoff_address=
                        location_text
                )

                if state == "edit_dropoff":

                    send_order_summary(
                        phone
                    )

                else:

                    ask_recipient_name(
                        phone
                    )

                return "OK", 200


            send_message(
                phone,

                "📍 קיבלתי את המיקום, "
                "אבל כרגע לא ביקשתי מיקום."
            )

            return "OK", 200


        # =====================================
        # בחירת משלוח מתוך כמה
        # =====================================

        if state in (
            "choose_active_order",
            "choose_cancel_order"
        ):

            if clean.isdigit():

                index = (
                    int(clean)
                    - 1
                )

                orders = active_orders(
                    phone
                )

                if (
                    0
                    <= index
                    < len(orders)
                ):

                    order = orders[
                        index
                    ]

                    if (
                        state
                        == "choose_cancel_order"
                    ):

                        with db() as conn:

                            conn.execute(
                                """
                                UPDATE orders

                                SET
                                    status='cancel_requested',
                                    updated_at=?

                                WHERE id=?
                                """,

                                (
                                    now_ts(),
                                    order["id"]
                                )
                            )

                        clear_session(
                            phone
                        )

                        send_message(
                            phone,

                            "⏳ בקשת הביטול נשלחה לנציג."
                        )

                        send_message(
                            ADMIN_PHONE,

                            "🚨 בקשת ביטול\n\n"

                            f"📱 "
                            f"{display_phone(phone)}\n"

                            f"📍 "
                            f"{order['pickup_address']} "
                            f"→ "
                            f"{order['dropoff_address']}"
                        )

                    else:

                        clear_session(
                            phone
                        )

                        send_message(
                            phone,

                            f"{STATUS_TEXT.get(order['status'], order['status'])}\n"

                            f"📍 "
                            f"{order['pickup_address']} "
                            f"→ "
                            f"{order['dropoff_address']}"
                        )

                    return "OK", 200


            send_message(
                phone,

                "כתוב רק את המספר "
                "שמופיע ליד המשלוח ברשימה."
            )

            return "OK", 200


        # =====================================
        # מחכה למסלול
        # =====================================

        if state == "waiting_route":

            origin, destination = (
                find_route(
                    text
                )
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
                        price,

                        urgent=bool(
                            session.get(
                                "urgent"
                            )
                        )
                    )

                else:

                    clear_session(
                        phone
                    )

                    send_message(
                        phone,

                        f"📍 "
                        f"{origin} → {destination}\n"

                        "אין מחיר אוטומטי למסלול הזה.\n"

                        "העברתי בקשה לנציג."
                    )

                    send_message(
                        ADMIN_PHONE,

                        "💰 בקשת מחיר\n\n"

                        f"📱 "
                        f"{display_phone(phone)}\n"

                        f"📍 "
                        f"{origin} → {destination}"
                    )

                return "OK", 200


            send_message(
                phone,

                "לא הצלחתי לזהות שתי ערים.\n"

                "נסה למשל:\n"

                "ירושלים תל אביב"
            )

            return "OK", 200


        # =====================================
        # איסוף
        # =====================================

        if state in (
            "pickup_address",
            "edit_pickup"
        ):

            save_session(
                phone,

                pickup_address=
                    text
            )

            if state == "edit_pickup":

                send_order_summary(
                    phone
                )

            else:

                ask_dropoff(
                    phone
                )

            return "OK", 200


        # =====================================
        # מסירה
        # =====================================

        if state in (
            "dropoff_address",
            "edit_dropoff"
        ):

            save_session(
                phone,

                dropoff_address=
                    text
            )

            if state == "edit_dropoff":

                send_order_summary(
                    phone
                )

            else:

                ask_recipient_name(
                    phone
                )

            return "OK", 200


        # =====================================
        # שם מקבל
        # =====================================

        if state == "recipient_name":

            save_session(
                phone,

                recipient_name=
                    text
            )

            ask_recipient_phone(
                phone
            )

            return "OK", 200


        # =====================================
        # טלפון
        # =====================================

        if state in (
            "recipient_phone",
            "edit_phone"
        ):

            digits = re.sub(
                r"\D",
                "",
                text
            )

            if len(digits) < 9:

                send_message(
                    phone,

                    "המספר נראה קצר מדי.\n"

                    "שלח מספר טלפון מלא."
                )

                return "OK", 200


            save_session(
                phone,

                recipient_phone=
                    text
            )

            if state == "edit_phone":

                send_order_summary(
                    phone
                )

            else:

                ask_package(
                    phone
                )

            return "OK", 200


        # =====================================
        # חבילה אחרת
        # =====================================

        if state == "package_other":

            save_session(
                phone,
                package=text
            )

            ask_time(
                phone
            )

            return "OK", 200


        # =====================================
        # זמן
        # =====================================

        if state in (
            "time_today",
            "time_other"
        ):

            save_session(
                phone,

                delivery_time=
                    text
            )

            ask_notes(
                phone
            )

            return "OK", 200


        # =====================================
        # הערות
        # =====================================

        if state == "notes":

            save_session(
                phone,
                notes=text
            )

            send_order_summary(
                phone
            )

            return "OK", 200


        # =====================================
        # אם כתב מסלול ישר
        # =====================================

        origin, destination = (
            find_route(
                text
            )
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

                send_message(
                    phone,

                    f"📍 "
                    f"{origin} → {destination}\n"

                    "אין מחיר אוטומטי למסלול הזה.\n"

                    "העברתי בקשת מחיר לנציג."
                )

                send_message(
                    ADMIN_PHONE,

                    "💰 בקשת מחיר\n\n"

                    f"📱 "
                    f"{display_phone(phone)}\n"

                    f"📍 "
                    f"{origin} → {destination}"
                )

            return "OK", 200


        # =====================================
        # לא הבין
        # =====================================

        handle_unknown(
            phone
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
# הפעלה
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
