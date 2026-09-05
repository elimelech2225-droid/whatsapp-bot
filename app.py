from flask import Flask, request
import os
import re
import time
import sqlite3
import requests
import traceback

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
            trial_started_at INTEGER DEFAULT 0,
            trial_expires_at INTEGER DEFAULT 0,
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
            updated_at INTEGER DEFAULT 0
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
            conn.execute("""
                ALTER TABLE driver_profiles
                ADD COLUMN current_city TEXT DEFAULT ''
            """)
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
        print("ERROR: missing WhatsApp credentials")
        return False

    try:
        response = requests.post(
            api_url(),
            headers={
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "application/json",
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
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": text
        },
    })


def create_paperless_receipt(
    client_name,
    phone,
    amount,
    payment_method,
    plan_name
):
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
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": items
            },
        },
    })
