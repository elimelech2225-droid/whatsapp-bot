from flask import Flask, request
import os
import re
import time
import sqlite3
import requests

app = Flask(__name__)

# =========================================================
# הגדרות
# =========================================================

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
PAPERLESS_API_KEY = os.environ.get("PAPERLESS_API_KEY", "")
IS_VAT_EXEMPT = True
# מספר המנהל קבוע ישירות בקוד
ADMIN_PHONE = "972553155049"

GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v23.0"
)

DB_PATH = os.environ.get(
    "DB_PATH",
    "bot.db"
)

ROLE_CUSTOMER = "CUSTOMER"
ROLE_DRIVER = "DRIVER"

REG_IN_PROGRESS = "REGISTRATION_IN_PROGRESS"
REG_WAITING = "WAITING_ADMIN_APPROVAL"
REG_APPROVED = "APPROVED"
REG_REJECTED = "REJECTED"
REG_BLOCKED = "BLOCKED"

AVAIL_OFFLINE = "OFFLINE"
AVAIL_AVAILABLE = "AVAILABLE"
AVAIL_BUSY = "BUSY"
# =========================================================
# זיהוי שמות ערים
# =========================================================

CITY_ALIASES = {
    "תא": "תל אביב",
    'ת"א': "תל אביב",
    "ת״א": "תל אביב",
    "תלאביב": "תל אביב",
    "תל-אביב": "תל אביב",

    "ירושליים": "ירושלים",
    "ירושלים": "ירושלים",

    "ביתשמש": "בית שמש",
    "בית שמש": "בית שמש",

    "בניברק": "בני ברק",
    "בני ברק": "בני ברק",

    'פ"ת': "פתח תקווה",
    "פ״ת": "פתח תקווה",
    "פתח תקוה": "פתח תקווה",
    "פתח תקווה": "פתח תקווה",

    "ראשלצ": "ראשון לציון",
    'ראשל"צ': "ראשון לציון",
    "ראשון לציון": "ראשון לציון",

    "ראשהעין": "ראש העין",
    "ראש העין": "ראש העין",

    "אשקלון": "אשקלון",
    "אשדוד": "אשדוד",
    "תל אביב": "תל אביב",
    "רמת גן": "רמת גן",
    "גבעתיים": "גבעתיים",
    "חולון": "חולון",
    "בת ים": "בת ים",
    "רחובות": "רחובות",
    "יבנה": "יבנה",
    "נתניה": "נתניה",
    "חדרה": "חדרה",
    "הרצליה": "הרצליה",
    "רעננה": "רעננה",
    "כפר סבא": "כפר סבא",
    "מודיעין": "מודיעין",
    "אלעד": "אלעד",
    "עמנואל": "עמנואל",
    "קריית גת": "קריית גת",
    "קרית גת": "קריית גת",
    "באר שבע": "באר שבע",
    "בארשבע": "באר שבע",
    "חיפה": "חיפה",
}


def normalize_city_name(text):
    if not text:
        return ""

    clean = str(text).strip()

    clean = re.sub(
        r"\s+",
        " ",
        clean
    )

    if clean in CITY_ALIASES:
        return CITY_ALIASES[clean]

    lowered = clean.lower()

    for alias, city in CITY_ALIASES.items():
        if alias.lower() == lowered:
            return city

    return clean
SUB_NONE = "NONE"
SUB_WAITING_PAYMENT = "WAITING_PAYMENT"
SUB_WAITING_APPROVAL = "WAITING_ADMIN_PAYMENT_APPROVAL"
SUB_ACTIVE = "ACTIVE"
SUB_EXPIRED = "EXPIRED"

SHIP_OPEN = "OPEN"
SHIP_ACCEPTED = "ACCEPTED"
SHIP_ON_WAY_PICKUP = "ON_WAY_PICKUP"
SHIP_PICKED_UP = "PICKED_UP"
SHIP_ON_WAY_DESTINATION = "ON_WAY_DESTINATION"
SHIP_DELIVERED = "DELIVERED"
SHIP_CANCEL_REQUESTED = "CANCEL_REQUESTED"
SHIP_CANCELLED = "CANCELLED"


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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL") 
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            business_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            city TEXT DEFAULT '',
            vehicle_type TEXT DEFAULT '',
            vehicle_number TEXT DEFAULT '',
            registration_status TEXT DEFAULT 'REGISTRATION_IN_PROGRESS',
            agreement_accepted INTEGER DEFAULT 0,
            agreement_version TEXT DEFAULT '',
            agreement_accepted_at INTEGER DEFAULT 0,
            admin_approved_at INTEGER DEFAULT 0,
            admin_rejected_at INTEGER DEFAULT 0,
            rejection_reason TEXT DEFAULT '',
            is_blocked INTEGER DEFAULT 0,
            subscription_status TEXT DEFAULT 'NONE',
            subscription_plan TEXT DEFAULT '',
            subscription_expiry INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            phone TEXT PRIMARY KEY,
            state TEXT DEFAULT '',
            temp_role TEXT DEFAULT '',
            temp_full_name TEXT DEFAULT '',
            temp_business_name TEXT DEFAULT '',
            temp_email TEXT DEFAULT '',
            temp_city TEXT DEFAULT '',
            temp_vehicle_type TEXT DEFAULT '',
            temp_vehicle_number TEXT DEFAULT '',
            temp_service_areas TEXT DEFAULT '',
            temp_origin TEXT DEFAULT '',
            temp_destination TEXT DEFAULT '',
            temp_pickup_address TEXT DEFAULT '',
            temp_dropoff_address TEXT DEFAULT '',
            temp_package TEXT DEFAULT '',
            temp_recipient_name TEXT DEFAULT '',
            temp_recipient_phone TEXT DEFAULT '',
            temp_notes TEXT DEFAULT '',
            temp_plan TEXT DEFAULT '',
            temp_payment_method TEXT DEFAULT '',
            temp_reference_id INTEGER,
            updated_at INTEGER DEFAULT 0,
  trial_started_at INTEGER DEFAULT 0,
trial_expires_at INTEGER DEFAULT 0      
        );

        CREATE TABLE IF NOT EXISTS driver_profiles (
            user_id INTEGER PRIMARY KEY,
            availability_status TEXT DEFAULT 'OFFLINE',
            current_city TEXT DEFAULT '',
            all_country INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS driver_service_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            city TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0,
            UNIQUE(driver_id, city)
        );

        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            driver_id INTEGER,
            status TEXT DEFAULT 'OPEN',
            origin_city TEXT DEFAULT '',
            destination_city TEXT DEFAULT '',
            pickup_address TEXT DEFAULT '',
            dropoff_address TEXT DEFAULT '',
            package_description TEXT DEFAULT '',
            recipient_name TEXT DEFAULT '',
            recipient_phone TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0,
            accepted_at INTEGER DEFAULT 0,
            delivered_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS shipment_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            old_status TEXT DEFAULT '',
            new_status TEXT DEFAULT '',
            changed_by_phone TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cancellation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            requested_by_user_id INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            status TEXT DEFAULT 'WAITING_ADMIN_APPROVAL',
            requested_at INTEGER DEFAULT 0,
            approved_at INTEGER DEFAULT 0,
            rejected_at INTEGER DEFAULT 0,
            admin_phone TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_name TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'NONE',
            starts_at INTEGER DEFAULT 0,
            expires_at INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subscription_plan TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'WAITING_PROOF',
            proof_media_id TEXT DEFAULT '',
            submitted_at INTEGER DEFAULT 0,
            approved_at INTEGER DEFAULT 0,
            rejected_at INTEGER DEFAULT 0,
            rejection_reason TEXT DEFAULT '',
            approved_by_admin_phone TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS support_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT DEFAULT '',
            status TEXT DEFAULT 'OPEN',
            created_at INTEGER DEFAULT 0,
            closed_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_phone TEXT DEFAULT '',
            target_user_id INTEGER,
            action_type TEXT DEFAULT '',
            reference_id INTEGER,
            notes TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS processed_messages (
            message_id TEXT PRIMARY KEY,
            created_at INTEGER DEFAULT 0
        );
        """)

        try:
            conn.execute(
                """
                ALTER TABLE driver_profiles
                ADD COLUMN current_city TEXT DEFAULT ''
                """
            )
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN trial_started_at INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN trial_expires_at INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

init_db()


# =========================================================
# כלי עזר
# =========================================================

def normalize_phone(value):
    digits = re.sub(
        r"\D",
        "",
        value or ""
    )

    if digits.startswith("0"):
        return "972" + digits[1:]

    return digits


def get_user(phone):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone_number=?
            """,
            (phone,)
        ).fetchone()

    return dict(row) if row else None


def get_user_by_id(user_id):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (user_id,)
        ).fetchone()

    return dict(row) if row else None


def get_session(phone):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE phone=?
            """,
            (phone,)
        ).fetchone()

    return dict(row) if row else {}


def save_session(phone, **fields):
    current = get_session(phone)

    defaults = {
        "state": "",
        "temp_role": "",
        "temp_full_name": "",
        "temp_business_name": "",
        "temp_email": "",
        "temp_city": "",
        "temp_vehicle_type": "",
        "temp_vehicle_number": "",
        "temp_service_areas": "",
        "temp_origin": "",
        "temp_destination": "",
        "temp_pickup_address": "",
        "temp_dropoff_address": "",
        "temp_package": "",
        "temp_recipient_name": "",
        "temp_recipient_phone": "",
        "temp_notes": "",
        "temp_plan": "",
        "temp_payment_method": "",
        "temp_reference_id": None,
    }

    data = {}

    for key, default in defaults.items():
        data[key] = current.get(
            key,
            default
        )

    data.update(fields)
    data["updated_at"] = now_ts()

    with db() as conn:
        conn.execute("""
            INSERT INTO sessions (
                phone,
                state,
                temp_role,
                temp_full_name,
                temp_business_name,
                temp_email,
                temp_city,
                temp_vehicle_type,
                temp_vehicle_number,
                temp_service_areas,
                temp_origin,
                temp_destination,
                temp_pickup_address,
                temp_dropoff_address,
                temp_package,
                temp_recipient_name,
                temp_recipient_phone,
                temp_notes,
                temp_plan,
                temp_payment_method,
                temp_reference_id,
                updated_at
            )
            VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,?
            )

            ON CONFLICT(phone)
            DO UPDATE SET
                state=excluded.state,
                temp_role=excluded.temp_role,
                temp_full_name=excluded.temp_full_name,
                temp_business_name=excluded.temp_business_name,
                temp_email=excluded.temp_email,
                temp_city=excluded.temp_city,
                temp_vehicle_type=excluded.temp_vehicle_type,
                temp_vehicle_number=excluded.temp_vehicle_number,
                temp_service_areas=excluded.temp_service_areas,
                temp_origin=excluded.temp_origin,
                temp_destination=excluded.temp_destination,
                temp_pickup_address=excluded.temp_pickup_address,
                temp_dropoff_address=excluded.temp_dropoff_address,
                temp_package=excluded.temp_package,
                temp_recipient_name=excluded.temp_recipient_name,
                temp_recipient_phone=excluded.temp_recipient_phone,
                temp_notes=excluded.temp_notes,
                temp_plan=excluded.temp_plan,
                temp_payment_method=excluded.temp_payment_method,
                temp_reference_id=excluded.temp_reference_id,
                updated_at=excluded.updated_at
        """, (
            phone,
            data["state"],
            data["temp_role"],
            data["temp_full_name"],
            data["temp_business_name"],
            data["temp_email"],
            data["temp_city"],
            data["temp_vehicle_type"],
            data["temp_vehicle_number"],
            data["temp_service_areas"],
            data["temp_origin"],
            data["temp_destination"],
            data["temp_pickup_address"],
            data["temp_dropoff_address"],
            data["temp_package"],
            data["temp_recipient_name"],
            data["temp_recipient_phone"],
            data["temp_notes"],
            data["temp_plan"],
            data["temp_payment_method"],
            data["temp_reference_id"],
            data["updated_at"],
        ))


def clear_session(phone):
    with db() as conn:
        conn.execute(
            """
            DELETE FROM sessions
            WHERE phone=?
            """,
            (phone,)
        )


def is_duplicate(message_id):
    if not message_id:
        return False

    with db() as conn:
        conn.execute(
            """
            DELETE FROM processed_messages
            WHERE created_at < ?
            """,
            (now_ts() - 86400,)
        )

        row = conn.execute(
            """
            SELECT 1
            FROM processed_messages
            WHERE message_id=?
            """,
            (message_id,)
        ).fetchone()

        if row:
            return True

        conn.execute(
            """
            INSERT INTO processed_messages(
                message_id,
                created_at
            )
            VALUES (?, ?)
            """,
            (
                message_id,
                now_ts()
            )
        )

    return False


# =========================================================
# שליחת WhatsApp
# =========================================================

def api_url():
    return (
        "https://graph.facebook.com/"
        f"{GRAPH_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


def send_payload(payload):
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        print(
            "ERROR: missing WhatsApp credentials"
        )
        return False

    try:
        response = requests.post(
            api_url(),
            headers={
                "Authorization":
                    f"Bearer {ACCESS_TOKEN}",
                "Content-Type":
                    "application/json",
            },
            json=payload,
            timeout=(5, 10)
        )

        print(
            "WHATSAPP:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as exc:
        print(
            "WHATSAPP ERROR:",
            repr(exc)
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
        },
    })
def create_paperless_receipt(client_name, phone, amount, payment_method, plan_name):
    if not PAPERLESS_API_KEY:
        print("PAPERLESS_API_KEY is missing")
        return None

    method = str(payment_method or "").lower()

    payment_data = {
        "iType": 8,
        "dAmount": float(amount)
    }

    if "bit" in method or "ביט" in method:
        payment_data = {
            "iType": 5,
            "dAmount": float(amount),
            "iApp": 1
        }
    elif "paybox" in method or "פייבוקס" in method:
        payment_data = {
            "iType": 5,
            "dAmount": float(amount),
            "iApp": 2
        }
    elif "העברה" in method or "transfer" in method:
        payment_data = {
            "iType": 2,
            "dAmount": float(amount)
        }
    elif "מזומן" in method or "cash" in method:
        payment_data = {
            "iType": 4,
            "dAmount": float(amount)
        }
    elif "אשראי" in method or "credit" in method:
        payment_data = {
            "iType": 3,
            "dAmount": float(amount)
        }

    payload = {
        "type": {
            "iType": 3,
        "bIsPreview": True,    
            "sRemark": None,
            "sExtraTitle": None,
            "sBasedOnDocID": None,
            "sUniqueID": None
        },
        "client": {
            "sPaperlessID": None,
            "sNumber": None,
            "sName": client_name,
            "sEmail": None,
            "sMobile": phone,
            "sAddress": None,
            "sExternalID": None,
            "bIsFixed": True,
            "bIsEng": False
        },
        "items": [
            {
                "sProductID": None,
                "sProductName": f"מנוי חודשי - {plan_name}",
                "dCount": 1,
                "dPrice": float(amount),
                "bVAT0": IS_VAT_EXEMPT
            }
        ],
        "payments": [payment_data]
    }

    try:
        response = requests.put(
            "https://pl-apis-prod-il.azurewebsites.net/api/invoices/create",
            headers={
                "X-API-KEY": PAPERLESS_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if not response.ok:
            print("Paperless error body:", response.status_code, response.text)
            return None
        data = response.json()

        invoices = data.get("invoices", [])
        if not invoices:
            print("Paperless returned no invoice:", data)
            return None

        invoice = invoices[0]
        return invoice.get("sURL") or invoice.get("sDownloadPageURL")

    except Exception as e:
        print("Paperless receipt error:", e)
        return None

def send_image_by_id(phone, media_id):
    return send_payload({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "image": {
            "id": media_id
        },
    })

def send_buttons(phone, text, buttons):
    items = []

    for button_id, title in buttons[:3]:
        items.append({
            "type": "reply",
            "reply": {
                "id": str(button_id)[:256],
                "title": str(title)[:20],
            },
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
            },
        },
    })


def send_list(
    phone,
    text,
    button_text,
    sections
):
    return send_payload({
        "messaging_product":
            "whatsapp",
        "to":
            phone,
        "type":
            "interactive",
        "interactive": {
            "type":
                "list",
            "body": {
                "text":
                    text
            },
            "action": {
                "button":
                    button_text[:20],
                "sections":
                    sections,
            },
        },
    })


# =========================================================
# הסכמים
# =========================================================

def customer_agreement():
    return """הסכם שימוש ללקוח / שולח

1. הלקוח מתחייב למסור פרטים נכונים ומדויקים לגבי המשלוח.
2. אין למסור למשלוח פריט בלתי חוקי, אסור או מסוכן.
3. הלקוח אחראי למסירת כתובות ופרטי קשר נכונים.
4. המערכת משמשת לחיבור בין לקוחות לבין שליחים.
5. זמני ביצוע עשויים להשתנות עקב עומסים, מזג אוויר, זמינות ונסיבות נוספות.
6. בקשת ביטול אינה בהכרח ביטול אוטומטי.
7. אם שליח כבר קיבל משלוח, הביטול כפוף לאישור מנהל.
8. תשלומים ומנויים כפופים למסלול שנבחר.
9. המערכת רשאית לחסום משתמש שעושה שימוש לרעה בשירות.
10. פרטי המשלוח הדרושים לביצועו עשויים להימסר לשליח.
11. נתוני הרשמה, משלוחים, תשלומים וסטטוסים יישמרו לצורך הפעלת השירות.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים."""


def driver_agreement():
    return """הסכם שימוש לשליח

1. השליח מתחייב לבצע משלוחים באחריות ובנאמנות.
2. השליח יקבל רק משלוח שהוא מסוגל ומתכוון לבצע.
3. השליח מתחייב לשמור על פרטיות הלקוח והנמען.
4. השליח מתחייב לפעול בהתאם לחוקי התעבורה ולדין.
5. באחריות השליח להחזיק רישיון, ביטוח ואישורים תקפים כנדרש.
6. השליח מתחייב לשמור על המשלוח בזמן שהוא ברשותו.
7. אין לפתוח, להשתמש, לגנוב או לפגוע במשלוח.
8. השליח מתחייב לעדכן סטטוסים בצורה נכונה.
9. במקרה של תקלה או בעיה יש לפנות למנהל.
10. המערכת משמשת לחיבור בין לקוחות לשליחים.
11. המערכת רשאית להשעות או לחסום שליח עקב הפרה או שימוש לרעה.
12. שחרור ממשלוח שכבר התקבל עשוי לדרוש אישור מנהל.
13. השליח מסכים לתנאי המנוי והתשלום הרלוונטיים.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים."""


# =========================================================
# תפריטי מערכת
# =========================================================

def show_role_choice(phone):
    save_session(
        phone,
        state="choose_role"
    )

    send_buttons(
        phone,
        """ברוכים הבאים למערכת המשלוחים 🚚

לפני שמתחילים יש לבחור כיצד ברצונך להירשם.

כל מספר טלפון יכול להיות משויך לסוג חשבון אחד בלבד.""",
        [
            (
                "role_customer",
                "אני לקוח / שולח"
            ),
            (
                "role_driver",
                "אני שליח"
            ),
        ]
    )


def show_admin_menu(phone):
    send_list(
        phone,
        "תפריט מנהל 👑",
        "פתיחת תפריט",
        [
            {
                "title": "ניהול המערכת",
                "rows": [
                    {
                        "id": "admin_pending_users",
                        "title": "הרשמות ממתינות"
                    },
                    {
                        "id": "admin_cancel_requests",
                        "title": "בקשות ביטול"
                    },
                    {
                        "id": "admin_payments",
                        "title": "תשלומים ממתינים"
                    },
                    {
                        "id": "admin_support",
                        "title": "פניות לנציג"
                    },
                    {
                        "id": "admin_open_shipments",
                        "title": "משלוחים פעילים"
                    },
                ]
            }
        ]
    )

def show_customer_menu(phone):
    send_list(
        phone,
        "תפריט לקוח 📦",
        "פתיחת תפריט",
        [
            {
                "title": "אפשרויות",
                "rows": [
                    {
                        "id": "customer_new_delivery",
                        "title": "הזמנת משלוח חדש"
                    },
                    {
                        "id": "customer_my_shipments",
                        "title": "המשלוחים שלי"
                    },
                    {
                        "id": "customer_cancel",
                        "title": "בקשת ביטול"
                    },
                    {
                        "id": "customer_subscription",
                        "title": "מנוי ותשלומים"
                    },
                    {
                        "id": "customer_support",
                        "title": "צור קשר / תמיכה"
                    },
                ]
            }
        ]
    )


def show_driver_menu(phone):
    send_list(
        phone,
        "תפריט שליח 🚚",
        "פתיחת תפריט",
        [
            {
                "title": "אפשרויות",
                "rows": [
                    {
                        "id": "driver_available",
                        "title": "אני פנוי"
                    },
                    {
                        "id": "driver_offline",
                        "title": "אני לא פנוי"
                    },
                    {
                        "id": "driver_areas",
                        "title": "אזורי הפעילות שלי"
                    },
                    {
                        "id": "driver_open_shipments",
                        "title": "משלוחים פתוחים"
                    },
                    {
                        "id": "driver_my_shipments",
                        "title": "המשלוחים שלי"
                    },
                    {
                        "id": "driver_guide",
                        "title": "מדריך לשליח"
                    },
                    {
                        "id": "driver_subscription",
                        "title": "מנוי ותשלומים"
                    },
                    {
                        "id": "driver_support",
                        "title": "צור קשר / תמיכה"
                    },
                ]
            }
        ]
    )


def driver_guide_text():
    return """מדריך לשליח 🚚

1. "אני פנוי" — המערכת תוכל להציע לך משלוחים חדשים.

2. "אני לא פנוי" — לא תקבל הצעות חדשות.

3. "אזורי הפעילות שלי" — ניתן לבחור ערים שבהן אתה עובד או לבחור "כל הארץ".

4. "משלוחים פתוחים" — מציג משלוחים שמתאימים לאזורי הפעילות שלך.

5. כאשר אתה לוקח משלוח, הוא משויך אליך ולא ניתן לשליח אחר לקחת אותו.

6. במהלך המשלוח יש לעדכן:
• אני בדרך לאיסוף
• אספתי
• בדרך ליעד
• נמסר

7. אם אינך יכול להמשיך משלוח שכבר לקחת, ניתן לבקש שחרור. המנהל יצטרך לאשר.

8. "מנוי ותשלומים" — מאפשר לבחור חבילת מנוי ולשלוח אישור תשלום.

9. בכל בעיה ניתן לבחור "צור קשר / תמיכה"."""


# =========================================================
# יצירת משתמש לאחר אישור ההסכם
# =========================================================

def create_pending_user(phone, session):
    role = session.get("temp_role", "")
    trial_start = now_ts()
    trial_expiry = trial_start + (30 * 24 * 60 * 60)

    with db() as conn:
        conn.execute("""
            INSERT INTO users (
                phone_number,
                role,
                full_name,
                business_name,
                email,
                city,
                vehicle_type,
                vehicle_number,
                registration_status,
                agreement_accepted,
                agreement_version,
                agreement_accepted_at,
                created_at,
                updated_at,
trial_started_at,
trial_expires_at
                
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '1.0', ?, ?, ?, ?, ?)

            ON CONFLICT(phone_number)
            DO UPDATE SET
                full_name=excluded.full_name,
                business_name=excluded.business_name,
                email=excluded.email,
                city=excluded.city,
                vehicle_type=excluded.vehicle_type,
                vehicle_number=excluded.vehicle_number,
                registration_status=excluded.registration_status,
                agreement_accepted=1,
                agreement_version='1.0',
                agreement_accepted_at=excluded.agreement_accepted_at,
                updated_at=excluded.updated_at
        """, (
            phone,
            role,
            session.get("temp_full_name", ""),
            session.get("temp_business_name", ""),
            session.get("temp_email", ""),
            session.get("temp_city", ""),
            session.get("temp_vehicle_type", ""),
            session.get("temp_vehicle_number", ""),
            REG_WAITING,
            now_ts(),
            now_ts(),
            now_ts(),
trial_start,
trial_expiry
            
        ))

        row = conn.execute(
            "SELECT * FROM users WHERE phone_number=?",
            (phone,)
        ).fetchone()

        if role == ROLE_DRIVER:
            all_country = (
                session.get(
                    "temp_service_areas",
                    ""
                ).strip()
                == "כל הארץ"
            )

            conn.execute("""
                INSERT INTO driver_profiles (
                    user_id,
                    availability_status,
                    all_country
                )
                VALUES (?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    availability_status=excluded.availability_status,
                    all_country=excluded.all_country
            """, (
                row["id"],
                AVAIL_OFFLINE,
                1 if all_country else 0
            ))

            conn.execute(
                """
                DELETE FROM driver_service_areas
                WHERE driver_id=?
                """,
                (row["id"],)
            )

            if not all_country:
                areas = session.get(
                    "temp_service_areas",
                    ""
                )

                cities = [
                    city.strip()
                    for city in areas.split(",")
                    if city.strip()
                ]

                for city in cities:
                    conn.execute("""
                        INSERT OR IGNORE INTO driver_service_areas (
                            driver_id,
                            city,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, 1, ?, ?)
                    """, (
                        row["id"],
                        city,
                        now_ts(),
                        now_ts()
                    ))

            clear_session(phone)

            return get_user(phone)

# =========================================================
# הודעת הרשמה למנהל
# =========================================================

def notify_admin_new_registration(user):
    extra = ""

    if user["role"] == ROLE_CUSTOMER:
        extra = (
            "\nשם העסק: "
            + (user.get("business_name") or "-")
        )

    else:
        with db() as conn:
            profile = conn.execute(
                """
                SELECT *
                FROM driver_profiles
                WHERE user_id=?
                """,
                (user["id"],)
            ).fetchone()

            rows = conn.execute(
                """
                SELECT city
                FROM driver_service_areas
                WHERE driver_id=?
                AND is_active=1
                ORDER BY city
                """,
                (user["id"],)
            ).fetchall()

        if profile and profile["all_country"]:
            areas = "כל הארץ"
        else:
            areas = (
                ", ".join(
                    row["city"]
                    for row in rows
                )
                or "-"
            )

        extra = (
            "\nסוג רכב: "
            + (user.get("vehicle_type") or "-")
            + "\nמספר רכב: "
            + (user.get("vehicle_number") or "-")
            + "\nאזורי פעילות: "
            + areas
        )

    send_buttons(
        ADMIN_PHONE,
        f"""בקשת הרשמה חדשה 👤

מזהה משתמש: {user['id']}
שם: {user['full_name']}
טלפון: {user['phone_number']}
סוג חשבון: {'לקוח / שולח' if user['role'] == ROLE_CUSTOMER else 'שליח'}
עיר: {user['city']}{extra}

האם לאשר את המשתמש?""",
        [
            (
                f"approve_{user['id']}",
                "אשר הרשמה"
            ),
            (
                f"reject_{user['id']}",
                "דחה הרשמה"
            ),
            (
                f"block_{user['id']}",
                "חסום משתמש"
            ),
        ]
    )


# =========================================================
# אישור / דחיית משתמש
# =========================================================

def approve_user(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return None

        conn.execute("""
            UPDATE users
            SET
                registration_status=?,
                admin_approved_at=?,
                rejection_reason='',
                is_blocked=0,
                updated_at=?
            WHERE id=?
        """, (
            REG_APPROVED,
            now_ts(),
            now_ts(),
            user_id
        ))

        conn.execute("""
            INSERT INTO admin_actions (
                admin_phone,
                target_user_id,
                action_type,
                created_at
            )
            VALUES (?, ?, 'REGISTER_APPROVED', ?)
        """, (
            ADMIN_PHONE,
            user_id,
            now_ts()
        ))

    return get_user_by_id(user_id)


def reject_user(user_id, reason):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return None

        conn.execute("""
            UPDATE users
            SET
                registration_status=?,
                admin_rejected_at=?,
                rejection_reason=?,
                updated_at=?
            WHERE id=?
        """, (
            REG_REJECTED,
            now_ts(),
            reason,
            now_ts(),
            user_id
        ))

    return get_user_by_id(user_id)


def block_user(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return None

        conn.execute("""
            UPDATE users
            SET
                registration_status=?,
                is_blocked=1,
                updated_at=?
            WHERE id=?
        """, (
            REG_BLOCKED,
            now_ts(),
            user_id
        ))

    return get_user_by_id(user_id)


# =========================================================
# הרשמה
# =========================================================

def handle_registration(phone, text, action_id):
    session = get_session(phone)
    state = session.get("state", "")

    if action_id == "role_customer":
        save_session(
            phone,
            state="customer_name",
            temp_role=ROLE_CUSTOMER
        )

        send_message(
            phone,
            "מעולה. מה השם המלא שלך?"
        )
        return True

    if action_id == "role_driver":
        save_session(
            phone,
            state="driver_name",
            temp_role=ROLE_DRIVER
        )

        send_message(
            phone,
            "מעולה. מה השם המלא שלך?"
        )
        return True

    if state == "choose_role":
        send_message(
            phone,
            "יש לבחור באמצעות אחד הכפתורים."
        )
        return True

    # -------------------------
    # הרשמת לקוח
    # -------------------------

    if state == "customer_name":
        save_session(
            phone,
            state="customer_business",
            temp_full_name=text.strip()
        )

        send_message(
            phone,
            'מה שם העסק? אם אין עסק, כתוב "אין".'
        )
        return True

    if state == "customer_business":
        business = (
            ""
            if text.strip() == "אין"
            else text.strip()
        )

        save_session(
            phone,
            state="customer_city",
            temp_business_name=business
        )

        send_message(
            phone,
            "באיזו עיר אתה נמצא?"
        )
        return True

    if state == "customer_city":
        save_session(
            phone,
            state="customer_email",
            temp_city=text.strip()
        )

        send_message(
            phone,
            'מה האימייל שלך? אם אין, כתוב "אין".'
        )
        return True

    if state == "customer_email":
        email = (
            ""
            if text.strip() == "אין"
            else text.strip()
        )

        save_session(
            phone,
            state="customer_summary",
            temp_email=email
        )

        s = get_session(phone)

        send_buttons(
            phone,
            f"""נא לבדוק שהפרטים נכונים:

שם: {s.get('temp_full_name', '')}
שם העסק: {s.get('temp_business_name') or '-'}
עיר: {s.get('temp_city', '')}
אימייל: {s.get('temp_email') or '-'}
מספר WhatsApp: {phone}

סוג החשבון: לקוח / שולח""",
            [
                (
                    "customer_details_ok",
                    "מאשר את הפרטים"
                ),
                (
                    "customer_details_edit",
                    "עריכת פרטים"
                ),
            ]
        )
        return True

    if action_id == "customer_details_edit":
        save_session(
            phone,
            state="customer_name"
        )

        send_message(
            phone,
            "נתחיל מחדש. מה השם המלא שלך?"
        )
        return True

    if action_id == "customer_details_ok":
        save_session(
            phone,
            state="customer_agreement"
        )

        send_buttons(
            phone,
            customer_agreement(),
            [
                (
                    "agreement_accept",
                    "אני מסכים"
                ),
                (
                    "agreement_decline",
                    "איני מסכים"
                ),
            ]
        )
        return True

    # -------------------------
    # הרשמת שליח
    # -------------------------

    if state == "driver_name":
        save_session(
            phone,
            state="driver_city",
            temp_full_name=text.strip()
        )

        send_message(
            phone,
            "באיזו עיר אתה גר?"
        )
        return True

    if state == "driver_city":
        save_session(
            phone,
            state="driver_vehicle_type",
            temp_city=text.strip()
        )

        send_list(
            phone,
            "בחר סוג רכב:",
            "בחירת רכב",
            [
                {
                    "title": "סוג רכב",
                    "rows": [
                        {
                            "id": "vehicle_private",
                            "title": "רכב פרטי"
                        },
                        {
                            "id": "vehicle_motorcycle",
                            "title": "אופנוע / קטנוע"
                        },
                        {
                            "id": "vehicle_commercial",
                            "title": "רכב מסחרי"
                        },
                        {
                            "id": "vehicle_other",
                            "title": "אחר"
                        },
                    ]
                }
            ]
        )
        return True

    vehicle_map = {
        "vehicle_private": "רכב פרטי",
        "vehicle_motorcycle": "אופנוע / קטנוע",
        "vehicle_commercial": "רכב מסחרי",
        "vehicle_other": "אחר",
    }

    if action_id in vehicle_map:
        save_session(
            phone,
            state="driver_vehicle_number",
            temp_vehicle_type=
                vehicle_map[action_id]
        )

        send_message(
            phone,
            'מה מספר הרכב? אם לא רוצה למסור כרגע, כתוב "אין".'
        )
        return True

    if state == "driver_vehicle_number":
        number = (
            ""
            if text.strip() == "אין"
            else text.strip()
        )

        save_session(
            phone,
            state="driver_areas",
            temp_vehicle_number=number
        )

        send_message(
            phone,
            """באילו ערים אתה פנוי לבצע משלוחים?

אפשר לרשום כמה ערים עם פסיקים.

לדוגמה:
ירושלים, בית שמש, תל אביב

אם אתה עובד בכל הארץ, כתוב:
כל הארץ"""
        )
        return True

    if state == "driver_areas":
        save_session(
            phone,
            state="driver_agreement",
            temp_service_areas=text.strip()
        )

        send_buttons(
            phone,
            driver_agreement(),
            [
                (
                    "agreement_accept",
                    "אני מסכים"
                ),
                (
                    "agreement_decline",
                    "איני מסכים"
                ),
            ]
        )
        return True

    # -------------------------
    # הסכמים
    # -------------------------

    if action_id == "agreement_decline":
        clear_session(phone)

        send_message(
            phone,
            """ההרשמה נעצרה משום שלא אישרת את תנאי השימוש.

ניתן להתחיל מחדש בכל עת."""
        )
        return True

    if action_id == "agreement_accept":
        s = get_session(phone)

        if not s.get("temp_role"):
            show_role_choice(phone)
            return True

        user = create_pending_user(
            phone,
            s
        )

        send_message(
            phone,
            """ההרשמה התקבלה בהצלחה ✅

החשבון שלך ממתין כעת לאישור מנהל.

לאחר שהמנהל יאשר אותך תקבל הודעה אוטומטית."""
        )

        notify_admin_new_registration(
            user
        )

        return True

    return False


# =========================================================
# שליחים
# =========================================================

def set_driver_availability(phone, status):
    user = get_user(phone)

    if not user:
        return False

    if user["role"] != ROLE_DRIVER:
        return False

    with db() as conn:
        conn.execute("""
            INSERT INTO driver_profiles (
                user_id,
                availability_status
            )
            VALUES (?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                availability_status=
                    excluded.availability_status
        """, (
            user["id"],
            status
        ))

    return True

def set_driver_current_availability(phone, status, city=""):
    user = get_user(phone)

    if not user:
        return False

    if user["role"] != ROLE_DRIVER:
        return False

    normalized_city = (
        normalize_city_name(city)
        if city
        else ""
    )

    with db() as conn:
        conn.execute(
            """
            INSERT INTO driver_profiles (
                user_id,
                availability_status,
                current_city,
                all_country
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                availability_status=excluded.availability_status,
                current_city=excluded.current_city,
                all_country=excluded.all_country
            """,
            (
                user["id"],
                status,
                normalized_city if status == AVAIL_AVAILABLE else "",
                1 if (
                    normalized_city == "כל הארץ"
                    and status == AVAIL_AVAILABLE
                ) else 0
            )
        )

    return True
def get_driver_areas(user_id):
    with db() as conn:
        profile = conn.execute(
            """
            SELECT *
            FROM driver_profiles
            WHERE user_id=?
            """,
            (user_id,)
        ).fetchone()

        rows = conn.execute(
            """
            SELECT city
            FROM driver_service_areas
            WHERE driver_id=?
            AND is_active=1
            ORDER BY city
            """,
            (user_id,)
        ).fetchall()

    if profile and profile["all_country"]:
        return "כל הארץ"

    return (
        ", ".join(
            row["city"]
            for row in rows
        )
        or "לא הוגדרו אזורים"
    )


# =========================================================
# משלוחים
# =========================================================

def create_shipment(customer, session):
    with db() as conn:
        cursor = conn.execute("""
            INSERT INTO shipments (
                customer_id,
                status,
                origin_city,
                destination_city,
                                pickup_address,
                dropoff_address,
                package_description,
                recipient_name,
                recipient_phone,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            customer["id"],
            SHIP_OPEN,
            session.get("temp_origin", ""),
            session.get("temp_destination", ""),
            session.get("temp_pickup_address", ""),
            session.get("temp_dropoff_address", ""),
            session.get("temp_package", ""),
            session.get("temp_recipient_name", ""),
            session.get("temp_recipient_phone", ""),
            session.get("temp_notes", ""),
            now_ts(),
            now_ts()
        ))

        shipment_id = cursor.lastrowid

        conn.execute("""
            INSERT INTO shipment_status_history (
                shipment_id,
                old_status,
                new_status,
                changed_by_phone,
                created_at
            )
            VALUES (?, '', ?, ?, ?)
        """, (
            shipment_id,
            SHIP_OPEN,
            customer["phone_number"],
            now_ts()
        ))

    return shipment_id


def get_shipment(shipment_id):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE id=?
            """,
            (shipment_id,)
        ).fetchone()

    return dict(row) if row else None


def update_shipment_status(
    shipment_id,
    new_status,
    changed_by_phone
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    old_status = shipment["status"]

    delivered_at = (
        now_ts()
        if new_status == SHIP_DELIVERED
        else shipment["delivered_at"]
    )

    with db() as conn:
        conn.execute("""
            UPDATE shipments
            SET
                status=?,
                delivered_at=?,
                updated_at=?
            WHERE id=?
        """, (
            new_status,
            delivered_at,
            now_ts(),
            shipment_id
        ))

        conn.execute("""
            INSERT INTO shipment_status_history (
                shipment_id,
                old_status,
                new_status,
                changed_by_phone,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            shipment_id,
            old_status,
            new_status,
            changed_by_phone,
            now_ts()
        ))

    return True


def shipment_text(shipment):
    return f"""משלוח #{shipment['id']} 📦

מאיפה: {shipment['origin_city']}
לאן: {shipment['destination_city']}

כתובת איסוף:
{shipment['pickup_address']}

כתובת מסירה:
{shipment['dropoff_address']}

מה מעבירים:
{shipment['package_description']}

שם מקבל:
{shipment['recipient_name']}

טלפון מקבל:
{shipment['recipient_phone']}

הערות:
{shipment['notes'] or '-'}"""


def get_customer_for_shipment(shipment):
    return get_user_by_id(
        shipment["customer_id"]
    )


def get_driver_for_shipment(shipment):
    if not shipment["driver_id"]:
        return None

    return get_user_by_id(
        shipment["driver_id"]
    )


def driver_matches_shipment(driver_id, origin_city):
    origin_city = normalize_city_name(origin_city)

    with db() as conn:
        profile = conn.execute(
            """
            SELECT *
            FROM driver_profiles
            WHERE user_id=?
            """,
            (driver_id,)
        ).fetchone()

    if not profile:
        return False

    if profile["availability_status"] != AVAIL_AVAILABLE:
        return False

    current_city = (
        profile["current_city"]
        or ""
    ).strip()

    if profile["all_country"] == 1:
        return True

    if current_city == "כל הארץ":
        return True

    if not current_city:
        return False

    return normalize_city_name(current_city) == origin_city

def notify_drivers_about_shipment(
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return

    with db() as conn:
        drivers = conn.execute("""
            SELECT u.*
            FROM users u

            JOIN driver_profiles d
            ON d.user_id=u.id

            WHERE
                u.role=?
                AND u.registration_status=?
                AND u.is_blocked=0
                AND d.availability_status=?
        """, (
            ROLE_DRIVER,
            REG_APPROVED,
            AVAIL_AVAILABLE
        )).fetchall()

    sent = 0

    for row in drivers:
        driver = dict(row)

        if not driver_matches_shipment(
            driver["id"],
            shipment["origin_city"]
        ):
            continue

        send_buttons(
            driver["phone_number"],
            shipment_text(shipment),
            [
                (
                    f"take_ship_{shipment_id}",
                    "אני לוקח"
                ),
                (
                    f"skip_ship_{shipment_id}",
                    "דלג"
                ),
            ]
        )

        sent += 1

    if sent == 0:
        send_message(
            ADMIN_PHONE,
            f"""⚠️ משלוח #{shipment_id}

כרגע לא נמצא שליח פנוי שמתאים לאזור.

מאיפה: {shipment['origin_city']}
לאן: {shipment['destination_city']}"""
        )


def take_shipment(
    shipment_id,
    driver_phone
):
    driver = get_user(
        driver_phone
    )

    if not driver:
        return False, "השליח לא נמצא."

    if driver["role"] != ROLE_DRIVER:
        return False, "הפעולה מיועדת לשליחים בלבד."

    with db() as conn:
        cursor = conn.execute("""
            UPDATE shipments
            SET
                driver_id=?,
                status=?,
                accepted_at=?,
                updated_at=?
            WHERE
                id=?
                AND status=?
                AND driver_id IS NULL
        """, (
            driver["id"],
            SHIP_ACCEPTED,
            now_ts(),
            now_ts(),
            shipment_id,
            SHIP_OPEN
        ))

        if cursor.rowcount != 1:
            return (
                False,
                "המשלוח כבר נלקח על ידי שליח אחר."
            )

        conn.execute("""
            UPDATE driver_profiles
            SET availability_status=?
            WHERE user_id=?
        """, (
            AVAIL_BUSY,
            driver["id"]
        ))

        conn.execute("""
            INSERT INTO shipment_status_history (
                shipment_id,
                old_status,
                new_status,
                changed_by_phone,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            shipment_id,
            SHIP_OPEN,
            SHIP_ACCEPTED,
            driver_phone,
            now_ts()
        ))

    shipment = get_shipment(
        shipment_id
    )

    customer = get_customer_for_shipment(
        shipment
    )

    if customer:
        send_message(
            customer["phone_number"],
            f"""נמצא שליח למשלוח #{shipment_id} ✅

שם השליח:
{driver['full_name']}

השליח קיבל את המשלוח ויעדכן את הסטטוס בהמשך."""
        )

    send_message(
        ADMIN_PHONE,
        f"""🚚 שליח לקח משלוח

משלוח #{shipment_id}
שליח: {driver['full_name']}
טלפון: {driver['phone_number']}"""
    )

    return True, "המשלוח שויך אליך בהצלחה ✅"


def show_driver_shipment_actions(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "המשלוח לא נמצא."
        )
        return

    send_list(
        phone,
        shipment_text(shipment),
        "עדכון משלוח",
        [
            {
                "title": "פעולות",
                "rows": [
                    {
                        "id":
                            f"ship_pickup_way_{shipment_id}",
                        "title":
                            "אני בדרך לאיסוף"
                    },
                    {
                        "id":
                            f"ship_picked_{shipment_id}",
                        "title":
                            "אספתי"
                    },
                    {
                        "id":
                            f"ship_destination_{shipment_id}",
                        "title":
                            "בדרך ליעד"
                    },
                    {
                        "id":
                            f"ship_delivered_{shipment_id}",
                        "title":
                            "נמסר"
                    },
                    {
                        "id":
                            f"driver_release_{shipment_id}",
                        "title":
                            "בקשת שחרור"
                    },
                ]
            }
        ]
    )


def notify_customer_status(
    shipment_id,
    status
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return

    customer = get_customer_for_shipment(
        shipment
    )

    if not customer:
        return

    status_text = {
        SHIP_ACCEPTED:
            "🚚 נמצא שליח למשלוח שלך.",
        SHIP_ON_WAY_PICKUP:
            "🚗 השליח בדרך לנקודת האיסוף.",
        SHIP_PICKED_UP:
            "📦 המשלוח נאסף.",
        SHIP_ON_WAY_DESTINATION:
            "🛣️ המשלוח בדרך ליעד.",
        SHIP_DELIVERED:
            "✅ המשלוח נמסר בהצלחה.",
        SHIP_CANCEL_REQUESTED:
            "⏳ בקשת הביטול נשלחה למנהל.",
        SHIP_CANCELLED:
            "❌ המשלוח בוטל.",
    }.get(
        status,
        "סטטוס המשלוח עודכן."
    )

    send_message(
        customer["phone_number"],
        f"""עדכון למשלוח #{shipment_id}

{status_text}"""
    )


# =========================================================
# בקשת ביטול
# =========================================================

def request_cancellation(
    shipment_id,
    user,
    reason
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if shipment["status"] in {
        SHIP_DELIVERED,
        SHIP_CANCELLED,
    }:
        return False

    with db() as conn:
        existing = conn.execute("""
            SELECT *
            FROM cancellation_requests
            WHERE shipment_id=?
            AND status='WAITING_ADMIN_APPROVAL'
        """, (
            shipment_id,
        )).fetchone()

        if existing:
            return True

        conn.execute("""
            INSERT INTO cancellation_requests (
                shipment_id,
                requested_by_user_id,
                reason,
                status,
                requested_at
            )
            VALUES (
                ?,
                ?,
                ?,
                'WAITING_ADMIN_APPROVAL',
                ?
            )
        """, (
            shipment_id,
            user["id"],
            reason,
            now_ts()
        ))

    update_shipment_status(
        shipment_id,
        SHIP_CANCEL_REQUESTED,
        user["phone_number"]
    )

    send_buttons(
        ADMIN_PHONE,
        f"""בקשת ביטול משלוח ❗

משלוח #{shipment_id}

מבקש:
{user['full_name']}

טלפון:
{user['phone_number']}

סיבה:
{reason}

לאשר את הביטול?""",
        [
            (
                f"cancel_yes_{shipment_id}",
                "אשר ביטול"
            ),
            (
                f"cancel_no_{shipment_id}",
                "דחה ביטול"
            ),
        ]
    )

    return True


def approve_cancellation(
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    with db() as conn:
        conn.execute("""
            UPDATE cancellation_requests
            SET
                status='APPROVED',
                approved_at=?,
                admin_phone=?
            WHERE shipment_id=?
            AND status='WAITING_ADMIN_APPROVAL'
        """, (
            now_ts(),
            ADMIN_PHONE,
            shipment_id
        ))

    update_shipment_status(
        shipment_id,
        SHIP_CANCELLED,
        ADMIN_PHONE
    )

    customer = get_customer_for_shipment(
        shipment
    )

    driver = get_driver_for_shipment(
        shipment
    )

    if customer:
        send_message(
            customer["phone_number"],
            f"""בקשת הביטול אושרה ✅

משלוח #{shipment_id} בוטל."""
        )

    if driver:
        send_message(
            driver["phone_number"],
            f"""משלוח #{shipment_id} בוטל על ידי המנהל."""
        )

        set_driver_availability(
            driver["phone_number"],
            AVAIL_AVAILABLE
        )

    return True


def reject_cancellation(
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    previous_status = (
        SHIP_ACCEPTED
        if shipment["driver_id"]
        else SHIP_OPEN
    )

    with db() as conn:
        conn.execute("""
            UPDATE cancellation_requests
            SET
                status='REJECTED',
                rejected_at=?,
                admin_phone=?
            WHERE shipment_id=?
            AND status='WAITING_ADMIN_APPROVAL'
        """, (
            now_ts(),
            ADMIN_PHONE,
            shipment_id
        ))

    update_shipment_status(
        shipment_id,
        previous_status,
        ADMIN_PHONE
    )

    customer = get_customer_for_shipment(
        shipment
    )

    if customer:
        send_message(
            customer["phone_number"],
            f"""בקשת הביטול למשלוח #{shipment_id} לא אושרה.

המשלוח ממשיך כרגיל."""
        )

    return True
# =========================================================
# מנויים ותשלומים
# =========================================================

def subscription_menu(phone, user):
    if user["role"] == ROLE_CUSTOMER:
        rows = [
            {
                "id": "plan_customer_50",
                "title": "חבילה 50 ₪",
                "description": "מנוי חודשי"
            },
            {
                "id": "plan_customer_100",
                "title": "חבילה 100 ₪",
                "description": "מנוי חודשי"
            },
        ]
    else:
        rows = [
            {
                "id": "plan_driver_50",
                "title": "חבילה 50 ₪",
                "description": "מנוי חודשי"
            },
            {
                "id": "plan_driver_100",
                "title": "חבילה 100 ₪",
                "description": "מנוי חודשי"
            },
        ]

    send_list(
        phone,
        """מנוי ותשלומים 💳

בחר את החבילה הרצויה:""",
        "בחירת חבילה",
        [
            {
                "title": "חבילות",
                "rows": rows
            }
        ]
    )


def plan_data(action_id):
    plans = {
        "plan_customer_50": (
            "CUSTOMER_50",
            50
        ),
        "plan_customer_100": (
            "CUSTOMER_100",
            100
        ),
        "plan_driver_50": (
            "DRIVER_50",
            50
        ),
        "plan_driver_100": (
            "DRIVER_100",
            100
        ),
    }

    return plans.get(action_id)


def start_payment(
    phone,
    user,
    action_id
):
    data = plan_data(action_id)

    if not data:
        return False

    plan_name, amount = data

    save_session(
        phone,
        state="payment_method",
        temp_plan=plan_name
    )

    send_buttons(
        phone,
        f"""בחרת חבילה:

{amount} ₪ לחודש.

כיצד תרצה לשלם?""",
        [
            (
                "payment_bit",
                "Bit"
            ),
            (
                "payment_bank",
                "העברה בנקאית"
            ),
        ]
    )

    return True


def payment_instructions(
    phone,
    method
):
    session = get_session(phone)

    plan = session.get(
        "temp_plan",
        ""
    )

    data = {
        "CUSTOMER_50": 50,
        "CUSTOMER_100": 100,
        "DRIVER_50": 50,
        "DRIVER_100": 100,
    }

    amount = data.get(
        plan,
        0
    )

    save_session(
        phone,
        state="waiting_payment_proof",
        temp_payment_method=method
    )

    if method == "BIT":
        send_message(
            phone,
            f"""תשלום באמצעות Bit 💳

סכום לתשלום:
{amount} ₪

יש להעביר את התשלום למספר שיוגדר על ידי מנהל המערכת.

לאחר שביצעת את התשלום, שלח כאן צילום מסך של אישור התשלום."""
        )

    else:
        send_message(
            phone,
            f"""תשלום בהעברה בנקאית 🏦

סכום לתשלום:
{amount} ₪

פרטי חשבון הבנק יוגדרו על ידי מנהל המערכת.

לאחר ביצוע ההעברה, שלח כאן צילום מסך של האסמכתה."""
        )


def save_payment_proof(
    phone,
    media_id
):
    user = get_user(phone)

    if not user:
        return None

    session = get_session(phone)

    plan = session.get(
        "temp_plan",
        ""
    )

    method = session.get(
        "temp_payment_method",
        ""
    )

    amounts = {
        "CUSTOMER_50": 50,
        "CUSTOMER_100": 100,
        "DRIVER_50": 50,
        "DRIVER_100": 100,
    }

    amount = amounts.get(
        plan,
        0
    )

    with db() as conn:
        cursor = conn.execute("""
            INSERT INTO payments (
                user_id,
                subscription_plan,
                amount,
                payment_method,
                payment_status,
                proof_media_id,
                submitted_at
            )
            VALUES (
                ?, ?, ?, ?,
                'WAITING_ADMIN_PAYMENT_APPROVAL',
                ?, ?
            )
        """, (
            user["id"],
            plan,
            amount,
            method,
            media_id,
            now_ts()
        ))

        payment_id = cursor.lastrowid

        conn.execute("""
            UPDATE users
            SET
                subscription_status=?,
                subscription_plan=?,
                updated_at=?
            WHERE id=?
        """, (
            SUB_WAITING_APPROVAL,
            plan,
            now_ts(),
            user["id"]
        ))
    send_image_by_id("972553155049", media_id)
    clear_session(phone)

    send_message(
        phone,
        """אישור התשלום התקבל ✅

הוא הועבר למנהל לבדיקה.

לאחר אישור המנהל תקבל הודעה."""
    )

    send_buttons(
        ADMIN_PHONE,
        f"""תשלום חדש ממתין לאישור 💳

מזהה תשלום: {payment_id}
משתמש: {user['full_name']}
טלפון: {user['phone_number']}
חבילה: {plan}
סכום: {amount} ₪
אמצעי תשלום: {method}

המשתמש שלח צילום/אסמכתה לתשלום.""",
        [
            (
                f"pay_yes_{payment_id}",
                "אשר תשלום"
            ),
            (
                f"pay_no_{payment_id}",
                "דחה תשלום"
            ),
        ]
    )

    return payment_id


def approve_payment(payment_id):
    with db() as conn:
        payment = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id=?
            """,
            (payment_id,)
        ).fetchone()

        if not payment:
            return False

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (payment["user_id"],)
        ).fetchone()

        if not user:
            return False

        start = now_ts()

        # 30 יום
        expiry = (
            start
            + (30 * 24 * 60 * 60)
        )

        conn.execute("""
            UPDATE payments
            SET
                payment_status='APPROVED',
                approved_at=?,
                approved_by_admin_phone=?
            WHERE id=?
        """, (
            start,
            ADMIN_PHONE,
            payment_id
        ))

        conn.execute("""
            UPDATE users
            SET
                subscription_status=?,
                subscription_plan=?,
                subscription_expiry=?,
                updated_at=?
            WHERE id=?
        """, (
            SUB_ACTIVE,
            payment["subscription_plan"],
            expiry,
            now_ts(),
            user["id"]
        ))

        conn.execute("""
            INSERT INTO subscriptions (
                user_id,
                plan_name,
                amount,
                status,
                starts_at,
                expires_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, 'ACTIVE',
                ?, ?, ?, ?
            )
        """, (
            user["id"],
            payment["subscription_plan"],
            payment["amount"],
            start,
            expiry,
            now_ts(),
            now_ts()
        ))
    receipt_url = create_paperless_receipt(
    user["phone_number"],
    user["phone_number"],
    payment["amount"],
    payment["payment_method"],
    payment["subscription_plan"]
)
    send_message(
        user["phone_number"],
        """התשלום אושר ✅

המנוי שלך הופעל בהצלחה."""
    )

    return True


def reject_payment(payment_id):
    with db() as conn:
        payment = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id=?
            """,
            (payment_id,)
        ).fetchone()

        if not payment:
            return False

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (payment["user_id"],)
        ).fetchone()

        conn.execute("""
            UPDATE payments
            SET
                payment_status='REJECTED',
                rejected_at=?,
                rejection_reason='התשלום לא אושר על ידי המנהל'
            WHERE id=?
        """, (
            now_ts(),
            payment_id
        ))

        conn.execute("""
            UPDATE users
            SET
                subscription_status=?,
                updated_at=?
            WHERE id=?
        """, (
            SUB_WAITING_PAYMENT,
            now_ts(),
            payment["user_id"]
        ))

    if user:
        send_message(
            user["phone_number"],
            """התשלום לא אושר.

ניתן לבצע תשלום מחדש ולשלוח אסמכתה חדשה."""
        )

    return True


# =========================================================
# פנייה לנציג
# =========================================================

def start_support_request(
    phone,
    user
):
    save_session(
        phone,
        state="support_message"
    )

    send_message(
        phone,
        """כתוב עכשיו את ההודעה שברצונך להעביר לנציג.

ההודעה תישלח למנהל."""
    )


def save_support_request(
    phone,
    text
):
    user = get_user(phone)

    if not user:
        return False

    with db() as conn:
        cursor = conn.execute("""
            INSERT INTO support_requests (
                user_id,
                message,
                status,
                created_at
            )
            VALUES (
                ?, ?, 'OPEN', ?
            )
        """, (
            user["id"],
            text,
            now_ts()
        ))

        request_id = cursor.lastrowid

    clear_session(phone)

    send_message(
        phone,
        """הפנייה שלך נשלחה לנציג ✅

המנהל קיבל את פרטי הפנייה."""
    )

    send_message(
        ADMIN_PHONE,
        f"""פנייה חדשה לנציג 📞

מספר פנייה: {request_id}

שם:
{user['full_name']}

טלפון:
{user['phone_number']}

סוג משתמש:
{'לקוח' if user['role'] == ROLE_CUSTOMER else 'שליח'}

הודעה:
{text}"""
    )

    return True


# =========================================================
# פתיחת משלוח על ידי לקוח
# =========================================================

def start_new_delivery(phone):
    save_session(
        phone,
        state="delivery_origin"
    )

    send_message(
        phone,
        """פתיחת משלוח חדש 📦

מאיזו עיר צריך לאסוף את המשלוח?"""
    )


def handle_delivery_creation(
    phone,
    text
):
    session = get_session(phone)
    state = session.get(
        "state",
        ""
    )

    if state == "delivery_origin":
        save_session(
            phone,
            state="delivery_destination",
            temp_origin=text.strip()
        )

        send_message(
            phone,
            "לאיזו עיר צריך למסור את המשלוח?"
        )

        return True

    if state == "delivery_destination":
        save_session(
            phone,
            state="delivery_pickup_address",
            temp_destination=text.strip()
        )

        send_message(
            phone,
            "מה כתובת האיסוף המלאה?"
        )

        return True

    if state == "delivery_pickup_address":
        save_session(
            phone,
            state="delivery_dropoff_address",
            temp_pickup_address=text.strip()
        )

        send_message(
            phone,
            "מה כתובת המסירה המלאה?"
        )

        return True

    if state == "delivery_dropoff_address":
        save_session(
            phone,
            state="delivery_package",
            temp_dropoff_address=text.strip()
        )

        send_message(
            phone,
            "מה צריך להעביר?"
        )

        return True

    if state == "delivery_package":
        save_session(
            phone,
            state="delivery_recipient_name",
            temp_package=text.strip()
        )

        send_message(
            phone,
            "מה שם מקבל המשלוח?"
        )

        return True

    if state == "delivery_recipient_name":
        save_session(
            phone,
            state="delivery_recipient_phone",
            temp_recipient_name=text.strip()
        )

        send_message(
            phone,
            "מה מספר הטלפון של מקבל המשלוח?"
        )

        return True

    if state == "delivery_recipient_phone":
        save_session(
            phone,
            state="delivery_notes",
            temp_recipient_phone=text.strip()
        )

        send_message(
            phone,
            """יש הערות מיוחדות?

אם אין, כתוב:
אין"""
        )

        return True

    if state == "delivery_notes":
        notes = (
            ""
            if text.strip() == "אין"
            else text.strip()
        )

        save_session(
            phone,
            state="delivery_confirm",
            temp_notes=notes
        )

        s = get_session(phone)

        send_buttons(
            phone,
            f"""סיכום המשלוח 📦

מאיפה:
{s.get('temp_origin', '')}

לאן:
{s.get('temp_destination', '')}

כתובת איסוף:
{s.get('temp_pickup_address', '')}

כתובת מסירה:
{s.get('temp_dropoff_address', '')}

מה מעבירים:
{s.get('temp_package', '')}

מקבל:
{s.get('temp_recipient_name', '')}

טלפון:
{s.get('temp_recipient_phone', '')}

הערות:
{s.get('temp_notes') or '-'}

""",
            [
                (
                    "delivery_confirm_yes",
                    "אשר משלוח"
                ),
                (
                    "delivery_confirm_no",
                    "בטל"
                ),
            ]
        )

        return True

    return False


# =========================================================
# המשלוחים שלי
# =========================================================

def customer_shipments(
    phone,
    user
):
    with db() as conn:
        rows = conn.execute("""
            SELECT *
            FROM shipments
            WHERE customer_id=?
            ORDER BY created_at DESC
            LIMIT 10
        """, (
            user["id"],
        )).fetchall()

    if not rows:
        send_message(
            phone,
            "עדיין אין לך משלוחים."
        )
        return

    for row in rows:
        shipment = dict(row)

        send_message(
            phone,
            f"""משלוח #{shipment['id']}

מאיפה:
{shipment['origin_city']}

לאן:
{shipment['destination_city']}

סטטוס:
{shipment['status']}"""
        )


def driver_shipments(
    phone,
    user
):
    with db() as conn:
        rows = conn.execute("""
            SELECT *
            FROM shipments
            WHERE driver_id=?
            AND status NOT IN (
                'DELIVERED',
                'CANCELLED'
            )
            ORDER BY created_at DESC
        """, (
            user["id"],
        )).fetchall()

    if not rows:
        send_message(
            phone,
            "אין לך כרגע משלוחים פעילים."
        )
        return

    for row in rows:
        shipment = dict(row)

        send_buttons(
            phone,
            shipment_text(
                shipment
            ),
            [
                (
                    f"driver_manage_{shipment['id']}",
                    "ניהול משלוח"
                ),
            ]
        )


def open_shipments_for_driver(
    phone,
    user
):
    with db() as conn:
        rows = conn.execute("""
            SELECT *
            FROM shipments
            WHERE
                status=?
                AND driver_id IS NULL
            ORDER BY created_at ASC
            LIMIT 20
        """, (
            SHIP_OPEN,
        )).fetchall()

    matches = []

    for row in rows:
        shipment = dict(row)

        if driver_matches_shipment(
            user["id"],
            shipment["origin_city"]
        ):
            matches.append(
                shipment
            )

    if not matches:
        send_message(
            phone,
            """אין כרגע משלוחים פתוחים שמתאימים לאזורי הפעילות שלך."""
        )
        return

    for shipment in matches:
        send_buttons(
            phone,
            shipment_text(
                shipment
            ),
            [
                (
                    f"take_ship_{shipment['id']}",
                    "אני לוקח"
                ),
            ]
        )


# =========================================================
# בקשת שחרור שליח
# =========================================================

def request_driver_release(
    shipment_id,
    driver
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if (
        shipment["driver_id"]
        != driver["id"]
    ):
        return False

    send_buttons(
        ADMIN_PHONE,
        f"""בקשת שחרור ממשלוח 🚚

משלוח #{shipment_id}

שליח:
{driver['full_name']}

טלפון:
{driver['phone_number']}

השליח מבקש להשתחרר מהמשלוח.

לאשר?""",
        [
            (
                f"release_yes_{shipment_id}",
                "אשר שחרור"
            ),
            (
                f"release_no_{shipment_id}",
                "דחה שחרור"
            ),
        ]
    )

    send_message(
        driver["phone_number"],
        """בקשת השחרור נשלחה למנהל.

עד לאישור המנהל המשלוח עדיין משויך אליך."""
    )

    return True


def approve_driver_release(
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    driver = get_driver_for_shipment(
        shipment
    )

    with db() as conn:
        conn.execute("""
            UPDATE shipments
            SET
                driver_id=NULL,
                status=?,
                accepted_at=0,
                updated_at=?
            WHERE id=?
        """, (
            SHIP_OPEN,
            now_ts(),
            shipment_id
        ))

    if driver:
        set_driver_availability(
            driver["phone_number"],
            AVAIL_AVAILABLE
        )

        send_message(
            driver["phone_number"],
            f"""המנהל אישר את השחרור ממשלוח #{shipment_id} ✅"""
        )

    customer = get_customer_for_shipment(
        shipment
    )

    if customer:
        send_message(
            customer["phone_number"],
            f"""עדכון לגבי משלוח #{shipment_id}

השליח שוחרר מהמשלוח.

המערכת מחפשת כעת שליח אחר."""
        )

    notify_drivers_about_shipment(
        shipment_id
    )

    return True


# =========================================================
# פעולות מנהל
# =========================================================

def handle_admin(
    phone,
    text,
    action_id
):
    if phone != ADMIN_PHONE:
        return False

    # =====================================================
    # אישור / דחייה / חסימת הרשמה
    # =====================================================

    match = re.match(
        r"^(approve|reject|block)_(\d+)$",
        action_id or ""
    )

    if match:
        action = match.group(1)
        user_id = int(match.group(2))

        if action == "approve":
            user = approve_user(user_id)

            if not user:
                send_message(
                    phone,
                    "המשתמש לא נמצא."
                )
                return True

            send_message(
                user["phone_number"],
                """ההרשמה שלך אושרה בהצלחה ✅

ברוך הבא למערכת."""
            )

            if user["role"] == ROLE_CUSTOMER:
                show_customer_menu(
                    user["phone_number"]
                )
            else:
                show_driver_menu(
                    user["phone_number"]
                )

            send_message(
                ADMIN_PHONE,
                f"""המשתמש אושר בהצלחה ✅

שם:
{user['full_name']}

טלפון:
{user['phone_number']}"""
            )

            return True

        if action == "reject":
            save_session(
                ADMIN_PHONE,
                state=f"admin_reject_user:{user_id}"
            )

            send_message(
                ADMIN_PHONE,
                """כתוב את סיבת הדחייה.

אם אינך רוצה לציין סיבה, כתוב:
ללא"""
            )

            return True

        if action == "block":
            user = block_user(user_id)

            if not user:
                send_message(
                    ADMIN_PHONE,
                    "המשתמש לא נמצא."
                )
                return True

            send_message(
                user["phone_number"],
                """החשבון שלך נחסם.

לפרטים נוספים יש לפנות למנהל."""
            )

            send_message(
                ADMIN_PHONE,
                "המשתמש נחסם בהצלחה."
            )

            return True

    # =====================================================
    # סיבת דחיית הרשמה
    # =====================================================

    session = get_session(
        ADMIN_PHONE
    )

    state = session.get(
        "state",
        ""
    )

    if state.startswith(
        "admin_reject_user:"
    ):
        try:
            user_id = int(
                state.split(
                    ":",
                    1
                )[1]
            )
        except ValueError:
            clear_session(
                ADMIN_PHONE
            )
            return True

        reason = text.strip()

        if not reason:
            reason = "לא צוין"

        if reason == "ללא":
            reason = "לא צוין"

        user = reject_user(
            user_id,
            reason
        )

        clear_session(
            ADMIN_PHONE
        )

        if user:
            send_message(
                user["phone_number"],
                f"""ההרשמה שלך לא אושרה.

סיבה:
{reason}

לפרטים נוספים ניתן לפנות למנהל."""
            )

            send_message(
                ADMIN_PHONE,
                "ההרשמה נדחתה."
            )
        else:
            send_message(
                ADMIN_PHONE,
                "המשתמש לא נמצא."
            )

        return True

    # =====================================================
    # אישור / דחיית ביטול
    # =====================================================

    match = re.match(
        r"^cancel_(yes|no)_(\d+)$",
        action_id or ""
    )

    if match:
        decision = match.group(1)
        shipment_id = int(
            match.group(2)
        )

        if decision == "yes":
            if approve_cancellation(
                shipment_id
            ):
                send_message(
                    ADMIN_PHONE,
                    f"""ביטול משלוח #{shipment_id} אושר ✅"""
                )
            else:
                send_message(
                    ADMIN_PHONE,
                    "לא ניתן לאשר את הביטול."
                )

        else:
            if reject_cancellation(
                shipment_id
            ):
                send_message(
                    ADMIN_PHONE,
                    f"""בקשת הביטול למשלוח #{shipment_id} נדחתה."""
                )
            else:
                send_message(
                    ADMIN_PHONE,
                    "לא ניתן לדחות את הביטול."
                )

        return True

    # =====================================================
    # אישור / דחיית תשלום
    # =====================================================

    match = re.match(
        r"^pay_(yes|no)_(\d+)$",
        action_id or ""
    )

    if match:
        decision = match.group(1)
        payment_id = int(
            match.group(2)
        )

        if decision == "yes":
            if approve_payment(
                payment_id
            ):
                send_message(
                    ADMIN_PHONE,
                    f"""תשלום #{payment_id} אושר ✅"""
                )
            else:
                send_message(
                    ADMIN_PHONE,
                    "התשלום לא נמצא."
                )

        else:
            if reject_payment(
                payment_id
            ):
                send_message(
                    ADMIN_PHONE,
                    f"""תשלום #{payment_id} נדחה."""
                )
            else:
                send_message(
                    ADMIN_PHONE,
                    "התשלום לא נמצא."
                )

        return True

    # =====================================================
    # שחרור שליח ממשלוח
    # =====================================================

    match = re.match(
        r"^release_(yes|no)_(\d+)$",
        action_id or ""
    )

    if match:
        decision = match.group(1)
        shipment_id = int(
            match.group(2)
        )

        shipment = get_shipment(
            shipment_id
        )

        if not shipment:
            send_message(
                ADMIN_PHONE,
                "המשלוח לא נמצא."
            )
            return True

        driver = get_driver_for_shipment(
            shipment
        )

        if decision == "yes":
            if approve_driver_release(
                shipment_id
            ):
                send_message(
                    ADMIN_PHONE,
                    f"""השליח שוחרר ממשלוח #{shipment_id} ✅"""
                )
            else:
                send_message(
                    ADMIN_PHONE,
                    "לא ניתן לשחרר את השליח."
                )

        else:
            if driver:
                send_message(
                    driver["phone_number"],
                    f"""בקשת השחרור ממשלוח #{shipment_id} לא אושרה.

המשלוח עדיין משויך אליך."""
                )

            send_message(
                ADMIN_PHONE,
                f"""בקשת השחרור ממשלוח #{shipment_id} נדחתה."""
            )

        return True

    # =====================================================
    # תפריט מנהל
    # =====================================================

    if action_id == "admin_pending_users":
        with db() as conn:
            rows = conn.execute("""
                SELECT *
                FROM users
                WHERE registration_status=?
                ORDER BY created_at ASC
                LIMIT 20
            """, (
                REG_WAITING,
            )).fetchall()

        if not rows:
            send_message(
                ADMIN_PHONE,
                "אין כרגע הרשמות שממתינות לאישור."
            )
            return True

        for row in rows:
            user = dict(row)

            send_buttons(
                ADMIN_PHONE,
                f"""הרשמה ממתינה 👤

מזהה: {user['id']}
שם: {user['full_name']}
טלפון: {user['phone_number']}
סוג: {'לקוח' if user['role'] == ROLE_CUSTOMER else 'שליח'}
עיר: {user['city']}""",
                [
                    (
                        f"approve_{user['id']}",
                        "אשר הרשמה"
                    ),
                    (
                        f"reject_{user['id']}",
                        "דחה הרשמה"
                    ),
                    (
                        f"block_{user['id']}",
                        "חסום משתמש"
                    ),
                ]
            )

        return True

    if action_id == "admin_cancel_requests":
        with db() as conn:
            rows = conn.execute("""
                SELECT *
                FROM cancellation_requests
                WHERE status='WAITING_ADMIN_APPROVAL'
                ORDER BY requested_at ASC
                LIMIT 20
            """).fetchall()

        if not rows:
            send_message(
                ADMIN_PHONE,
                "אין כרגע בקשות ביטול שממתינות לאישור."
            )
            return True

        for row in rows:
            send_buttons(
                ADMIN_PHONE,
                f"""בקשת ביטול

משלוח:
#{row['shipment_id']}

סיבה:
{row['reason'] or '-'}""",
                [
                    (
                        f"cancel_yes_{row['shipment_id']}",
                        "אשר ביטול"
                    ),
                    (
                        f"cancel_no_{row['shipment_id']}",
                        "דחה ביטול"
                    ),
                ]
            )

        return True

    if action_id == "admin_payments":
        with db() as conn:
            rows = conn.execute("""
                SELECT
                    p.*,
                    u.full_name,
                    u.phone_number
                FROM payments p

                JOIN users u
                ON u.id=p.user_id

                WHERE
                    p.payment_status=
                    'WAITING_ADMIN_PAYMENT_APPROVAL'

                ORDER BY p.submitted_at ASC
                LIMIT 20
            """).fetchall()

        if not rows:
            send_message(
                ADMIN_PHONE,
                "אין כרגע תשלומים שממתינים לאישור."
            )
            return True

        for row in rows:
            send_buttons(
                ADMIN_PHONE,
                f"""תשלום ממתין 💳

תשלום #{row['id']}
שם: {row['full_name']}
טלפון: {row['phone_number']}
סכום: {row['amount']} ₪
אמצעי תשלום: {row['payment_method']}""",
                [
                    (
                        f"pay_yes_{row['id']}",
                        "אשר תשלום"
                    ),
                    (
                        f"pay_no_{row['id']}",
                        "דחה תשלום"
                    ),
                ]
            )

        return True

    if action_id == "admin_support":
        with db() as conn:
            rows = conn.execute("""
                SELECT
                    s.*,
                    u.full_name,
                    u.phone_number
                FROM support_requests s

                JOIN users u
                ON u.id=s.user_id

                WHERE s.status='OPEN'

                ORDER BY s.created_at ASC
                LIMIT 20
            """).fetchall()

        if not rows:
            send_message(
                ADMIN_PHONE,
                "אין כרגע פניות פתוחות לנציג."
            )
            return True

        for row in rows:
            send_message(
                ADMIN_PHONE,
                f"""פנייה #{row['id']} 📞

שם:
{row['full_name']}

טלפון:
{row['phone_number']}

הודעה:
{row['message']}"""
            )

        return True

    if action_id == "admin_open_shipments":
        with db() as conn:
            rows = conn.execute("""
                SELECT *
                FROM shipments
                WHERE status NOT IN (
                    'DELIVERED',
                    'CANCELLED'
                )
                ORDER BY created_at DESC
                LIMIT 20
            """).fetchall()

        if not rows:
            send_message(
                ADMIN_PHONE,
                "אין כרגע משלוחים פעילים."
            )
            return True

        for row in rows:
            send_message(
                ADMIN_PHONE,
                shipment_text(
                    dict(row)
                )
            )

        return True

    return False


# =========================================================
# פעולות משתמש מאושר
# =========================================================

def handle_approved_user(
    phone,
    user,
    text,
    action_id,
    media_id=""
):
    session = get_session(phone)

    state = session.get(
        "state",
        ""
    )
    # =====================================================
    # זמינות שליח לפי עיר - פנוי / תפוס
    # =====================================================

    if user["role"] == ROLE_DRIVER and text and not action_id:
        clean_text = re.sub(r"\s+", " ", str(text).strip())

        unavailable_patterns = [
            r"^תפוס(?:ה)?\s+(.+)$",
            r"^לא\s+פנוי(?:ה)?\s+(.+)$",
            r"^לא\s+זמין(?:ה)?\s+(.+)$",
        ]  

        for pattern in unavailable_patterns:
            match = re.match(
                pattern,
                clean_text,
                flags=re.IGNORECASE
            )

            if match:
                city_text = match.group(1).strip()

                set_driver_current_availability(
                    phone,
                    AVAIL_OFFLINE,
                    ""
                )

                if city_text:
                    city = normalize_city_name(city_text)

                    send_message(
                        phone,
                        f"""סומן שאתה לא פנוי כרגע ב{city} ✅

לא תקבל הצעות חדשות עד שתכתוב:
פנוי + שם עיר"""
                    )
                else:
                    send_message(
                        phone,
                        """סומן שאתה לא פנוי כרגע ✅

לא תקבל הצעות חדשות עד שתכתוב:
פנוי + שם עיר"""
                    )

                return True

        available_patterns = [
                    r"^פנוי(?:ה)?\s+(.+)$",
                    r"^אני\s+פנוי(?:ה)?\s+(.+)$",
                    r"^זמין(?:ה)?\s+(.+)$",
                    r"^אני\s+זמין(?:ה)?\s+(.+)$",
                    r"^פ\s+(.+)$",
                ] 

        for pattern in available_patterns:
            match = re.match(
                pattern,
                clean_text,
                flags=re.IGNORECASE
            )

            if match:
                city_text = match.group(1).strip()

                if city_text in ("בכל הארץ", "כל הארץ"):
                    city = "כל הארץ"
                else:
                    city = normalize_city_name(city_text)

                set_driver_current_availability(
                    phone,
                    AVAIL_AVAILABLE,
                    city
                )

                open_shipments_for_driver(
                    phone,
                    user
                )

                if city == "כל הארץ":
                    send_message(
                        phone,
                        """🟩 סומן שאתה פנוי בכל הארץ

תקבל הצעות למשלוחים מכל הארץ."""
                    )
                else:
                    send_message(
                        phone,
                        f"""🟩 סומן שאתה פנוי ב{city}

מעכשיו תקבל הצעות למשלוחים שיוצאים מ{city}.

אם עברת לעיר אחרת, פשוט כתוב:
פנוי + שם העיר החדשה"""
                    )

                return True           
    # פנייה לנציג
    if state == "support_message":
        save_support_request(
            phone,
            text
        )
        return True

    # צילום תשלום
    if state == "waiting_payment_proof":
        if media_id:
            save_payment_proof(
                phone,
                media_id
            )
        else:
            send_message(
                phone,
                """יש לשלוח צילום מסך או תמונה של אישור התשלום."""
            )

        return True

    # יצירת משלוח
    if state.startswith(
        "delivery_"
    ):
        if (
            action_id
            == "delivery_confirm_yes"
        ):
            session = get_session(
                phone
            )

            shipment_id = create_shipment(
                user,
                session
            )

            clear_session(
                phone
            )

            send_message(
                phone,
                f"""המשלוח נפתח בהצלחה ✅

מספר משלוח:
#{shipment_id}

המערכת מחפשת כעת שליח מתאים."""
            )

            send_message(
                ADMIN_PHONE,
                f"""משלוח חדש נפתח 📦

משלוח #{shipment_id}

לקוח:
{user['full_name']}

טלפון:
{user['phone_number']}"""
            )

            notify_drivers_about_shipment(
                shipment_id
            )

            return True

        if (
            action_id
            == "delivery_confirm_no"
        ):
            clear_session(
                phone
            )

            send_message(
                phone,
                "פתיחת המשלוח בוטלה."
            )

            show_customer_menu(
                phone
            )

            return True

        if handle_delivery_creation(
            phone,
            text
        ):
            return True

    # בחירת מנוי
    if start_payment(
        phone,
        user,
        action_id
    ):
        return True

    if action_id == "payment_bit":
        payment_instructions(
            phone,
            "BIT"
        )
        return True

    if action_id == "payment_bank":
        payment_instructions(
            phone,
            "BANK_TRANSFER"
        )
        return True

    # לקוח
    if (
        user["role"]
        == ROLE_CUSTOMER
    ):
        if (
            action_id
            == "customer_new_delivery"
        ):
            start_new_delivery(
                phone
            )
            return True

        if (
            action_id
            == "customer_my_shipments"
        ):
            customer_shipments(
                phone,
                user
            )
            return True

        if (
            action_id
            == "customer_cancel"
        ):
            save_session(
                phone,
                state="customer_cancel_id"
            )

            send_message(
                phone,
                """כתוב את מספר המשלוח שברצונך לבטל.

לדוגמה:
12"""
            )

            return True

        if state == "customer_cancel_id":
            try:
                shipment_id = int(
                    re.sub(
                        r"\D",
                        "",
                        text
                    )
                )
            except ValueError:
                send_message(
                    phone,
                    "יש לרשום מספר משלוח תקין."
                )
                return True

            shipment = get_shipment(
                shipment_id
            )

            if (
                not shipment
                or shipment["customer_id"]
                != user["id"]
            ):
                send_message(
                    phone,
                    "המשלוח לא נמצא."
                )
                return True

            save_session(
                phone,
                state="customer_cancel_reason",
                temp_reference_id=
                    shipment_id
            )

            send_message(
                phone,
                "מה סיבת הביטול?"
            )

            return True

        if state == "customer_cancel_reason":
            shipment_id = session.get(
                "temp_reference_id"
            )

            clear_session(
                phone
            )

            if request_cancellation(
                shipment_id,
                user,
                text.strip()
            ):
                send_message(
                    phone,
                    """בקשת הביטול נשלחה למנהל ⏳

המשלוח אינו מבוטל עד שהמנהל מאשר את הבקשה."""
                )
            else:
                send_message(
                    phone,
                    "לא ניתן לבקש ביטול עבור המשלוח הזה."
                )

            return True

        if (
            action_id
            == "customer_subscription"
        ):
            subscription_menu(
                phone,
                user
            )
            return True

        if (
            action_id
            == "customer_support"
        ):
            start_support_request(
                phone,
                user
            )
            return True

    # שליח
    if (
        user["role"]
        == ROLE_DRIVER
    ):
        if (
            action_id
            == "driver_available"
        ):
            set_driver_availability(
                phone,
                AVAIL_AVAILABLE
            )

            send_message(
                phone,
                """סומן שאתה פנוי לקבלת משלוחים ✅"""
            )

            return True

        if (
            action_id
            == "driver_offline"
        ):
            set_driver_availability(
                phone,
                AVAIL_OFFLINE
            )

            send_message(
                phone,
                """סומן שאתה לא פנוי.

לא תקבל הצעות חדשות עד שתסמן שוב "אני פנוי"."""
            )

            return True

        if (
            action_id
            == "driver_areas"
        ):
            areas = get_driver_areas(
                user["id"]
            )

            send_message(
                phone,
                f"""אזורי הפעילות שלך:

{areas}"""
            )

            return True

        if (
            action_id
            == "driver_open_shipments"
        ):
            open_shipments_for_driver(
                phone,
                user
            )
            return True

        if (
            action_id
            == "driver_my_shipments"
        ):
            driver_shipments(
                phone,
                user
            )
            return True

        if (
            action_id
            == "driver_guide"
        ):
            send_message(
                phone,
                driver_guide_text()
            )
            return True

        if (
            action_id
            == "driver_subscription"
        ):
            subscription_menu(
                phone,
                user
            )
            return True

        if (
            action_id
            == "driver_support"
        ):
            start_support_request(
                phone,
                user
            )
            return True

    # לקיחת משלוח
    match = re.match(
        r"^take_ship_(\d+)$",
        action_id or ""
    )

    if (
        match
        and user["role"]
        == ROLE_DRIVER
    ):
        shipment_id = int(
            match.group(1)
        )

        ok, message = take_shipment(
            shipment_id,
            phone
        )

        send_message(
            phone,
            message
        )

        if ok:
            show_driver_shipment_actions(
                phone,
                shipment_id
            )

        return True

    match = re.match(
        r"^driver_manage_(\d+)$",
        action_id or ""
    )

        

    if match:
        show_driver_shipment_actions(
            phone,
            int(match.group(1))
        )
        return True

    status_actions = {
        "ship_pickup_way_": SHIP_ON_WAY_PICKUP,
        "ship_picked_": SHIP_PICKED_UP,
        "ship_destination_": SHIP_ON_WAY_DESTINATION,
        "ship_delivered_": SHIP_DELIVERED,
    }

    for prefix, new_status in status_actions.items():
        if action_id.startswith(prefix):
            try:
                shipment_id = int(
                    action_id[len(prefix):]
                )
            except ValueError:
                return True

            shipment = get_shipment(
                shipment_id
            )

            if not shipment:
                send_message(
                    phone,
                    "המשלוח לא נמצא."
                )
                return True

            if (
                user["role"] != ROLE_DRIVER
                or shipment["driver_id"] != user["id"]
            ):
                send_message(
                    phone,
                    "המשלוח הזה אינו משויך אליך."
                )
                return True

            update_shipment_status(
                shipment_id,
                new_status,
                phone
            )

            notify_customer_status(
                shipment_id,
                new_status
            )

            if new_status == SHIP_DELIVERED:
                set_driver_availability(
                    phone,
                    AVAIL_AVAILABLE
                )

                send_message(
                    phone,
                    f"""משלוח #{shipment_id} סומן כנמסר ✅

אתה שוב מסומן כפנוי לקבלת משלוחים."""
                )

                send_message(
                    ADMIN_PHONE,
                    f"""משלוח #{shipment_id} הושלם ✅

השליח:
{user['full_name']}"""
                )
            else:
                send_message(
                    phone,
                    f"סטטוס משלוח #{shipment_id} עודכן בהצלחה ✅"
                )

                show_driver_shipment_actions(
                    phone,
                    shipment_id
                )

            return True

    match = re.match(
        r"^driver_release_(\d+)$",
        action_id or ""
    )

    if match:
        shipment_id = int(
            match.group(1)
        )

        if request_driver_release(
            shipment_id,
            user
        ):
            return True

        send_message(
            phone,
            "לא ניתן לשלוח בקשת שחרור עבור המשלוח הזה."
        )

        return True

    clean = (
        text
        or ""
    ).strip().lower()

    if clean in {
        "שלום",
        "היי",
        "הי",
        "תפריט",
        "ראשי",
        "menu",
    }:
        if user["role"] == ROLE_CUSTOMER:
            show_customer_menu(phone)
        else:
            show_driver_menu(phone)

        return True

    if user["role"] == ROLE_CUSTOMER:
        show_customer_menu(phone)
    else:
        show_driver_menu(phone)

    return True


# =========================================================
# קריאת הודעה מ-WhatsApp
# =========================================================

def extract_incoming(payload):
    try:
        value = (
            payload["entry"][0]
            ["changes"][0]
            ["value"]
        )

        messages = (
            value.get("messages")
            or []
        )

        if not messages:
            return None

        msg = messages[0]

        phone = normalize_phone(
            msg.get("from", "")
        )

        message_id = msg.get(
            "id",
            ""
        )

        msg_type = msg.get(
            "type",
            ""
        )

        text = ""
        action_id = ""
        media_id = ""

        if msg_type == "text":
            text = (
                msg.get("text", {})
                .get("body", "")
            )

        elif msg_type == "interactive":
            interactive = msg.get(
                "interactive",
                {}
            )

            if (
                interactive.get("type")
                == "button_reply"
            ):
                reply = interactive.get(
                    "button_reply",
                    {}
                )

                action_id = reply.get(
                    "id",
                    ""
                )

                text = reply.get(
                    "title",
                    ""
                )

            elif (
                interactive.get("type")
                == "list_reply"
            ):
                reply = interactive.get(
                    "list_reply",
                    {}
                )

                action_id = reply.get(
                    "id",
                    ""
                )

                text = reply.get(
                    "title",
                    ""
                )

        elif msg_type == "image":
            image = msg.get(
                "image",
                {}
            )

            media_id = image.get(
                "id",
                ""
            )

            text = image.get(
                "caption",
                ""
            )

        elif msg_type == "document":
            document = msg.get(
                "document",
                {}
            )

            media_id = document.get(
                "id",
                ""
            )

            text = document.get(
                "caption",
                ""
            )

        return {
            "phone": phone,
            "message_id": message_id,
            "text": text,
            "action_id": action_id,
            "media_id": media_id,
        }

    except (
        KeyError,
        IndexError,
        TypeError
    ):
        return None


# =========================================================
# Flask
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return (
        "WhatsApp delivery bot is running",
        200
    )


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
            challenge or "",
            200
        )

    return (
        "verification failed",
        403
    )


@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():
    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    incoming = extract_incoming(
        payload
    )

    if not incoming:
        return "ok", 200

    phone = incoming.get(
        "phone",
        ""
    )

    message_id = incoming.get(
        "message_id",
        ""
    )

    text = incoming.get(
        "text",
        ""
    )

    action_id = incoming.get(
        "action_id",
        ""
    )

    media_id = incoming.get(
        "media_id",
        ""
    )

    if not phone:
        return "ok", 200

    if is_duplicate(
        message_id
    ):
        return "ok", 200

    try:
        # המנהל תמיד קודם לכל משתמש אחר
        if phone == ADMIN_PHONE:
            if handle_admin(
                phone,
                text,
                action_id
            ):
                return "ok", 200

            show_admin_menu(
                phone
            )

            return "ok", 200

        user = get_user(
            phone
        )

        if not user:
            if handle_registration(
                phone,
                text,
                action_id
            ):
                return "ok", 200

            show_role_choice(
                phone
            )

            return "ok", 200

        if (
            user["is_blocked"]
            or user["registration_status"]
            == REG_BLOCKED
        ):
            send_message(
                phone,
                """החשבון שלך חסום.

יש לפנות למנהל."""
            )

            return "ok", 200

        if (
            user["registration_status"]
            == REG_WAITING
        ):
            send_message(
                phone,
                "החשבון שלך עדיין ממתין לאישור מנהל."
            )

            return "ok", 200

        if (
            user["registration_status"]
            == REG_REJECTED
        ):
            reason = (
                user.get(
                    "rejection_reason",
                    ""
                )
                or "לא צוין"
            )

            send_message(
                phone,
                f"""החשבון שלך אינו מאושר כרגע.

סיבה:
{reason}"""
            )

            return "ok", 200

        if (
            user["registration_status"]
            != REG_APPROVED
        ):
            send_message(
                phone,
                "החשבון שלך עדיין לא פעיל."
            )

            return "ok", 200

        handle_approved_user(
            phone,
            user,
            text,
            action_id,
            media_id
        )

        return "ok", 200

    except Exception as exc:
        print(
            "WEBHOOK ERROR:",
            repr(exc)
        )

        try:
            send_message(
                phone,
                """אירעה תקלה זמנית במערכת.

נסה שוב בעוד רגע."""
            )
        except Exception:
            pass

        return "ok", 200


# =========================================================
# הפעלת השרת
# =========================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
