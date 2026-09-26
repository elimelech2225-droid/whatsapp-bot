from flask import Flask, request
import os
import re
import time
import json
import sqlite3
import requests
import traceback

app = Flask(__name__)


# =========================================================
# שליחובוט - הגדרות מערכת
# =========================================================

BOT_NAME = "שליחובוט"

# מספר המנהל:
# 0553155049
ADMIN_PHONE = "972553155049"

VERIFY_TOKEN = os.environ.get(
    "WHATSAPP_VERIFY_TOKEN",
    ""
)

ACCESS_TOKEN = os.environ.get(
    "WHATSAPP_ACCESS_TOKEN",
    ""
)

PHONE_NUMBER_ID = os.environ.get(
    "WHATSAPP_PHONE_NUMBER_ID",
    ""
)

PAPERLESS_API_KEY = os.environ.get(
    "PAPERLESS_API_KEY",
    ""
)

GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v23.0"
)

DB_PATH = os.environ.get(
    "DB_PATH",
    "bot.db"
)

IS_VAT_EXEMPT = True


# =========================================================
# תפקידים
# =========================================================

ROLE_CUSTOMER = "CUSTOMER"
ROLE_DRIVER = "DRIVER"
ROLE_DISPATCHER = "DISPATCHER"


# =========================================================
# סטטוס הרשמה
# =========================================================

REG_ACTIVE = "ACTIVE"
REG_WAITING = "WAITING_ADMIN_APPROVAL"
REG_REJECTED = "REJECTED"
REG_BLOCKED = "BLOCKED"


# =========================================================
# סטטוס משלוח
# =========================================================

SHIP_OPEN = "OPEN"
SHIP_HAS_INTEREST = "HAS_INTEREST"
SHIP_ASSIGNED = "ASSIGNED"
SHIP_COMPLETED = "COMPLETED"
SHIP_CANCELLED = "CANCELLED"


# =========================================================
# סטטוס התעניינות
# =========================================================

INTEREST_INTERESTED = "INTERESTED"
INTEREST_SELECTED = "SELECTED"
INTEREST_REJECTED = "REJECTED"


# =========================================================
# סטטוס תשלום
# =========================================================

PAY_WAITING_PROOF = "WAITING_PROOF"
PAY_WAITING_ADMIN = "WAITING_ADMIN"
PAY_APPROVED = "APPROVED"
PAY_REJECTED = "REJECTED"


# =========================================================
# הגדרות ברירת מחדל
# הכל יהיה ניתן לשינוי מתפריט המנהל
# =========================================================

DEFAULT_SETTINGS = {
    "subscription_enabled": "1",

    # מחיר חודשי לשליח
    "subscription_price": "50",

    # חודשיים ניסיון
    "trial_days": "60",

    # העברה בנקאית
    "bank_enabled": "1",
    "bank_details":
        "פרטי חשבון הבנק טרם הוגדרו על ידי המנהל.",

    # Bit
    "bit_enabled": "1",
    "bit_phone":
        "טרם הוגדר",

    # PayBox
    "paybox_enabled": "1",
    "paybox_phone":
        "טרם הוגדר",

    # מצב תחזוקה
    "maintenance_mode": "0",
}


# =========================================================
# זמן
# =========================================================

def now_ts():
    return int(time.time())


def format_date(timestamp):
    if not timestamp:
        return "-"

    try:
        return time.strftime(
            "%d/%m/%Y",
            time.localtime(
                int(timestamp)
            )
        )
    except Exception:
        return "-"


# =========================================================
# חיבור למסד הנתונים
# =========================================================

def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=20
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA busy_timeout=30000"
    )

    conn.execute(
        "PRAGMA synchronous=NORMAL"
    )

    return conn


# =========================================================
# יצירת מסד הנתונים
# =========================================================

def init_db():

    with db() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                phone TEXT UNIQUE NOT NULL,

                role TEXT NOT NULL,

                full_name TEXT DEFAULT '',

                business_name TEXT DEFAULT '',

                city TEXT DEFAULT '',

                vehicle_type TEXT DEFAULT '',

                vehicle_year TEXT DEFAULT '',

                vehicle_number TEXT DEFAULT '',

                registration_status TEXT DEFAULT 'ACTIVE',

                is_blocked INTEGER DEFAULT 0,

                agreement_accepted INTEGER DEFAULT 0,

                agreement_accepted_at INTEGER DEFAULT 0,

                approved_at INTEGER DEFAULT 0,

                rejected_at INTEGER DEFAULT 0,

                trial_started_at INTEGER DEFAULT 0,

                trial_expires_at INTEGER DEFAULT 0,

                subscription_expires_at INTEGER DEFAULT 0,

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS sessions (
                phone TEXT PRIMARY KEY,

                state TEXT DEFAULT '',

                data TEXT DEFAULT '{}',

                updated_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,

                value TEXT DEFAULT ''
            );


            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                customer_id INTEGER NOT NULL,

                assigned_driver_id INTEGER,

                created_by_role TEXT DEFAULT '',

                status TEXT DEFAULT 'OPEN',

                origin_city TEXT DEFAULT '',

                pickup_address TEXT DEFAULT '',

                destination_city TEXT DEFAULT '',

                dropoff_address TEXT DEFAULT '',

                pickup_time TEXT DEFAULT '',

                package_description TEXT DEFAULT '',

                recipient_name TEXT DEFAULT '',

                recipient_phone TEXT DEFAULT '',

                price REAL DEFAULT 0,

                notes TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0,

                assigned_at INTEGER DEFAULT 0,

                completed_at INTEGER DEFAULT 0,

                cancelled_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS shipment_interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER NOT NULL,

                driver_id INTEGER NOT NULL,

                eta_minutes INTEGER DEFAULT 0,

                status TEXT DEFAULT 'INTERESTED',

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0,

                UNIQUE(
                    shipment_id,
                    driver_id
                )
            );


            CREATE TABLE IF NOT EXISTS driver_availability (
                driver_id INTEGER PRIMARY KEY,

                city TEXT DEFAULT '',

                is_available INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS driver_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER UNIQUE NOT NULL,

                driver_id INTEGER NOT NULL,

                customer_id INTEGER NOT NULL,

                stars INTEGER NOT NULL,

                created_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_phone TEXT NOT NULL,

                user_role TEXT DEFAULT '',

                category TEXT DEFAULT '',

                message TEXT DEFAULT '',

                shipment_id INTEGER,

                status TEXT DEFAULT 'OPEN',

                admin_reply TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                replied_at INTEGER DEFAULT 0,

                closed_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                amount REAL DEFAULT 0,

                payment_method TEXT DEFAULT '',

                status TEXT DEFAULT 'WAITING_PROOF',

                proof_media_id TEXT DEFAULT '',

                receipt_url TEXT DEFAULT '',

                submitted_at INTEGER DEFAULT 0,

                approved_at INTEGER DEFAULT 0,

                rejected_at INTEGER DEFAULT 0,

                approved_by TEXT DEFAULT ''
            );


            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                admin_phone TEXT DEFAULT '',

                action_type TEXT DEFAULT '',

                target_phone TEXT DEFAULT '',

                reference_id INTEGER,

                notes TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,

                created_at INTEGER DEFAULT 0
            );
            """
        )


        # -----------------------------------------
        # הכנסת הגדרות ברירת מחדל
        # -----------------------------------------

        for key, value in DEFAULT_SETTINGS.items():

            conn.execute(
                """
                INSERT OR IGNORE INTO settings (
                    key,
                    value
                )
                VALUES (?, ?)
                """,
                (
                    key,
                    value
                )
            )


        conn.commit()


# יצירת הטבלאות בעליית השרת

init_db()


# =========================================================
# כלי עזר - מספר טלפון
# =========================================================

def normalize_phone(value):

    digits = re.sub(
        r"\D",
        "",
        value or ""
    )

    if not digits:
        return ""

    if digits.startswith("972"):
        return digits

    if digits.startswith("0"):
        return (
            "972"
            + digits[1:]
        )

    return digits


# =========================================================
# כלי עזר - Row -> dict
# =========================================================

def row_to_dict(row):

    if not row:
        return None

    return dict(row)


# =========================================================
# משתמשים
# =========================================================

def get_user(phone):

    phone = normalize_phone(
        phone
    )

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone=?
            """,
            (
                phone,
            )
        ).fetchone()

    return row_to_dict(
        row
    )


def get_user_by_id(
    user_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (
                user_id,
            )
        ).fetchone()

    return row_to_dict(
        row
    )


# =========================================================
# הגדרות מערכת
# =========================================================

def get_setting(
    key,
    default=""
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT value
            FROM settings
            WHERE key=?
            """,
            (
                key,
            )
        ).fetchone()

    if not row:
        return default

    return row["value"]


def set_setting(
    key,
    value
):

    with db() as conn:

        conn.execute(
            """
            INSERT INTO settings (
                key,
                value
            )
            VALUES (?, ?)

            ON CONFLICT(key)
            DO UPDATE SET
                value=excluded.value
            """,
            (
                key,
                str(value)
            )
        )

        conn.commit()


# =========================================================
# Session
# =========================================================

def get_session(phone):

    phone = normalize_phone(
        phone
    )

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

        return {
            "state": "",
            "data": {},
        }

    result = dict(row)

    try:

        result["data"] = json.loads(
            result.get(
                "data",
                "{}"
            )
            or "{}"
        )

    except Exception:

        result["data"] = {}

    return result


def save_session(
    phone,
    state,
    data=None
):

    phone = normalize_phone(
        phone
    )

    if data is None:
        data = {}

    encoded_data = json.dumps(
        data,
        ensure_ascii=False
    )

    with db() as conn:

        conn.execute(
            """
            INSERT INTO sessions (
                phone,
                state,
                data,
                updated_at
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(phone)
            DO UPDATE SET
                state=excluded.state,
                data=excluded.data,
                updated_at=excluded.updated_at
            """,
            (
                phone,
                state,
                encoded_data,
                now_ts()
            )
        )

        conn.commit()


def clear_session(phone):

    phone = normalize_phone(
        phone
    )

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

        conn.commit()


# =========================================================
# מניעת טיפול כפול באותה הודעת WhatsApp
# =========================================================

def is_duplicate_message(
    message_id
):

    if not message_id:
        return False

    with db() as conn:

        # מנקה מזהים ישנים אחרי 24 שעות
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
            INSERT INTO processed_messages (
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

        conn.commit()

    return False


# =========================================================
# מידע על דירוג שליח
# =========================================================

def get_driver_rating(
    driver_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT
                COUNT(*) AS rating_count,
                COALESCE(
                    AVG(stars),
                    0
                ) AS rating_average
            FROM driver_ratings
            WHERE driver_id=?
            """,
            (
                driver_id,
            )
        ).fetchone()

    return {
        "count":
            int(
                row["rating_count"]
                or 0
            ),

        "average":
            float(
                row["rating_average"]
                or 0
            ),
    }


def get_driver_completed_count(
    driver_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE
                assigned_driver_id=?
                AND status=?
            """,
            (
                driver_id,
                SHIP_COMPLETED
            )
        ).fetchone()

    return int(
        row["total"]
        or 0
    )


# =========================================================
# בדיקת מנוי שליח
# =========================================================

def driver_has_access(
    user
):

    if not user:
        return False

    # סדרן פטור ממנוי
    if (
        user.get("role")
        == ROLE_DISPATCHER
    ):
        return True

    if (
        user.get("role")
        != ROLE_DRIVER
    ):
        return False

    # המנהל יכול לכבות את מערכת המנויים
    if (
        get_setting(
            "subscription_enabled",
            "1"
        )
        != "1"
    ):
        return True

    trial_expires_at = int(
        user.get(
            "trial_expires_at"
        )
        or 0
    )

    subscription_expires_at = int(
        user.get(
            "subscription_expires_at"
        )
        or 0
    )

    valid_until = max(
        trial_expires_at,
        subscription_expires_at
    )

    return (
        valid_until
        >= now_ts()
    )


# =========================================================
# רישום פעולת מנהל
# =========================================================

def log_admin_action(
    action_type,
    target_phone="",
    reference_id=None,
    notes=""
):

    with db() as conn:

        conn.execute(
            """
            INSERT INTO admin_actions (
                admin_phone,
                action_type,
                target_phone,
                reference_id,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ADMIN_PHONE,
                action_type,
                normalize_phone(
                    target_phone
                ),
                reference_id,
                notes,
                now_ts()
            )
        )

        conn.commit()
# =========================================================
# שליחת הודעות WhatsApp
# =========================================================

def whatsapp_api_url():

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
            "ERROR: missing WhatsApp credentials",
            flush=True
        )

        return False

    try:

        response = requests.post(
            whatsapp_api_url(),
            headers={
                "Authorization":
                    f"Bearer {ACCESS_TOKEN}",

                "Content-Type":
                    "application/json",
            },
            json=payload,
            timeout=(5, 15)
        )

        print(
            "WHATSAPP:",
            response.status_code,
            response.text,
            flush=True
        )

        return response.ok

    except Exception as exc:

        print(
            "WHATSAPP ERROR:",
            repr(exc),
            flush=True
        )

        return False


def send_message(
    phone,
    text
):

    phone = normalize_phone(
        phone
    )

    return send_payload(
        {
            "messaging_product":
                "whatsapp",

            "to":
                phone,

            "type":
                "text",

            "text": {
                "body":
                    str(text)
            },
        }
    )


def send_image_by_id(
    phone,
    media_id
):

    phone = normalize_phone(
        phone
    )

    return send_payload(
        {
            "messaging_product":
                "whatsapp",

            "to":
                phone,

            "type":
                "image",

            "image": {
                "id":
                    media_id
            },
        }
    )


def send_buttons(
    phone,
    text,
    buttons
):

    phone = normalize_phone(
        phone
    )

    items = []

    for (
        button_id,
        title
    ) in buttons[:3]:

        items.append(
            {
                "type":
                    "reply",

                "reply": {
                    "id":
                        str(
                            button_id
                        )[:256],

                    "title":
                        str(
                            title
                        )[:20],
                },
            }
        )

    return send_payload(
        {
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
                        str(text)
                },

                "action": {
                    "buttons":
                        items
                },
            },
        }
    )


def send_list(
    phone,
    text,
    button_text,
    rows,
    section_title="אפשרויות"
):

    phone = normalize_phone(
        phone
    )

    safe_rows = []

    for row in rows[:10]:

        row_id = row[0]
        row_title = row[1]

        row_description = (
            row[2]
            if len(row) > 2
            else ""
        )

        item = {
            "id":
                str(
                    row_id
                )[:200],

            "title":
                str(
                    row_title
                )[:24],
        }

        if row_description:

            item[
                "description"
            ] = str(
                row_description
            )[:72]

        safe_rows.append(
            item
        )

    return send_payload(
        {
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
                        str(text)
                },

                "action": {
                    "button":
                        str(
                            button_text
                        )[:20],

                    "sections": [
                        {
                            "title":
                                str(
                                    section_title
                                )[:24],

                            "rows":
                                safe_rows,
                        }
                    ],
                },
            },
        }
    )


# =========================================================
# Paperless - הפקת קבלה
# =========================================================

def create_paperless_receipt(
    client_name,
    phone,
    amount,
    payment_method,
    plan_name
):

    if not PAPERLESS_API_KEY:

        print(
            "PAPERLESS_API_KEY is missing",
            flush=True
        )

        return None

    method = str(
        payment_method
        or ""
    ).lower()

    payment_data = {
        "iType": 8,
        "dAmount":
            float(amount)
    }


    # -----------------------------------------
    # Bit
    # -----------------------------------------

    if (
        "bit" in method
        or "ביט" in method
    ):

        payment_data = {
            "iType": 5,

            "dAmount":
                float(amount),

            "iApp": 1,

            "dtDue": None,

            "iPayments": 0,

            "sBank": None,

            "sBranch": None,

            "sAccount": None,

            "sCheck": None,

            "iCreditType": None,

            "sCardSuffix": None,
        }


    # -----------------------------------------
    # PayBox
    # -----------------------------------------

    elif (
        "paybox" in method
        or "פייבוקס" in method
    ):

        payment_data = {
            "iType": 5,

            "dAmount":
                float(amount),

            "iApp": 2,
        }


    # -----------------------------------------
    # העברה בנקאית
    # -----------------------------------------

    elif (
        "bank" in method
        or "transfer" in method
        or "העברה" in method
    ):

        payment_data = {
            "iType": 2,

            "dAmount":
                float(amount),
        }


    # -----------------------------------------
    # אשראי
    # -----------------------------------------

    elif (
        "credit" in method
        or "אשראי" in method
    ):

        payment_data = {
            "iType": 3,

            "dAmount":
                float(amount),
        }


    # -----------------------------------------
    # מבנה הקבלה
    # -----------------------------------------

    payload = {

        "type": {

            "iType": 3,

            # קבלה אמיתית רק לאחר אישור מנהל
            "bIsPreview": False,

            "sRemark": None,

            "sExtraTitle": None,

            "sBasedOnDocID": None,

            "sUniqueID": None,
        },


        "client": {

            "sPaperlessID": None,

            "sNumber": None,

            "sName":
                client_name,

            "sEmail": None,

            "sMobile":
                phone,

            "sAddress": None,

            "sExternalID": None,

            "bIsFixed": True,

            "bIsEng": False,
        },


        "items": [

            {

                "sProductID": None,

                "sProductName":
                    (
                        f"מנוי חודשי - "
                        f"{plan_name}"
                    ),

                "dCount": 1,

                "dPrice":
                    float(amount),

                "bVAT0":
                    IS_VAT_EXEMPT,
            }

        ],


        "payments": [
            payment_data
        ],
    }


    try:

        response = requests.put(

            (
                "https://pl-apis-prod-il."
                "azurewebsites.net/"
                "api/invoices/create"
            ),

            headers={
                "X-API-KEY":
                    PAPERLESS_API_KEY,

                "Content-Type":
                    "application/json",
            },

            json=payload,

            timeout=30
        )


        if not response.ok:

            print(
                "Paperless error body:",
                response.status_code,
                response.text,
                flush=True
            )

            return None


        data = response.json()


        invoices = data.get(
            "invoices",
            []
        )


        if not invoices:

            print(
                "Paperless returned no invoice:",
                data,
                flush=True
            )

            return None


        invoice = invoices[0]


        return (
            invoice.get(
                "sURL"
            )
            or
            invoice.get(
                "sDownloadPageURL"
            )
        )


    except Exception as exc:

        print(
            "Paperless receipt error:",
            repr(exc),
            flush=True
        )

        return None


# =========================================================
# הסכם מזמין
# =========================================================

def customer_agreement():

    return f"""
📄 תנאי שימוש למזמין - {BOT_NAME}

1. המזמין אחראי למסירת פרטים נכונים ומדויקים לגבי המשלוח.

2. המזמין אחראי לתכולת המשלוח, לחוקיותה, לכתובות, לפרטי ההתקשרות, למועד ולמחיר שהוא מפרסם.

3. אין לפרסם או למסור באמצעות המערכת חפץ בלתי חוקי, אסור או מסוכן.

4. {BOT_NAME} משמשת כפלטפורמה המקשרת בין מזמיני משלוחים לבין שליחים.

5. {BOT_NAME} אינה צד לעסקה או להסכמות הישירות שבין המזמין לבין השליח.

6. המזמין והשליח אחראים להסכמות ביניהם ולביצוע המשלוח בהתאם לדין.

7. במקרה של בעיה או מחלוקת ניתן לפנות לנציג דרך המערכת. אנו ננסה לסייע בבירור ובפתרון ככל שניתן.

8. כל עוד טרם נבחר שליח, המזמין רשאי לערוך את פרטי המשלוח, לשנות את המחיר או לבטל את המשלוח.

9. לאחר שנבחר שליח, אין לבצע שינוי מהותי בפרטי המשלוח ללא תיאום עם השליח.

10. שימוש לרעה במערכת, פרסום מטעה או הפרות חוזרות עלולים להביא להגבלת החשבון או לחסימתו.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים.
""".strip()


# =========================================================
# התחייבות שליח
# =========================================================

def driver_agreement():

    return f"""
📄 התחייבות שליח - {BOT_NAME}

לפני לחיצה על "אני מעוניין" יש לבדוק את המסלול, המחיר, המועד והזמינות שלך.

אין ללחוץ "אני מעוניין" סתם. לחיצה מהווה כוונה אמיתית לבצע את המשלוח. לחיצות סרק, אי-הגעה או ביטולים חוזרים עלולים להביא להגבלה או חסימה.

השליח אחראי לביצוע המשלוח שקיבל, לשמירתו ולפעולה בהתאם לדין, לרבות רישיונות וביטוחים נדרשים.

{BOT_NAME} מקשרת בין המזמין לשליח ואינה צד לעסקה ביניהם. האחריות להסכמות ולמשלוח היא של הצדדים.

במקרה של בעיה ניתן לפנות לנציג ואנו ננסה לסייע.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי.
""".strip()


# =========================================================
# מדריך למזמין
# =========================================================

def customer_guide():

    return f"""
📖 מדריך למזמין - {BOT_NAME}

📦 פרסום משלוח
בחר "פרסם משלוח" והזן:
• עיר איסוף
• כתובת איסוף
• עיר יעד
• כתובת יעד
• מועד האיסוף
• תיאור המשלוח
• פרטי הנמען
• המחיר שאתה מציע
• הערות במידת הצורך

💰 מחיר פתוח
אתה קובע את המחיר שאתה מציע עבור המשלוח.
השליחים מחליטים אם הם מעוניינים במחיר שפורסם.

✏️ עריכת משלוח
כל עוד טרם בחרת שליח, ניתן לשנות מחיר ופרטים או לבטל את המשלוח.

🚚 בחירת שליח
שליח שמעוניין במשלוח מציין תוך כמה זמן הוא יכול להגיע.
אתה רואה את השליחים המעוניינים ובוחר את השליח המתאים לך.

⭐ דירוג
לאחר שהמשלוח הושלם תוכל לדרג את השליח מ-1 עד 5 כוכבים.

💬 פנייה לנציג
בכל בעיה ניתן לפתוח פנייה לנציג מתוך התפריט.
""".strip()


# =========================================================
# מדריך לשליח
# =========================================================

def driver_guide():

    return f"""
📖 מדריך לשליח - {BOT_NAME}

🟢 חיפוש לפי עיר
ניתן לכתוב למשל:

פנוי ירושלים

או:

פ ירושלים

המערכת תחפש עבורך משלוחים רלוונטיים.

📦 לפני התעניינות
לפני לחיצה על "אני מעוניין" בדוק:
• נקודת איסוף
• יעד
• מועד
• מחיר
• סוג המשלוח
• הזמינות שלך

🙋 אני מעוניין
לחץ רק אם אתה באמת יכול לבצע את המשלוח.

לאחר הלחיצה תתבקש לציין תוך כמה דקות תוכל להגיע לאיסוף.

👤 בחירת שליח
המזמין רואה את השליחים המעוניינים ובוחר למי למסור את המשלוח.

⚠️ התחייבות
אין לבצע לחיצות סרק.
ביטולים חוזרים, אי-הגעה או שימוש לרעה במערכת עלולים להביא להגבלת החשבון.

💳 מנוי
שליח חדש מקבל תקופת ניסיון חינם בהתאם להגדרות המערכת.
לאחר תקופת הניסיון נדרש מנוי פעיל, אלא אם מערכת המנויים כבויה.

💬 פנייה לנציג
במקרה של בעיה ניתן לפתוח פנייה לנציג מתוך התפריט.
""".strip()


# =========================================================
# בחירת סוג משתמש
# =========================================================

def show_role_choice(phone):

    save_session(
        phone,
        "choose_role",
        {}
    )

    send_buttons(
        phone,

        f"""
🚚 ברוכים הבאים ל{BOT_NAME}

איך תרצה להשתמש בפלטפורמה?
""".strip(),

        [
            (
                "register_customer",
                "📦 להזמין משלוח"
            ),

            (
                "register_driver",
                "🚚 לעבוד כשליח"
            ),
        ]
    )


# =========================================================
# תפריט מזמין
# =========================================================

def show_customer_menu(phone):

    send_list(
        phone,

        f"📦 תפריט מזמין - {BOT_NAME}",

        "פתיחת תפריט",

        [
            (
                "customer_new_shipment",
                "➕ פרסם משלוח",
                "יצירת משלוח חדש"
            ),

            (
                "customer_my_shipments",
                "📦 המשלוחים שלי",
                "ניהול משלוחים"
            ),

            (
                "customer_guide",
                "📖 מדריך למזמין",
                "הסבר על המערכת"
            ),

            (
                "support_new",
                "💬 פנייה לנציג",
                "יצירת פנייה לתמיכה"
            ),
        ]
    )


# =========================================================
# תפריט שליח
# =========================================================

def show_driver_menu(
    phone,
    user
):

    trial_expires = int(
        user.get(
            "trial_expires_at"
        )
        or 0
    )

    subscription_expires = int(
        user.get(
            "subscription_expires_at"
        )
        or 0
    )

    valid_until = max(
        trial_expires,
        subscription_expires
    )

    if valid_until:

        subscription_text = (
            "בתוקף עד "
            + format_date(
                valid_until
            )
        )

    else:

        subscription_text = (
            "אין מנוי פעיל"
        )


    send_list(
        phone,

        f"🚚 תפריט שליח - {BOT_NAME}",

        "פתיחת תפריט",

        [
            (
                "driver_available",
                "🟢 פנוי לפי עיר",
                "חיפוש משלוחים באזור"
            ),

            (
                "driver_open_shipments",
                "📦 משלוחים זמינים",
                "צפייה במשלוחים"
            ),

            (
                "driver_my_shipments",
                "🚚 המשלוחים שלי",
                "משלוחים ששובצת אליהם"
            ),

            (
                "driver_guide",
                "📖 מדריך לשליח",
                "כללים והסברים"
            ),

            (
                "driver_subscription",
                "💳 מנוי ותשלומים",
                subscription_text
            ),

            (
                "support_new",
                "💬 פנייה לנציג",
                "יצירת פנייה לתמיכה"
            ),
        ]
    )


# =========================================================
# תפריט סדרן
# =========================================================

def show_dispatcher_menu(phone):

    send_list(
        phone,

        f"👨‍💼 תפריט סדרן - {BOT_NAME}",

        "פתיחת תפריט",

        [
            (
                "customer_new_shipment",
                "➕ פרסם משלוח",
                "פרסום משלוח חדש"
            ),

            (
                "customer_my_shipments",
                "📦 משלוחים שלי",
                "ניהול משלוחים"
            ),

            (
                "driver_open_shipments",
                "🚚 משלוחים זמינים",
                "עבודה גם כשליח"
            ),

            (
                "driver_guide",
                "📖 מדריך לשליח",
                "כללי ביצוע"
                          ),

            (
                "support_new",
                "💬 פנייה לנציג",
                "יצירת פנייה לתמיכה"
            ),
        ]
    )


# =========================================================
# תפריט מנהל
# =========================================================

def show_admin_menu(phone):

    send_list(
        phone,

        f"👑 תפריט מנהל - {BOT_NAME}",

        "פתיחת תפריט",

        [
            (
                "admin_pending_drivers",
                "👤 אישורי שליחים",
                "שליחים הממתינים לאישור"
            ),

            (
                "admin_dispatchers",
                "👨‍💼 ניהול סדרנים",
                "הוספה והסרת סדרנים"
            ),

            (
                "admin_block_user",
                "🚫 חסום משתמש",
                "חסימה לפי מספר טלפון"
            ),

            (
                "admin_unblock_user",
                "🔓 הסר חסימה",
                "פתיחת משתמש חסום"
            ),

            (
                "admin_blocked_list",
                "📋 רשימת חסומים",
                "צפייה במשתמשים חסומים"
            ),

            (
                "admin_payments",
                "💳 אישורי תשלום",
                "אסמכתאות הממתינות לאישור"
            ),

            (
                "admin_support",
                "💬 פניות לנציג",
                "פניות פתוחות"
            ),

            (
                "admin_statistics",
                "📊 נתוני מערכת",
                "משתמשים ומשלוחים"
            ),

            (
                "admin_settings",
                "⚙️ הגדרות מערכת",
                "מנויים ואמצעי תשלום"
            ),

            (
                "admin_shipments",
                "📦 משלוחים פעילים",
                "צפייה במשלוחים"
            ),
        ]
    )


# =========================================================
# תפריט הגדרות מנהל
# =========================================================

def show_admin_settings_menu(phone):

    subscription_price = get_setting(
        "subscription_price",
        "50"
    )

    trial_days = get_setting(
        "trial_days",
        "60"
    )

    subscription_enabled = get_setting(
        "subscription_enabled",
        "1"
    )

    if subscription_enabled == "1":

        subscription_status = (
            "פעילה"
        )

    else:

        subscription_status = (
            "כבויה"
        )


    send_list(
        phone,

        (
            f"⚙️ הגדרות {BOT_NAME}\n\n"
            f"מחיר מנוי: {subscription_price} ₪\n"
            f"ימי ניסיון: {trial_days}\n"
            f"מערכת מנויים: {subscription_status}"
        ),

        "פתיחת הגדרות",

        [
            (
                "admin_set_price",
                "💰 מחיר מנוי",
                "שינוי מחיר חודשי"
            ),

            (
                "admin_set_trial",
                "🎁 ימי ניסיון",
                "שינוי תקופת הניסיון"
            ),

            (
                "admin_toggle_subscription",
                "🔄 מערכת מנויים",
                "הפעלה או כיבוי"
            ),

            (
                "admin_set_bank",
                "🏦 פרטי בנק",
                "שינוי פרטי העברה"
            ),

            (
                "admin_set_bit",
                "📱 מספר Bit",
                "שינוי מספר Bit"
            ),

            (
                "admin_set_paybox",
                "📲 מספר PayBox",
                "שינוי מספר PayBox"
            ),

            (
                "admin_payment_methods",
                "💳 אמצעי תשלום",
                "הפעלה וכיבוי"
            ),

            (
                "admin_maintenance",
                "🛠️ מצב תחזוקה",
                "הפעלת או השבתת הבוט"
            ),

            (
                "admin_menu",
                "⬅️ חזרה למנהל",
                "חזרה לתפריט הראשי"
            ),
        ]
    )


# =========================================================
# תפריט ניהול סדרנים
# =========================================================

def show_dispatcher_management_menu(
    phone
):

    send_list(
        phone,

        "👨‍💼 ניהול סדרנים",

        "פתיחת תפריט",

        [
            (
                "admin_dispatcher_add",
                "➕ הוסף סדרן",
                "הוספה לפי מספר טלפון"
            ),

            (
                "admin_dispatcher_remove",
                "➖ הסר סדרן",
                "הסרת הרשאת סדרן"
            ),

            (
                "admin_dispatcher_list",
                "📋 רשימת סדרנים",
                "צפייה בכל הסדרנים"
            ),

            (
                "admin_menu",
                "⬅️ חזרה",
                "חזרה לתפריט מנהל"
            ),
        ]
    )


# =========================================================
# תפריט אמצעי תשלום
# =========================================================

def show_payment_methods_admin(
    phone
):

    bank_enabled = (
        get_setting(
            "bank_enabled",
            "1"
        )
        == "1"
    )

    bit_enabled = (
        get_setting(
            "bit_enabled",
            "1"
        )
        == "1"
    )

    paybox_enabled = (
        get_setting(
            "paybox_enabled",
            "1"
        )
        == "1"
    )


    bank_text = (
        "פעיל"
        if bank_enabled
        else "כבוי"
    )

    bit_text = (
        "פעיל"
        if bit_enabled
        else "כבוי"
    )

    paybox_text = (
        "פעיל"
        if paybox_enabled
        else "כבוי"
    )


    send_list(
        phone,

        (
            "💳 אמצעי תשלום\n\n"
            f"בנק: {bank_text}\n"
            f"Bit: {bit_text}\n"
            f"PayBox: {paybox_text}"
        ),

        "ניהול תשלום",

        [
            (
                "admin_toggle_bank",
                "🏦 בנק",
                "הפעל / כבה העברה בנקאית"
            ),

            (
                "admin_toggle_bit",
                "📱 Bit",
                "הפעל / כבה Bit"
            ),

            (
                "admin_toggle_paybox",
                "📲 PayBox",
                "הפעל / כבה PayBox"
            ),

            (
                "admin_settings",
                "⬅️ חזרה",
                "חזרה להגדרות"
            ),
        ]
    )


# =========================================================
# הצגת אפשרויות תשלום לשליח
# =========================================================

def show_driver_payment_methods(
    phone
):

    price = get_setting(
        "subscription_price",
        "50"
    )

    rows = []


    if (
        get_setting(
            "bank_enabled",
            "1"
        )
        == "1"
    ):

        rows.append(
            (
                "pay_bank",
                "🏦 העברה בנקאית",
                f"{price} ₪"
            )
        )


    if (
        get_setting(
            "bit_enabled",
            "1"
        )
        == "1"
    ):

        rows.append(
            (
                "pay_bit",
                "📱 Bit",
                f"{price} ₪"
            )
        )


    if (
        get_setting(
            "paybox_enabled",
            "1"
        )
        == "1"
    ):

        rows.append(
            (
                "pay_paybox",
                "📲 PayBox",
                f"{price} ₪"
            )
        )


    if not rows:

        send_message(
            phone,
            (
                "כרגע אין אמצעי תשלום פעיל.\n"
                "יש לפנות לנציג."
            )
        )

        return


    send_list(
        phone,

        (
            f"💳 מנוי {BOT_NAME}\n\n"
            f"מחיר חודשי: {price} ₪\n\n"
            "בחר אמצעי תשלום:"
        ),

        "בחירת תשלום",

        rows
    )


# =========================================================
# הצגת מצב מנוי לשליח
# =========================================================

def show_driver_subscription(
    phone,
    user
):

    trial_expires_at = int(
        user.get(
            "trial_expires_at"
        )
        or 0
    )

    subscription_expires_at = int(
        user.get(
            "subscription_expires_at"
        )
        or 0
    )

    valid_until = max(
        trial_expires_at,
        subscription_expires_at
    )


    if (
        get_setting(
            "subscription_enabled",
            "1"
        )
        != "1"
    ):

        send_message(
            phone,
            (
                "💳 מערכת המנויים כרגע כבויה.\n\n"
                "ניתן להשתמש בשירות ללא מנוי."
            )
        )

        return


    if valid_until >= now_ts():

        send_buttons(
            phone,

            (
                "✅ המנוי שלך פעיל.\n\n"
                f"תוקף עד: {format_date(valid_until)}"
            ),

            [
                (
                    "driver_pay_subscription",
                    "💳 הארכת מנוי"
                ),

                (
                    "driver_menu",
                    "⬅️ חזרה"
                ),
            ]
        )

        return


    send_buttons(
        phone,

        (
            "⚠️ אין לך כרגע מנוי פעיל.\n\n"
            "כדי להמשיך לקבל משלוחים "
            "יש לחדש את המנוי."
        ),

        [
            (
                "driver_pay_subscription",
                "💳 תשלום מנוי"
            ),

            (
                "support_new",
                "💬 פנייה לנציג"
            ),
        ]
    )


# =========================================================
# שליחת תפריט לפי סוג משתמש
# =========================================================

def show_menu_for_user(
    phone,
    user=None
):

    phone = normalize_phone(
        phone
    )


    # המנהל תמיד מקבל תפריט מנהל
    if phone == ADMIN_PHONE:

        show_admin_menu(
            phone
        )

        return


    if not user:

        user = get_user(
            phone
        )


    if not user:

        show_role_choice(
            phone
        )

        return


    if (
        int(
            user.get(
                "is_blocked"
            )
            or 0
        )
        == 1
    ):

        send_message(
            phone,
            (
                "🚫 החשבון שלך חסום במערכת.\n\n"
                "לפרטים ניתן לפנות לתמיכה."
            )
        )

        return


    role = user.get(
        "role"
    )


    if role == ROLE_CUSTOMER:

        show_customer_menu(
            phone
        )

        return


    if role == ROLE_DRIVER:

        if (
            user.get(
                "registration_status"
            )
            == REG_WAITING
        ):

            send_message(
                phone,
                (
                    "⏳ ההרשמה שלך כשליח "
                    "ממתינה לאישור מנהל."
                )
            )

            return


        if (
            user.get(
                "registration_status"
            )
            != REG_ACTIVE
        ):

            send_message(
                phone,
                (
                    "החשבון שלך אינו פעיל כרגע.\n"
                    "ניתן לפנות לנציג לקבלת מידע."
                )
            )

            return


        show_driver_menu(
            phone,
            user
        )

        return


    if role == ROLE_DISPATCHER:

        show_dispatcher_menu(
            phone
        )

        return


    show_role_choice(
        phone
    )
# =========================================================
# הרשמת משתמשים
# =========================================================

def create_or_update_user(
    phone,
    role,
    full_name,
    business_name="",
    city="",
    vehicle_type="",
    vehicle_year="",
    vehicle_number="",
    registration_status=REG_ACTIVE
):

    phone = normalize_phone(
        phone
    )

    current_time = now_ts()

    trial_started_at = 0
    trial_expires_at = 0


    # תקופת ניסיון ניתנת רק לשליח
    if role == ROLE_DRIVER:

        trial_days = int(
            get_setting(
                "trial_days",
                "60"
            )
        )

        trial_started_at = (
            current_time
        )

        trial_expires_at = (
            current_time
            + (
                trial_days
                * 86400
            )
        )


    with db() as conn:

        conn.execute(
            """
            INSERT INTO users (
                phone,
                role,
                full_name,
                business_name,
                city,
                vehicle_type,
                vehicle_year,
                vehicle_number,
                registration_status,
                agreement_accepted,
                agreement_accepted_at,
                trial_started_at,
                trial_expires_at,
                created_at,
                updated_at
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
                1, ?, ?, ?, ?, ?
            )

            ON CONFLICT(phone)
            DO UPDATE SET

                role=excluded.role,

                full_name=excluded.full_name,

                business_name=excluded.business_name,

                city=excluded.city,

                vehicle_type=excluded.vehicle_type,

                vehicle_year=excluded.vehicle_year,

                vehicle_number=excluded.vehicle_number,

                registration_status=
                    excluded.registration_status,

                agreement_accepted=1,

                agreement_accepted_at=
                    excluded.agreement_accepted_at,

                trial_started_at=
                    CASE
                        WHEN users.trial_started_at > 0
                        THEN users.trial_started_at
                        ELSE excluded.trial_started_at
                    END,

                trial_expires_at=
                    CASE
                        WHEN users.trial_expires_at > 0
                        THEN users.trial_expires_at
                        ELSE excluded.trial_expires_at
                    END,

                updated_at=
                    excluded.updated_at
            """,

            (
                phone,
                role,
                full_name,
                business_name,
                city,
                vehicle_type,
                vehicle_year,
                vehicle_number,
                registration_status,
                current_time,
                trial_started_at,
                trial_expires_at,
                current_time,
                current_time
            )
        )

        conn.commit()


    clear_session(
        phone
    )

    return get_user(
        phone
    )


# =========================================================
# שליחת בקשת אישור שליח למנהל
# =========================================================

def notify_admin_new_driver(
    user
):

    if not user:
        return


    send_buttons(
        ADMIN_PHONE,

        f"""
👤 בקשת הרשמה חדשה לשליח

שם: {user.get("full_name") or "-"}
טלפון: {user.get("phone") or "-"}
עיר: {user.get("city") or "-"}

🚗 סוג רכב:
{user.get("vehicle_type") or "-"}

📅 שנת רכב:
{user.get("vehicle_year") or "-"}

🔢 מספר רכב:
{user.get("vehicle_number") or "-"}

לאשר את השליח?
""".strip(),

        [
            (
                f"admin_approve_driver_"
                f"{user['id']}",

                "✅ אשר"
            ),

            (
                f"admin_reject_driver_"
                f"{user['id']}",

                "❌ דחה"
            ),

            (
                f"admin_block_driver_"
                f"{user['id']}",

                "🚫 חסום"
            ),
        ]
    )


# =========================================================
# התחלת הרשמת מזמין
# =========================================================

def start_customer_registration(
    phone
):

    save_session(
        phone,

        "customer_name",

        {
            "role":
                ROLE_CUSTOMER
        }
    )


    send_message(
        phone,

        (
            "📦 הרשמת מזמין משלוח\n\n"
            "מה השם המלא שלך?"
        )
    )


# =========================================================
# התחלת הרשמת שליח
# =========================================================

def start_driver_registration(
    phone
):

    save_session(
        phone,

        "driver_name",

        {
            "role":
                ROLE_DRIVER
        }
    )


    send_message(
        phone,

        (
            "🚚 הרשמת שליח\n\n"
            "מה השם המלא שלך?"
        )
    )


# =========================================================
# טיפול בתהליך הרשמה
# =========================================================

def handle_registration(
    phone,
    text,
    action_id
):

    current_session = get_session(
        phone
    )

    state = current_session.get(
        "state",
        ""
    )

    data = current_session.get(
        "data",
        {}
    )


    # =====================================================
    # בחירת סוג חשבון
    # =====================================================

    if (
        action_id
        == "register_customer"
    ):

        start_customer_registration(
            phone
        )

        return True


    if (
        action_id
        == "register_driver"
    ):

        start_driver_registration(
            phone
        )

        return True


    # =====================================================
    # הרשמת מזמין
    # =====================================================

    if state == "customer_name":

        name = (
            text
            or ""
        ).strip()


        if len(name) < 2:

            send_message(
                phone,
                (
                    "נא לשלוח שם מלא תקין."
                )
            )

            return True


        data["full_name"] = name


        save_session(
            phone,

            "customer_business",

            data
        )


        send_message(
            phone,

            (
                "🏢 מה שם העסק?\n\n"
                "אם אין עסק, כתוב:\n"
                "אין"
            )
        )

        return True


    if state == "customer_business":

        business_name = (
            text
            or ""
        ).strip()


        if business_name == "אין":

            business_name = ""


        data[
            "business_name"
        ] = business_name


        save_session(
            phone,

            "customer_city",

            data
        )


        send_message(
            phone,

            (
                "📍 באיזו עיר אתה נמצא?"
            )
        )

        return True


    if state == "customer_city":

        city = (
            text
            or ""
        ).strip()


        if not city:

            send_message(
                phone,
                "נא לשלוח שם עיר."
            )

            return True


        data["city"] = city


        save_session(
            phone,

            "customer_agreement",

            data
        )


        send_buttons(
            phone,

            customer_agreement(),

            [
                (
                    "customer_agree",
                    "✅ אני מסכים"
                ),

                (
                    "registration_cancel",
                    "❌ ביטול"
                ),
            ]
        )

        return True


    if (
        state
        == "customer_agreement"
    ):

        if (
            action_id
            == "registration_cancel"
        ):

            clear_session(
                phone
            )

            show_role_choice(
                phone
            )

            return True


        if (
            action_id
            != "customer_agree"
        ):

            send_message(
                phone,
                (
                    "כדי לסיים את ההרשמה "
                    "יש לאשר את תנאי השימוש."
                )
            )

            return True


        user = create_or_update_user(

            phone=
                phone,

            role=
                ROLE_CUSTOMER,

            full_name=
                data.get(
                    "full_name",
                    ""
                ),

            business_name=
                data.get(
                    "business_name",
                    ""
                ),

            city=
                data.get(
                    "city",
                    ""
                ),

            registration_status=
                REG_ACTIVE
        )


        send_message(
            phone,

            f"""
✅ ההרשמה הושלמה בהצלחה!

ברוך הבא ל{BOT_NAME}.

מעכשיו המספר שלך שמור כמזמין משלוחים.
אין צורך להירשם מחדש בכל הזמנה.
""".strip()
        )


        show_customer_menu(
            phone
        )

        return True


    # =====================================================
    # הרשמת שליח
    # =====================================================

    if state == "driver_name":

        name = (
            text
            or ""
        ).strip()


        if len(name) < 2:

            send_message(
                phone,
                (
                    "נא לשלוח שם מלא תקין."
                )
            )

            return True


        data["full_name"] = name


        save_session(
            phone,

            "driver_city",

            data
        )


        send_message(
            phone,

            (
                "📍 באיזו עיר אתה גר?"
            )
        )

        return True


    if state == "driver_city":

        city = (
            text
            or ""
        ).strip()


        if not city:

            send_message(
                phone,
                "נא לשלוח שם עיר."
            )

            return True


        data["city"] = city


        save_session(
            phone,

            "driver_vehicle_type",

            data
        )


        send_message(
            phone,

            (
                "🚗 איזה סוג רכב יש לך?\n\n"
                "לדוגמה:\n"
                "רכב פרטי\n"
                "אופנוע\n"
                "קטנוע\n"
                "מסחרית"
            )
        )

        return True


    if (
        state
        == "driver_vehicle_type"
    ):

        vehicle_type = (
            text
            or ""
        ).strip()


        if not vehicle_type:

            send_message(
                phone,
                (
                    "נא לשלוח את סוג הרכב."
                )
            )

            return True


        data[
            "vehicle_type"
        ] = vehicle_type


        save_session(
            phone,

            "driver_vehicle_year",

            data
        )


        send_message(
            phone,

            (
                "📅 מה שנת הרכב?\n\n"
                "לדוגמה:\n"
                "2022"
            )
        )

        return True


    if (
        state
        == "driver_vehicle_year"
    ):

        vehicle_year = (
            text
            or ""
        ).strip()


        if (
            not vehicle_year.isdigit()
            or len(vehicle_year) != 4
        ):

            send_message(
                phone,
                (
                    "נא לשלוח שנת רכב "
                    "ב-4 ספרות.\n"
                    "לדוגמה: 2022"
                )
            )

            return True


        data[
            "vehicle_year"
        ] = vehicle_year


        save_session(
            phone,

            "driver_vehicle_number",

            data
        )


        send_message(
            phone,

            (
                "🔢 מה מספר הרכב?"
            )
        )

        return True


    if (
        state
        == "driver_vehicle_number"
    ):

        vehicle_number = re.sub(
            r"\s+",
            "",
            text
            or ""
        )


        if len(vehicle_number) < 5:

            send_message(
                phone,
                (
                    "מספר הרכב לא נראה תקין.\n"
                    "נסה שוב."
                )
            )

            return True


        data[
            "vehicle_number"
        ] = vehicle_number


        save_session(
            phone,

            "driver_agreement",

            data
        )


        send_buttons(
            phone,

            driver_agreement(),

            [
                (
                    "driver_agree",
                    "✅ אני מסכים"
                ),

                (
                    "registration_cancel",
                    "❌ ביטול"
                ),
            ]
        )

        return True


    if (
        state
        == "driver_agreement"
    ):

        if (
            action_id
            == "registration_cancel"
        ):

            clear_session(
                phone
            )

            show_role_choice(
                phone
            )

            return True


    if state == "driver_agreement":
        if action_id == "registration_cancel":
            clear_session(phone)
            show_role_choice(phone)
            return True

        if action_id != "driver_agree":
            send_message(
                phone,
                "כדי להמשיך בהרשמה יש לאשר את הצהרת השליח."
            )
            return True

        save_session(
            phone,
            "driver_id_photo",
            data
        )

        send_message(
            phone,
            """📸 צילום תעודת זהות

כדי להמשיך בהרשמה לשליחובוט, יש לשלוח עכשיו צילום ברור של תעודת הזהות שלך.

📌 יש לשלוח את התמונה כתמונה ב-WhatsApp."""
        )

        return True

    return False            

# =========================================================
# אישור שליח על ידי מנהל
# =========================================================

def approve_driver(
    user_id
):

    user = get_user_by_id(
        user_id
    )


    if not user:

        return None


    if (
        user.get("role")
        != ROLE_DRIVER
    ):

        return None


    current_time = now_ts()


    trial_days = int(
        get_setting(
            "trial_days",
            "60"
        )
    )


    # הניסיון מתחיל ביום האישור בפועל
    trial_expires_at = (
        current_time
        + (
            trial_days
            * 86400
        )
    )


    with db() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                registration_status=?,

                is_blocked=0,

                approved_at=?,

                trial_started_at=?,

                trial_expires_at=?,

                updated_at=?

            WHERE id=?
            """,

            (
                REG_ACTIVE,
                current_time,
                current_time,
                trial_expires_at,
                current_time,
                user_id
            )
        )

        conn.commit()


    updated_user = get_user_by_id(
        user_id
    )


    log_admin_action(
        "APPROVE_DRIVER",

        target_phone=
            updated_user.get(
                "phone",
                ""
            ),

        reference_id=
            user_id
    )


    send_message(
        updated_user["phone"],

        f"""
🎉 ההרשמה שלך אושרה!

ברוך הבא כשליח ב{BOT_NAME} 🚚

🎁 קיבלת {trial_days} ימי ניסיון חינם.

תקופת הניסיון בתוקף עד:
{format_date(trial_expires_at)}

מומלץ לקרוא את "מדריך לשליח" לפני לקיחת המשלוח הראשון.
""".strip()
    )


    show_driver_menu(
        updated_user["phone"],
        updated_user
    )


    return updated_user


# =========================================================
# דחיית שליח
# =========================================================

def reject_driver(
    user_id
):

    user = get_user_by_id(
        user_id
    )


    if not user:

        return None


    with db() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                registration_status=?,

                rejected_at=?,

                updated_at=?

            WHERE id=?
            """,

            (
                REG_REJECTED,
                now_ts(),
                now_ts(),
                user_id
            )
        )

        conn.commit()


    updated_user = get_user_by_id(
        user_id
    )


    log_admin_action(
        "REJECT_DRIVER",

        target_phone=
            updated_user.get(
                "phone",
                ""
            ),

        reference_id=
            user_id
    )


    send_message(
        updated_user["phone"],

        f"""
❌ בקשת ההרשמה שלך כשליח ב{BOT_NAME}
לא אושרה כרגע.

אם לדעתך מדובר בטעות,
ניתן לפנות לנציג.
""".strip()
    )


    return updated_user


# =========================================================
# חסימת משתמש
# =========================================================

def block_user_by_phone(
    target_phone
):

    target_phone = normalize_phone(
        target_phone
    )


    user = get_user(
        target_phone
    )


    if not user:

        return False


    with db() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                is_blocked=1,

                registration_status=?,

                updated_at=?

            WHERE phone=?
            """,

            (
                REG_BLOCKED,
                now_ts(),
                target_phone
            )
        )

        conn.commit()


    log_admin_action(
        "BLOCK_USER",

        target_phone=
            target_phone
    )


    send_message(
        target_phone,

        f"""
🚫 החשבון שלך ב{BOT_NAME} נחסם.

לפרטים ניתן לפנות לתמיכה.
""".strip()
    )


    return True


# =========================================================
# הסרת חסימה
# =========================================================

def unblock_user_by_phone(
    target_phone
):

    target_phone = normalize_phone(
        target_phone
    )


    user = get_user(
        target_phone
    )


    if not user:

        return False


    # אם זה שליח שהיה כבר מאושר בעבר
    # נחזיר אותו למצב פעיל.
    new_status = REG_ACTIVE


    with db() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                is_blocked=0,

                registration_status=?,

                updated_at=?

            WHERE phone=?
            """,

            (
                new_status,
                now_ts(),
                target_phone
            )
        )

        conn.commit()


    log_admin_action(
        "UNBLOCK_USER",

        target_phone=
            target_phone
    )


    send_message(
        target_phone,

        f"""
🔓 החסימה בחשבון {BOT_NAME} הוסרה.

ניתן לחזור להשתמש במערכת.
""".strip()
    )


    return True


# =========================================================
# הוספת סדרן
# =========================================================

def add_dispatcher(
    target_phone
):

    target_phone = normalize_phone(
        target_phone
    )


    if not target_phone:

        return False


    # לא ניתן לשנות את המנהל
    if target_phone == ADMIN_PHONE:

        return False


    user = get_user(
        target_phone
    )


    current_time = now_ts()


    # אם המשתמש כבר קיים במערכת
    if user:

        with db() as conn:

            conn.execute(
                """
                UPDATE users

                SET
                    role=?,

                    registration_status=?,

                    is_blocked=0,

                    updated_at=?

                WHERE phone=?
                """,

                (
                    ROLE_DISPATCHER,
                    REG_ACTIVE,
                    current_time,
                    target_phone
                )
            )

            conn.commit()


    # אם המספר עדיין לא נרשם
    else:

        with db() as conn:

            conn.execute(
                """
                INSERT INTO users (
                    phone,
                    role,
                    full_name,
                    registration_status,
                    is_blocked,
                    agreement_accepted,
                    approved_at,
                    created_at,
                    updated_at
                )

                VALUES (
                    ?, ?, '', ?, 0, 1, ?, ?, ?
                )
                """,

                (
                    target_phone,
                    ROLE_DISPATCHER,
                    REG_ACTIVE,
                    current_time,
                    current_time,
                    current_time
                )
            )

            conn.commit()


    log_admin_action(
        "ADD_DISPATCHER",

        target_phone=
            target_phone
    )


    send_message(
        target_phone,

        f"""
👨‍💼 הוגדרת כסדרן ב{BOT_NAME}.

כסדרן אתה יכול:
• לפרסם ולנהל משלוחים
• לפעול גם כשליח
• להשתמש במערכת ללא תשלום מנוי

שלח "תפריט" כדי להתחיל.
""".strip()
    )


    return True


# =========================================================
# הסרת סדרן
# =========================================================

def remove_dispatcher(
    target_phone
):

    target_phone = normalize_phone(
        target_phone
    )


    if not target_phone:

        return False


    user = get_user(
        target_phone
    )


    if not user:

        return False


    if (
        user.get("role")
        != ROLE_DISPATCHER
    ):

        return False


    # בהסרת סדרן הוא הופך לשליח רגיל.
    # המנהל יכול לחסום אותו בנפרד אם צריך.
    with db() as conn:

        conn.execute(
            """
            UPDATE users

            SET
                role=?,

                registration_status=?,

                updated_at=?

            WHERE phone=?
            """,

            (
                ROLE_DRIVER,
                REG_ACTIVE,
                now_ts(),
                target_phone
            )
        )

        conn.commit()


    log_admin_action(
        "REMOVE_DISPATCHER",

        target_phone=
            target_phone
    )


    send_message(
        target_phone,

        f"""
ℹ️ הרשאת הסדרן שלך ב{BOT_NAME} הוסרה.

החשבון שלך מוגדר כעת כחשבון שליח רגיל.
""".strip()
    )


    return True


# =========================================================
# רשימת סדרנים
# =========================================================

def send_dispatcher_list(
    phone
):

    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM users

            WHERE role=?

            ORDER BY
                full_name ASC,
                id ASC
            """,

            (
                ROLE_DISPATCHER,
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            (
                "📋 אין כרגע סדרנים במערכת."
            )
        )

        return


    lines = [
        "📋 רשימת סדרנים",
        ""
    ]


    for row in rows:

        user = dict(row)

        name = (
            user.get("full_name")
            or "ללא שם"
        )

        number = (
            user.get("phone")
            or "-"
        )


        lines.append(
            f"👨‍💼 {name}"
        )

        lines.append(
            f"📱 {number}"
        )

        lines.append(
            ""
        )


    send_message(
        phone,
        "\n".join(lines)
    )


# =========================================================
# רשימת חסומים
# =========================================================

def send_blocked_users(
    phone
):

    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM users

            WHERE is_blocked=1

            ORDER BY
                updated_at DESC
            """
        ).fetchall()


    if not rows:

        send_message(
            phone,
            "📋 אין כרגע משתמשים חסומים."
        )

        return


    lines = [
        "🚫 משתמשים חסומים",
        ""
    ]


    for row in rows:

        user = dict(row)


        lines.append(
            (
                f"👤 "
                f"{user.get('full_name') or 'ללא שם'}"
            )
        )


        lines.append(
            (
                f"📱 "
                f"{user.get('phone') or '-'}"
            )
        )


        role = user.get(
            "role",
            ""
        )


        if role == ROLE_DRIVER:

            role_text = "שליח"

        elif role == ROLE_CUSTOMER:

            role_text = "מזמין"

        elif role == ROLE_DISPATCHER:

            role_text = "סדרן"

        else:

            role_text = role or "-"


        lines.append(
            f"סוג: {role_text}"
        )

        lines.append(
            ""
        )


    send_message(
        phone,
        "\n".join(lines)
    )


# =========================================================
# שליחים שממתינים לאישור
# =========================================================

def show_pending_drivers(
    phone
):

    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM users

            WHERE
                role=?
                AND registration_status=?
                AND is_blocked=0

            ORDER BY created_at ASC

            LIMIT 20
            """,

            (
                ROLE_DRIVER,
                REG_WAITING
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            "✅ אין כרגע שליחים שממתינים לאישור."
        )

        return


    # כל שליח נשלח בנפרד
    # כדי שיהיו כפתורי אישור / דחייה / חסימה.
    for row in rows:

        user = dict(row)

        notify_admin_new_driver(
            user
        )


# =========================================================
# סטטיסטיקות מערכת למנהל
# =========================================================

def send_admin_statistics(
    phone
):

    with db() as conn:

        total_users = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"]


        total_customers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role=?
            """,

            (
                ROLE_CUSTOMER,
            )
        ).fetchone()["total"]


        total_drivers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role=?
            """,

            (
                ROLE_DRIVER,
            )
        ).fetchone()["total"]


        approved_drivers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users

            WHERE
                role=?
                AND registration_status=?
                AND is_blocked=0
            """,

            (
                ROLE_DRIVER,
                REG_ACTIVE
            )
        ).fetchone()["total"]


        pending_drivers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users

            WHERE
                role=?
                AND registration_status=?
            """,

            (
                ROLE_DRIVER,
                REG_WAITING
            )
        ).fetchone()["total"]


        dispatchers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role=?
            """,

            (
                ROLE_DISPATCHER,
            )
        ).fetchone()["total"]


        blocked = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE is_blocked=1
            """
        ).fetchone()["total"]


        open_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status IN (?, ?)
            """,

            (
                SHIP_OPEN,
                SHIP_HAS_INTEREST
            )
        ).fetchone()["total"]


        assigned_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status=?
            """,

            (
                SHIP_ASSIGNED,
            )
        ).fetchone()["total"]


        completed_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status=?
            """,

            (
                SHIP_COMPLETED,
            )
        ).fetchone()["total"]


        waiting_payments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM payments
            WHERE status=?
            """,

            (
                PAY_WAITING_ADMIN,
            )
        ).fetchone()["total"]


        open_support = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM support_requests
            WHERE status='OPEN'
            """
        ).fetchone()["total"]


    send_message(
        phone,

        f"""
📊 נתוני מערכת - {BOT_NAME}

👥 משתמשים
סה"כ: {total_users}
מזמינים: {total_customers}
שליחים: {total_drivers}
שליחים מאושרים: {approved_drivers}
שליחים ממתינים: {pending_drivers}
סדרנים: {dispatchers}
חסומים: {blocked}

📦 משלוחים
פתוחים: {open_shipments}
שובצו לשליח: {assigned_shipments}
הושלמו: {completed_shipments}

💳 תשלומים
ממתינים לאישור: {waiting_payments}

💬 תמיכה
פניות פתוחות: {open_support}
""".strip()
    )
# =========================================================
# משלוחים - פונקציות בסיס
# =========================================================

def get_shipment(
    shipment_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE id=?
            """,
            (
                shipment_id,
            )
        ).fetchone()

    return row_to_dict(
        row
    )


def get_interest(
    shipment_id,
    driver_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM shipment_interests

            WHERE
                shipment_id=?
                AND driver_id=?
            """,
            (
                shipment_id,
                driver_id
            )
        ).fetchone()

    return row_to_dict(
        row
    )


# =========================================================
# התחלת פרסום משלוח
# =========================================================

def start_new_shipment(
    phone
):

    user = get_user(
        phone
    )


    if not user:

        show_role_choice(
            phone
        )

        return


    if (
        user.get("role")
        not in (
            ROLE_CUSTOMER,
            ROLE_DISPATCHER
        )
    ):

        send_message(
            phone,
            (
                "אפשרות זו מיועדת "
                "למזמין או לסדרן."
            )
        )

        return


    save_session(
        phone,

        "shipment_origin_city",

        {}
    )


    send_message(
        phone,

        """
📦 פרסום משלוח חדש

מאיזו עיר המשלוח יוצא?
""".strip()
    )


# =========================================================
# תהליך יצירת משלוח
# =========================================================

def handle_new_shipment(
    phone,
    text,
    action_id
):

    current_session = get_session(
        phone
    )

    state = current_session.get(
        "state",
        ""
    )

    data = current_session.get(
        "data",
        {}
    )


    if state == "shipment_origin_city":

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לשלוח עיר איסוף."
            )

            return True


        data[
            "origin_city"
        ] = value


        save_session(
            phone,

            "shipment_pickup_address",

            data
        )


        send_message(
            phone,

            """
📍 מה כתובת האיסוף המלאה?

לדוגמה:
הרצל 10, ירושלים
""".strip()
        )

        return True


    if (
        state
        == "shipment_pickup_address"
    ):

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לשלוח כתובת איסוף."
            )

            return True


        data[
            "pickup_address"
        ] = value


        save_session(
            phone,

            "shipment_destination_city",

            data
        )


        send_message(
            phone,
            "🏁 לאיזו עיר המשלוח מיועד?"
        )

        return True


    if (
        state
        == "shipment_destination_city"
    ):

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לשלוח עיר יעד."
            )

            return True


        data[
            "destination_city"
        ] = value


        save_session(
            phone,

            "shipment_dropoff_address",

            data
        )


        send_message(
            phone,

            """
📍 מה כתובת המסירה המלאה?
""".strip()
        )

        return True


    if (
        state
        == "shipment_dropoff_address"
    ):

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לשלוח כתובת מסירה."
            )

            return True


        data[
            "dropoff_address"
        ] = value


        save_session(
            phone,

            "shipment_pickup_time",

            data
        )


        send_message(
            phone,

            """
🕐 מתי צריך לאסוף את המשלוח?

אפשר לכתוב למשל:
היום 16:30
מחר בבוקר
בהקדם האפשרי
""".strip()
        )

        return True


    if (
        state
        == "shipment_pickup_time"
    ):

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לציין מועד איסוף."
            )

            return True


        data[
            "pickup_time"
        ] = value


        save_session(
            phone,

            "shipment_package",

            data
        )


        send_message(
            phone,

            """
📦 מה יש במשלוח?

נא לתאר בקצרה את החבילה.
""".strip()
        )

        return True


    if state == "shipment_package":

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לתאר את המשלוח."
            )

            return True


        data[
            "package_description"
        ] = value


        save_session(
            phone,

            "shipment_recipient_name",

            data
        )


        send_message(
            phone,

            """
👤 מה שם מקבל המשלוח?
""".strip()
        )

        return True


    if (
        state
        == "shipment_recipient_name"
    ):

        value = (
            text
            or ""
        ).strip()


        if not value:

            send_message(
                phone,
                "נא לשלוח שם נמען."
            )

            return True


        data[
            "recipient_name"
        ] = value


        save_session(
            phone,

            "shipment_recipient_phone",

            data
        )


        send_message(
            phone,

            """
📱 מה מספר הטלפון של הנמען?
""".strip()
        )

        return True


    if (
        state
        == "shipment_recipient_phone"
    ):

        value = normalize_phone(
            text
        )


        if len(value) < 9:

            send_message(
                phone,
                (
                    "מספר הטלפון לא נראה תקין.\n"
                    "נסה שוב."
                )
            )

            return True


        data[
            "recipient_phone"
        ] = value


        save_session(
            phone,

            "shipment_price",

            data
        )


        send_message(
            phone,

            """
💰 כמה אתה מציע לשליח עבור המשלוח?

שלח מספר בלבד.

לדוגמה:
85
""".strip()
        )

        return True


    if state == "shipment_price":

        raw_price = (
            text
            or ""
        ).strip()


        raw_price = raw_price.replace(
            ",",
            "."
        )


        try:

            price = float(
                raw_price
            )

        except Exception:

            price = 0


        if price <= 0:

            send_message(
                phone,

                (
                    "נא לשלוח מחיר תקין.\n"
                    "לדוגמה: 85"
                )
            )

            return True


        data["price"] = price


        save_session(
            phone,

            "shipment_notes",

            data
        )


        send_message(
            phone,

            """
📝 הערות נוספות?

אם אין, כתוב:
אין
""".strip()
        )

        return True


    if state == "shipment_notes":

        notes = (
            text
            or ""
        ).strip()


        if notes == "אין":

            notes = ""


        data["notes"] = notes


        save_session(
            phone,

            "shipment_confirm",

            data
        )


        send_buttons(
            phone,

            f"""
📦 נא לבדוק את פרטי המשלוח:

📍 איסוף:
{data.get("origin_city", "")}
{data.get("pickup_address", "")}

🏁 יעד:
{data.get("destination_city", "")}
{data.get("dropoff_address", "")}

🕐 איסוף:
{data.get("pickup_time", "")}

📦 תכולה:
{data.get("package_description", "")}

👤 נמען:
{data.get("recipient_name", "")}

📱 טלפון:
{data.get("recipient_phone", "")}

💰 מחיר מוצע:
{data.get("price", 0):g} ₪

📝 הערות:
{data.get("notes") or "-"}

לפרסם את המשלוח?
""".strip(),

            [
                (
                    "shipment_confirm_yes",
                    "✅ פרסם"
                ),

                (
                    "shipment_restart",
                    "✏️ התחל מחדש"
                ),

                (
                    "shipment_cancel_new",
                    "❌ ביטול"
                ),
            ]
        )

        return True


    if state == "shipment_confirm":

        if (
            action_id
            == "shipment_restart"
        ):

            start_new_shipment(
                phone
            )

            return True


        if (
            action_id
            == "shipment_cancel_new"
        ):

            clear_session(
                phone
            )

            send_message(
                phone,
                "❌ פרסום המשלוח בוטל."
            )

            show_menu_for_user(
                phone
            )

            return True


        if (
            action_id
            != "shipment_confirm_yes"
        ):

            send_message(
                phone,
                (
                    "בחר אחת מהאפשרויות "
                    "באמצעות הכפתורים."
                )
            )

            return True


        user = get_user(
            phone
        )


        if not user:

            clear_session(
                phone
            )

            show_role_choice(
                phone
            )

            return True


        with db() as conn:

            cursor = conn.execute(
                """
                INSERT INTO shipments (
                    customer_id,
                    created_by_role,
                    status,
                    origin_city,
                    pickup_address,
                    destination_city,
                    dropoff_address,
                    pickup_time,
                    package_description,
                    recipient_name,
                    recipient_phone,
                    price,
                    notes,
                    created_at,
                    updated_at
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,

                (
                    user["id"],
                    user["role"],
                    SHIP_OPEN,
                    data.get(
                        "origin_city",
                        ""
                    ),
                    data.get(
                        "pickup_address",
                        ""
                    ),
                    data.get(
                        "destination_city",
                        ""
                    ),
                    data.get(
                        "dropoff_address",
                        ""
                    ),
                    data.get(
                        "pickup_time",
                        ""
                    ),
                    data.get(
                        "package_description",
                        ""
                    ),
                    data.get(
                        "recipient_name",
                        ""
                    ),
                    data.get(
                        "recipient_phone",
                        ""
                    ),
                    float(
                        data.get(
                            "price",
                            0
                        )
                    ),
                    data.get(
                        "notes",
                        ""
                    ),
                    now_ts(),
                    now_ts()
                )
            )

            shipment_id = (
                cursor.lastrowid
            )

            conn.commit()


        notify_available_drivers(
            shipment_id
        )
        clear_session(
            phone
        )


        send_message(
            phone,

            f"""
✅ המשלוח פורסם בהצלחה!

מספר משלוח:
#{shipment_id}

💰 מחיר מוצע:
{data.get("price", 0):g} ₪

כאשר שליח יתעניין במשלוח,
תקבל הודעה.
""".strip()
        )


        return True


    return False


# =========================================================
# טקסט משלוח לשליח
# =========================================================

def shipment_driver_text(
    shipment
):

    return f"""
📦 משלוח #{shipment["id"]}

📍 איסוף:
{shipment["origin_city"]}
{shipment["pickup_address"]}

🏁 יעד:
{shipment["destination_city"]}
{shipment["dropoff_address"]}

🕐 מועד:
{shipment["pickup_time"]}

📦 תכולה:
{shipment["package_description"]}

💰 מחיר:
{shipment["price"]:g} ₪

⚠️ לפני לחיצה על "אני מעוניין":
ודא שבדקת את המסלול, המחיר,
המועד והזמינות שלך.
""".strip()


# =========================================================
# הצגת משלוחים זמינים לשליח
# =========================================================

def show_open_shipments_to_driver(
    phone,
    city=""
):

    user = get_user(
        phone
    )


    if not user:

        return


    if (
        user.get("role")
        not in (
            ROLE_DRIVER,
            ROLE_DISPATCHER
        )
    ):

        return


    if not driver_has_access(
        user
    ):

        send_buttons(
            phone,

            """
⚠️ תקופת הניסיון או המנוי שלך הסתיימה.

כדי לקבל משלוחים חדשים
יש לחדש את המנוי.
""".strip(),

            [
                (
                    "driver_pay_subscription",
                    "💳 תשלום מנוי"
                ),

                (
                    "support_new",
                    "💬 נציג"
                ),
            ]
        )

        return


    query = """
        SELECT *
        FROM shipments

        WHERE status IN (?, ?)
    """

    params = [
        SHIP_OPEN,
        SHIP_HAS_INTEREST
    ]


    if city:
        query += """
            AND LOWER(origin_city) LIKE LOWER(?)
        """

        pattern = "%" + city.strip() + "%"

        params.append(pattern)   


    query += """
        ORDER BY created_at DESC
        LIMIT 10
    """


    with db() as conn:

        rows = conn.execute(
            query,
            tuple(params)
        ).fetchall()


    if not rows:

        if city:

            send_message(
                phone,

                (
                    f"📭 כרגע אין משלוחים פתוחים "
                    f"ב-{city}."
                )
            )

        else:

            send_message(
                phone,
                "📭 כרגע אין משלוחים פתוחים."
            )

        return


    for row in rows:

        shipment = dict(row)


        existing_interest = (
            get_interest(
                shipment["id"],
                user["id"]
            )
        )


        if existing_interest:

            continue


        send_buttons(
            phone,

            shipment_driver_text(
                shipment
            ),

            [
                (
                    f"driver_interest_"
                    f"{shipment['id']}",

                    "🙋 אני מעוניין"
                ),

                (
                    "driver_menu",
                    "⬅️ תפריט"
                ),
            ]
        )


# =========================================================
# התחלת התעניינות שליח
# =========================================================

def start_driver_interest(
    phone,
    shipment_id
):

    user = get_user(
        phone
    )


    if not user:

        return False


    if (
        user.get("role")
        not in (
            ROLE_DRIVER,
            ROLE_DISPATCHER
        )
    ):

        return False


    if not driver_has_access(
        user
    ):

        show_driver_subscription(
            phone,
            user
        )

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
        shipment.get("status")
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        send_message(
            phone,

            (
                "המשלוח כבר אינו "
                "זמין להתעניינות."
            )
        )

        return True


    if get_interest(
        shipment_id,
        user["id"]
    ):

        send_message(
            phone,

            (
                "כבר סימנת שאתה מעוניין "
                "במשלוח הזה."
            )
        )

        return True


    save_session(
        phone,

        "driver_interest_eta",

        {
            "shipment_id":
                shipment_id
        }
    )


    send_message(
        phone,

        f"""
🙋 משלוח #{shipment_id}

תוך כמה דקות אתה יכול להגיע לנקודת האיסוף?

שלח מספר בלבד.

לדוגמה:
20
""".strip()
    )


    return True


# =========================================================
# שמירת זמן הגעה ושליחת השליח למזמין
# =========================================================

def handle_driver_interest_eta(
    phone,
    text
):

    current_session = get_session(
        phone
    )

    if (
        current_session.get("state")
        != "driver_interest_eta"
    ):

        return False


    data = current_session.get(
        "data",
        {}
    )


    shipment_id = int(
        data.get(
            "shipment_id",
            0
        )
        or 0
    )


    user = get_user(
        phone
    )


    if not user:

        clear_session(
            phone
        )

        return True


    try:

        eta = int(
            (
                text
                or ""
            ).strip()
        )

    except Exception:

        eta = 0


    if (
        eta <= 0
        or eta > 1440
    ):

        send_message(
            phone,

            (
                "נא לשלוח זמן הגעה בדקות.\n"
                "לדוגמה: 20"
            )
        )

        return True


    shipment = get_shipment(
        shipment_id
    )


    if (
        not shipment
        or shipment.get("status")
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        clear_session(
            phone
        )

        send_message(
            phone,

            (
                "המשלוח כבר אינו זמין."
            )
        )

        return True


    with db() as conn:

        conn.execute(
            """
            INSERT INTO shipment_interests (
                shipment_id,
                driver_id,
                eta_minutes,
                status,
                created_at,
                updated_at
            )

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(
                shipment_id,
                driver_id
            )
            DO UPDATE SET

                eta_minutes=
                    excluded.eta_minutes,

                status=
                    excluded.status,

                updated_at=
                    excluded.updated_at
            """,

            (
                shipment_id,
                user["id"],
                eta,
                INTEREST_INTERESTED,
                now_ts(),
                now_ts()
            )
        )


        conn.execute(
                    """
            UPDATE shipments

            SET
                status=?,
                updated_at=?

            WHERE id=?
            """,

            (
                SHIP_HAS_INTEREST,
                now_ts(),
                shipment_id
            )
        )

        conn.commit()


    clear_session(
        phone
    )


    send_message(
        phone,

        f"""
✅ ההתעניינות נשלחה למזמין.

משלוח #{shipment_id}

⏱️ ציינת שתוכל להגיע תוך:
{eta} דקות

אם המזמין יבחר בך,
תקבל הודעה אוטומטית.
""".strip()
    )


    customer = get_user_by_id(
        shipment["customer_id"]
    )


    if customer:

        rating = get_driver_rating(
            user["id"]
        )

        completed = get_driver_completed_count(
            user["id"]
        )


        if rating["count"] > 0:

            rating_text = (
                f"⭐ {rating['average']:.1f}/5 "
                f"({rating['count']} דירוגים)"
            )

        else:

            rating_text = (
                "⭐ עדיין אין דירוגים"
            )


        send_buttons(
            customer["phone"],

            f"""
🙋 שליח מעוניין במשלוח #{shipment_id}

👤 שם:
{user.get("full_name") or "-"}

🚗 רכב:
{user.get("vehicle_type") or "-"}
{user.get("vehicle_year") or ""}

⏱️ יכול להגיע תוך:
{eta} דקות

{rating_text}

📦 משלוחים שהושלמו:
{completed}

💰 המחיר שפרסמת:
{shipment["price"]:g} ₪

האם לבחור בשליח הזה?
""".strip(),

            [
                (
                    f"customer_select_driver_"
                    f"{shipment_id}_"
                    f"{user['id']}",
                    "✅ בחר שליח"
                ),

                (
                    f"customer_view_interest_"
                    f"{shipment_id}",
                    "👥 מתעניינים"
                ),

                (
                    f"customer_shipment_"
                    f"{shipment_id}",
                    "📦 משלוח"
                ),
            ]
        )


    return True


# =========================================================
# הצגת כל המתעניינים במשלוח
# =========================================================

def show_shipment_interests(
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


    customer = get_user(
        phone
    )


    if (
        not customer
        or (
            customer["id"] != shipment["customer_id"]
            and phone != ADMIN_PHONE
        )
    ):

        send_message(
            phone,
            "אין הרשאה לצפות במשלוח הזה."
        )

        return


    with db() as conn:

        rows = conn.execute(
            """
            SELECT
                shipment_interests.*,
                users.full_name,
                users.phone,
                users.vehicle_type,
                users.vehicle_year,
                users.vehicle_number

            FROM shipment_interests

            JOIN users
                ON users.id =
                    shipment_interests.driver_id

            WHERE
                shipment_interests.shipment_id=?
                AND shipment_interests.status=?

            ORDER BY
                shipment_interests.eta_minutes ASC,
                shipment_interests.created_at ASC
            """,

            (
                shipment_id,
                INTEREST_INTERESTED
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            (
                f"📭 עדיין אין שליחים "
                f"שמעוניינים במשלוח #{shipment_id}."
            )
        )

        return


    for row in rows:

        interest = dict(row)

        rating = get_driver_rating(
            interest["driver_id"]
        )

        completed = get_driver_completed_count(
            interest["driver_id"]
        )


        if rating["count"]:

            rating_text = (
                f"⭐ {rating['average']:.1f}/5 "
                f"({rating['count']} דירוגים)"
            )

        else:

            rating_text = (
                "⭐ עדיין אין דירוגים"
            )


        send_buttons(
            phone,

            f"""
🚚 שליח מעוניין

👤 {interest.get("full_name") or "-"}

🚗 {interest.get("vehicle_type") or "-"}
{interest.get("vehicle_year") or ""}

⏱️ הגעה:
{interest.get("eta_minutes", 0)} דקות

{rating_text}

📦 משלוחים שהושלמו:
{completed}
""".strip(),

            [
                (
                    f"customer_select_driver_"
                    f"{shipment_id}_"
                    f"{interest['driver_id']}",
                    "✅ בחר שליח"
                )
            ]
        )


# =========================================================
# בחירת שליח על ידי המזמין
# =========================================================

def select_driver_for_shipment(
    phone,
    shipment_id,
    driver_id
):

    shipment = get_shipment(
        shipment_id
    )


    if not shipment:

        send_message(
            phone,
            "המשלוח לא נמצא."
        )

        return False


    customer = get_user(
        phone
    )


    if (
        not customer
        or (
            customer["id"] != shipment["customer_id"]
            and phone != ADMIN_PHONE
        )
    ):

        send_message(
            phone,
            "אין הרשאה לבחור שליח למשלוח הזה."
        )

        return False


    if (
        shipment.get("status")
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        send_message(
            phone,
            (
                "כבר נבחר שליח למשלוח "
                "או שהמשלוח אינו פעיל."
            )
        )

        return False


    driver = get_user_by_id(
        driver_id
    )


    if not driver:

        send_message(
            phone,
            "השליח לא נמצא."
        )

        return False


    interest = get_interest(
        shipment_id,
        driver_id
    )


    if not interest:

        send_message(
            phone,
            (
                "השליח הזה אינו מסומן "
                "כמעוניין במשלוח."
            )
        )

        return False


    with db() as conn:

        conn.execute(
            """
            UPDATE shipments

            SET
                assigned_driver_id=?,
                status=?,
                assigned_at=?,
                updated_at=?

            WHERE id=?
            """,

            (
                driver_id,
                SHIP_ASSIGNED,
                now_ts(),
                now_ts(),
                shipment_id
            )
        )


        conn.execute(
            """
            UPDATE shipment_interests

            SET
                status=?,
                updated_at=?

            WHERE
                shipment_id=?
                AND driver_id=?
            """,

            (
                INTEREST_SELECTED,
                now_ts(),
                shipment_id,
                driver_id
            )
        )


        conn.execute(
            """
            UPDATE shipment_interests

            SET
                status=?,
                updated_at=?

            WHERE
                shipment_id=?
                AND driver_id<>?
            """,

            (
                INTEREST_REJECTED,
                now_ts(),
                shipment_id,
                driver_id
            )
        )

        conn.commit()


        customer_phone = normalize_phone(
        phone
    )

    driver_phone = normalize_phone(
        driver.get(
            "phone",
            ""
        )
    )

    driver_chat_url = (
        f"https://wa.me/{driver_phone}"
        f"?text=שלום%20אני%20המזמין%20של%20משלוח%20"
        f"%23{shipment_id}%20דרך%20שליחובוט"
    )


    # הודעה למזמין
    send_message(
        phone,

        f"""
✅ השליח נבחר בהצלחה!

📦 משלוח #{shipment_id}

🚚 השליח שנבחר:
{driver.get("full_name") or "-"}

📱 מספר השליח:
{driver_phone}

⏱️ זמן הגעה:
{interest.get("eta_minutes", 0)} דקות

💬 לפנייה ישירה לשליח בוואטסאפ:
{driver_chat_url}

ניתן ללחוץ על הקישור ולפתוח צ'אט פרטי עם השליח.
""".strip()
    )


    # הודעה לשליח שנבחר
    send_message(
        driver_phone,

        f"""
🎉 נבחרת למשלוח #{shipment_id}!

המזמין בחר בך לביצוע המשלוח.

👤 המזמין:
{customer.get("full_name") or "-"}

📱 מספר המזמין:
{customer_phone}

המזמין יכול ליצור איתך קשר ישירות בוואטסאפ.

📍 איסוף:
{shipment["origin_city"]}
{shipment["pickup_address"]}

🏁 יעד:
{shipment["destination_city"]}
{shipment["dropoff_address"]}

🕐 מועד:
{shipment["pickup_time"]}

💰 מחיר:
{shipment["price"]:g} ₪

📦 תכולה:
{shipment["package_description"]}

👤 נמען:
{shipment["recipient_name"]}

📱 טלפון נמען:
{shipment["recipient_phone"]}
""".strip()
    )

    return True


# =========================================================
# המשלוחים שלי - מזמין
# =========================================================

def show_customer_shipments(
    phone
):

    user = get_user(
        phone
    )


    if not user:

        return


    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM shipments

            WHERE customer_id=?

            ORDER BY created_at DESC

            LIMIT 10
            """,

            (
                user["id"],
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            "📭 עדיין לא פרסמת משלוחים."
        )

        return


    for row in rows:

        shipment = dict(row)


        if (
            shipment["status"]
            in (
                SHIP_OPEN,
                SHIP_HAS_INTEREST
            )
        ):

            send_buttons(
                phone,

                f"""
📦 משלוח #{shipment["id"]}

🟢 פתוח

📍 {shipment["origin_city"]}
➡️ {shipment["destination_city"]}

💰 {shipment["price"]:g} ₪

🕐 {shipment["pickup_time"]}
""".strip(),

                [
                    (
                        f"customer_view_interest_"
                        f"{shipment['id']}",
                        "👥 מתעניינים"
                    ),

                    (
                        f"customer_edit_"
                        f"{shipment['id']}",
                        "✏️ עריכה"
                    ),

                    (
                        f"customer_cancel_"
                        f"{shipment['id']}",
                        "❌ ביטול"
                    ),
                ]
            )


        elif shipment["status"] == SHIP_ASSIGNED:

            driver = get_user_by_id(
                shipment["assigned_driver_id"]
            )


            send_buttons(
                phone,

                f"""
📦 משלוח #{shipment["id"]}

🚚 שובץ לשליח

שליח:
{driver.get("full_name") if driver else "-"}

📱:
{driver.get("phone") if driver else "-"}

📍 {shipment["origin_city"]}
➡️ {shipment["destination_city"]}

💰 {shipment["price"]:g} ₪
""".strip(),

                [
                    (
                        f"customer_complete_"
                        f"{shipment['id']}",
                        "✅ המשלוח נמסר"
                    ),

                    (
                        "support_new",
                        "💬 נציג"
                    ),
                ]
            )


        elif shipment["status"] == SHIP_COMPLETED:

            send_message(
                phone,

                f"""
📦 משלוח #{shipment["id"]}

✅ הושלם

📍 {shipment["origin_city"]}
➡️ {shipment["destination_city"]}

💰 {shipment["price"]:g} ₪
""".strip()
            )


        elif shipment["status"] == SHIP_CANCELLED:

            send_message(
                phone,
                f"📦 משלוח #{shipment['id']}\n\n❌ בוטל"
            )


# =========================================================
# המשלוחים שלי - שליח
# =========================================================

def show_driver_shipments(
    phone
):

    user = get_user(
        phone
    )


    if not user:

        return


    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM shipments

            WHERE
                assigned_driver_id=?
                AND status IN (?, ?)

            ORDER BY updated_at DESC

            LIMIT 10
            """,

            (
                user["id"],
                SHIP_ASSIGNED,
                SHIP_COMPLETED
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            (
                "📭 אין לך כרגע "
                "משלוחים ששובצת אליהם."
            )
        )

        return


    for row in rows:

        shipment = dict(row)


        if shipment["status"] == SHIP_ASSIGNED:

            send_message(
                phone,

                f"""
🚚 משלוח #{shipment["id"]}

📍 איסוף:
{shipment["origin_city"]}
{shipment["pickup_address"]}

🏁 יעד:
{shipment["destination_city"]}
{shipment["dropoff_address"]}

🕐:
{shipment["pickup_time"]}

📦:
{shipment["package_description"]}

👤 נמען:
{shipment["recipient_name"]}

📱:
{shipment["recipient_phone"]}

💰:
{shipment["price"]:g} ₪
""".strip()
            )

        else:

            send_message(
                phone,

                f"""
🚚 משלוח #{shipment["id"]}

✅ המשלוח הושלם

📍 {shipment["origin_city"]}
➡️ {shipment["destination_city"]}

💰 {shipment["price"]:g} ₪
""".strip()
            )
# =========================================================
# עריכת משלוח
# =========================================================

def show_edit_shipment_menu(
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

    user = get_user(
        phone
    )

    if (
        not user
        or user["id"] != shipment["customer_id"]
    ):

        send_message(
            phone,
            "אין הרשאה לערוך את המשלוח הזה."
        )
        return

    if (
        shipment["status"]
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        send_message(
            phone,
            (
                "לא ניתן לערוך את המשלוח "
                "לאחר בחירת שליח."
            )
        )
        return

    send_list(
        phone,

        f"""
✏️ עריכת משלוח #{shipment_id}

בחר מה ברצונך לשנות:
""".strip(),

        "בחר עריכה",

        [
            (
                f"edit_price_{shipment_id}",
                "💰 שינוי מחיר",
                f"כעת {shipment['price']:g} ₪"
            ),

            (
                f"edit_pickup_{shipment_id}",
                "📍 כתובת איסוף",
                "שינוי כתובת האיסוף"
            ),

            (
                f"edit_dropoff_{shipment_id}",
                "🏁 כתובת יעד",
                "שינוי כתובת המסירה"
            ),

            (
                f"edit_time_{shipment_id}",
                "🕐 מועד איסוף",
                "שינוי המועד"
            ),

            (
                f"edit_package_{shipment_id}",
                "📦 תיאור משלוח",
                "שינוי תיאור החבילה"
            ),

            (
                f"edit_notes_{shipment_id}",
                "📝 הערות",
                "שינוי הערות"
            ),
        ]
    )


# =========================================================
# התחלת עריכת שדה
# =========================================================

def start_shipment_edit(
    phone,
    shipment_id,
    field
):

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:

        send_message(
            phone,
            "המשלוח לא נמצא."
        )
        return True

    user = get_user(
        phone
    )

    if (
        not user
        or user["id"] != shipment["customer_id"]
    ):

        send_message(
            phone,
            "אין הרשאה לערוך את המשלוח."
        )
        return True

    if (
        shipment["status"]
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        send_message(
            phone,
            (
                "לא ניתן לערוך משלוח "
                "לאחר בחירת שליח."
            )
        )
        return True

    prompts = {
        "price":
            "💰 שלח את המחיר החדש במספר בלבד:",

        "pickup_address":
            "📍 שלח כתובת איסוף חדשה:",

        "dropoff_address":
            "🏁 שלח כתובת מסירה חדשה:",

        "pickup_time":
            "🕐 שלח מועד איסוף חדש:",

        "package_description":
            "📦 שלח תיאור חדש למשלוח:",

        "notes":
            "📝 שלח הערות חדשות. אם אין, כתוב: אין",
    }

    if field not in prompts:

        return False

    save_session(
        phone,
        "shipment_edit_value",
        {
            "shipment_id":
                shipment_id,

            "field":
                field
        }
    )

    send_message(
        phone,
        prompts[field]
    )

    return True


# =========================================================
# שמירת העריכה
# =========================================================

def handle_shipment_edit_value(
    phone,
    text
):

    current_session = get_session(
        phone
    )

    if (
        current_session.get("state")
        != "shipment_edit_value"
    ):

        return False

    data = current_session.get(
        "data",
        {}
    )

    shipment_id = int(
        data.get(
            "shipment_id",
            0
        )
        or 0
    )

    field = data.get(
        "field",
        ""
    )

    shipment = get_shipment(
        shipment_id
    )

    user = get_user(
        phone
    )

    if (
        not shipment
        or not user
        or user["id"] != shipment["customer_id"]
    ):

        clear_session(
            phone
        )

        send_message(
            phone,
            "לא ניתן לבצע את העריכה."
        )

        return True

    if (
        shipment["status"]
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        clear_session(
            phone
        )

        send_message(
            phone,
            "כבר נבחר שליח ולכן העריכה נעולה."
        )

        return True

    value = (
        text
        or ""
    ).strip()

    allowed_fields = {
        "price",
        "pickup_address",
        "dropoff_address",
        "pickup_time",
        "package_description",
        "notes",
    }

    if field not in allowed_fields:

        clear_session(
            phone
        )
        return True

    if field == "price":

        try:

            new_value = float(
                value.replace(
                    ",",
                    "."
                )
            )

        except Exception:

            new_value = 0

        if new_value <= 0:

            send_message(
                phone,
                (
                    "מחיר לא תקין.\n"
                    "שלח מספר בלבד, לדוגמה: 85"
                )
            )

            return True

    else:

        if (
            field == "notes"
            and value == "אין"
        ):

            new_value = ""

        else:

            new_value = value

        if (
            not new_value
            and field != "notes"
        ):

            send_message(
                phone,
                "הערך לא יכול להיות ריק."
            )

            return True

    # שם העמודה מגיע רק מהרשימה הסגורה למעלה
    sql = (
        f"UPDATE shipments "
        f"SET {field}=?, updated_at=? "
        f"WHERE id=?"
    )

    with db() as conn:

        conn.execute(
            sql,
            (
                new_value,
                now_ts(),
                shipment_id
            )
        )

        conn.commit()

    clear_session(
        phone
    )

    send_message(
        phone,
        f"✅ משלוח #{shipment_id} עודכן בהצלחה."
    )

    show_customer_shipments(
        phone
    )

    return True


# =========================================================
# ביטול משלוח
# =========================================================

def cancel_shipment(
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
        return False

    user = get_user(
        phone
    )

    if (
        not user
        or (
            user["id"] != shipment["customer_id"]
            and phone != ADMIN_PHONE
        )
    ):

        send_message(
            phone,
            "אין הרשאה לבטל את המשלוח."
        )
        return False

    if (
        shipment["status"]
        not in (
            SHIP_OPEN,
            SHIP_HAS_INTEREST
        )
    ):

        send_message(
            phone,
            (
                "לא ניתן לבטל אוטומטית "
                "לאחר בחירת שליח.\n"
                "במקרה כזה יש לפנות לנציג."
            )
        )
        return False

    with db() as conn:

        conn.execute(
            """
            UPDATE shipments

            SET
                status=?,
                cancelled_at=?,
                updated_at=?

            WHERE id=?
            """,
            (
                SHIP_CANCELLED,
                now_ts(),
                now_ts(),
                shipment_id
            )
        )

        conn.commit()

    send_message(
        phone,
        f"❌ משלוח #{shipment_id} בוטל."
    )

    return True


# =========================================================
# סימון משלוח כהושלם
# =========================================================

def complete_shipment(
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
        return False

    customer = get_user(
        phone
    )

    if (
        not customer
        or customer["id"] != shipment["customer_id"]
    ):

        send_message(
            phone,
            "רק המזמין יכול לסיים את המשלוח."
        )
        return False

    if (
        shipment["status"]
        != SHIP_ASSIGNED
    ):

        send_message(
            phone,
            "המשלוח אינו במצב שמאפשר השלמה."
        )
        return False

    driver_id = shipment.get(
        "assigned_driver_id"
    )

    if not driver_id:

        send_message(
            phone,
            "לא נמצא שליח למשלוח."
        )
        return False

    with db() as conn:

        conn.execute(
            """
            UPDATE shipments

            SET
                status=?,
                completed_at=?,
                updated_at=?

            WHERE id=?
            """,
            (
                SHIP_COMPLETED,
                now_ts(),
                now_ts(),
                shipment_id
            )
        )

        conn.commit()

    driver = get_user_by_id(
        driver_id
    )

    send_message(
        phone,
        f"✅ משלוח #{shipment_id} סומן כהושלם."
    )

    if driver:

        send_message(
            driver["phone"],
            f"""
✅ משלוח #{shipment_id} הושלם.

תודה על ביצוע המשלוח ב{BOT_NAME}.
""".strip()
        )

    # דירוג לשליח בלבד
    send_buttons(
        phone,

        f"""
⭐ איך היה השירות של השליח במשלוח #{shipment_id}?

בחר דירוג:
""".strip(),

        [
            (
                f"rate_{shipment_id}_1",
                "⭐ 1"
            ),

            (
                f"rate_{shipment_id}_2",
                "⭐⭐ 2"
            ),

            (
                f"rate_more_{shipment_id}",
                "⭐⭐⭐ 3–5"
            ),
        ]
    )

    return True


# =========================================================
# הצגת דירוגים 3 עד 5
# =========================================================

def show_more_rating_options(
    phone,
    shipment_id
):

    send_buttons(
        phone,

        f"""
⭐ דירוג משלוח #{shipment_id}

בחר מספר כוכבים:
""".strip(),

        [
            (
                f"rate_{shipment_id}_3",
                "⭐⭐⭐ 3"
            ),

            (
                f"rate_{shipment_id}_4",
                "⭐⭐⭐⭐ 4"
            ),

            (
                f"rate_{shipment_id}_5",
                "⭐⭐⭐⭐⭐ 5"
            ),
        ]
    )


# =========================================================
# שמירת דירוג שליח
# =========================================================

def save_driver_rating(
    phone,
    shipment_id,
    stars
):

    if stars not in (
        1,
        2,
        3,
        4,
        5
    ):

        return False

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:

        send_message(
            phone,
            "המשלוח לא נמצא."
        )
        return False

    customer = get_user(
        phone
    )

    if (
        not customer
        or customer["id"] != shipment["customer_id"]
    ):

        send_message(
            phone,
            "אין הרשאה לדרג את המשלוח הזה."
        )
        return False

    if (
        shipment["status"]
        != SHIP_COMPLETED
    ):

        send_message(
            phone,
            (
                "ניתן לדרג שליח רק "
                "לאחר שהמשלוח הושלם."
            )
        )
        return False

    driver_id = shipment.get(
        "assigned_driver_id"
    )

    if not driver_id:

        return False

    with db() as conn:

        existing = conn.execute(
            """
            SELECT id
            FROM driver_ratings
            WHERE shipment_id=?
            """,
            (
                shipment_id,
            )
        ).fetchone()

        if existing:

            send_message(
                phone,
                "כבר דירגת את השליח במשלוח הזה."
            )
            return False

        conn.execute(
            """
            INSERT INTO driver_ratings (
                shipment_id,
                driver_id,
                customer_id,
                stars,
                created_at
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                driver_id,
                customer["id"],
                stars,
                now_ts()
            )
        )

        conn.commit()

    rating = get_driver_rating(
        driver_id
    )

    stars_text = (
        "⭐" * stars
    )

    send_message(
        phone,
        f"""
תודה על הדירוג 🙏

{stars_text}

הדירוג נשמר בהצלחה.
""".strip()
    )

    driver = get_user_by_id(
        driver_id
    )

    if driver:

        send_message(
            driver["phone"],
            f"""
⭐ התקבל דירוג חדש על משלוח #{shipment_id}.

הדירוג:
{stars_text}

הדירוג הנוכחי שלך:
⭐ {rating["average"]:.1f}/5

מספר דירוגים:
{rating["count"]}
""".strip()
        )

    return True


# =========================================================
# זיהוי "פנוי עיר" / "פ עיר"
# =========================================================

def parse_available_city(
    text
):

    clean = (
        text
        or ""
    ).strip()

    match = re.match(
        r"^פנוי\s+(.+)$",
        clean
    )

    if match:

        return match.group(
            1
        ).strip()

    match = re.match(
        r"^פ\s+(.+)$",
        clean
    )

    if match:

        return match.group(
            1
        ).strip()

    return ""


# =========================================================
# שמירת זמינות שליח
# =========================================================

def set_driver_available(
    phone,
    city
):

    user = get_user(
        phone
    )

    if not user:

        return False

    if (
        user.get("role")
        not in (
            ROLE_DRIVER,
            ROLE_DISPATCHER
        )
    ):

        return False

    city = (
        city
        or ""
    ).strip()

    if not city:

        return False

    with db() as conn:

        conn.execute(
            """
            INSERT INTO driver_availability (
                driver_id,
                city,
                is_available,
                updated_at
            )

            VALUES (?, ?, 1, ?)

            ON CONFLICT(driver_id)
            DO UPDATE SET
                city=excluded.city,
                is_available=1,
                updated_at=excluded.updated_at
            """,
            (
                user["id"],
                city,
                now_ts()
            )
        )

        conn.commit()

    send_message(
        phone,
        f"""
🟢 סומנת כפנוי באזור:
{city}

מחפש עבורך משלוחים זמינים...
""".strip()
    )

    show_open_shipments_to_driver(
        phone,
        city
    )

    return True            
# =========================================================
# מנויים ותשלומים
# =========================================================

# =========================================================
# סימון שליח כתפוס
# =========================================================

def set_driver_busy(
    phone
):

    user = get_user(
        phone
    )

    if not user:

        return False

    if (
        user.get("role")
        not in (
            ROLE_DRIVER,
            ROLE_DISPATCHER
        )
    ):

        return False

    with db() as conn:

        conn.execute(
            """
            UPDATE driver_availability

            SET
                city='',
                is_available=0,
                updated_at=?

            WHERE driver_id=?
            """,
            (
                now_ts(),
                user["id"]
            )
        )

        conn.commit()

    send_message(
        phone,
        """
🔴 סומנת כתפוס.

לא יישלחו אליך משלוחים חדשים
עד שתכתוב שוב לדוגמה:

פ ירושלים
או
פנוי ירושלים
""".strip()
    )

    return True

# =========================================================
# שליחת משלוח חדש לשליחים פנויים בעיר האיסוף
# =========================================================

def notify_available_drivers(
    shipment_id
):

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    city = (
        shipment.get("origin_city")
        or ""
    ).strip()

    if not city:
        return False

    # זמינות תקפה ל-24 שעות
    cutoff = now_ts() - (24 * 60 * 60)

    with db() as conn:

        rows = conn.execute(
            """
            SELECT u.phone
            FROM driver_availability da

            JOIN users u
                ON u.id = da.driver_id

            WHERE da.is_available = 1
              AND da.updated_at >= ?
              AND LOWER(da.city) = LOWER(?)
              AND u.is_blocked = 0
            """,
            (
                cutoff,
                city
            )
        ).fetchall()

    for row in rows:

        driver_phone = row["phone"]

        show_open_shipments_to_driver(
            driver_phone,
            city
        )

    return True
def start_subscription_payment(
    phone,
    method
):

    user = get_user(
        phone
    )

    if not user:

        return False


    if (
        user.get("role")
        != ROLE_DRIVER
    ):

        send_message(
            phone,
            "אפשרות המנוי מיועדת לשליחים."
        )

        return False


    price = float(
        get_setting(
            "subscription_price",
            "50"
        )
    )


    # -----------------------------------------
    # העברה בנקאית
    # -----------------------------------------

    if method == "bank":

        if (
            get_setting(
                "bank_enabled",
                "1"
            )
            != "1"
        ):

            send_message(
                phone,
                "העברה בנקאית אינה זמינה כרגע."
            )

            return True


        payment_text = f"""
🏦 תשלום בהעברה בנקאית

סכום לתשלום:
{price:g} ₪

פרטי החשבון:

{get_setting("bank_details", "טרם הוגדר")}

לאחר ביצוע ההעברה,
שלח כאן צילום מסך של אישור התשלום.

⚠️ המנוי יופעל רק לאחר אישור המנהל.
""".strip()


    # -----------------------------------------
    # Bit
    # -----------------------------------------

    elif method == "bit":

        if (
            get_setting(
                "bit_enabled",
                "1"
            )
            != "1"
        ):

            send_message(
                phone,
                "Bit אינו זמין כרגע."
            )

            return True


        payment_text = f"""
📱 תשלום באמצעות Bit

סכום לתשלום:
{price:g} ₪

מספר לתשלום:
{get_setting("bit_phone", "טרם הוגדר")}

לאחר ביצוע התשלום,
שלח כאן צילום מסך של אישור התשלום.

⚠️ המנוי יופעל רק לאחר אישור המנהל.
""".strip()


    # -----------------------------------------
    # PayBox
    # -----------------------------------------

    elif method == "paybox":

        if (
            get_setting(
                "paybox_enabled",
                "1"
            )
            != "1"
        ):

            send_message(
                phone,
                "PayBox אינו זמין כרגע."
            )

            return True


        payment_text = f"""
📲 תשלום באמצעות PayBox

סכום לתשלום:
{price:g} ₪

מספר לתשלום:
{get_setting("paybox_phone", "טרם הוגדר")}

לאחר ביצוע התשלום,
שלח כאן צילום מסך של אישור התשלום.

⚠️ המנוי יופעל רק לאחר אישור המנהל.
""".strip()


    else:

        return False


    with db() as conn:

        cursor = conn.execute(
            """
            INSERT INTO payments (
                user_id,
                amount,
                payment_method,
                status,
                submitted_at
            )

            VALUES (?, ?, ?, ?, ?)
            """,

            (
                user["id"],
                price,
                method,
                PAY_WAITING_PROOF,
                now_ts()
            )
        )

        payment_id = (
            cursor.lastrowid
        )

        conn.commit()


    save_session(
        phone,

        "payment_waiting_proof",

        {
            "payment_id":
                payment_id
        }
    )


    send_message(
        phone,
        payment_text
    )


    return True


# =========================================================
# קבלת צילום אסמכתא
# =========================================================

def handle_payment_proof(
    phone,
    media_id
):

    current_session = get_session(
        phone
    )


    if (
        current_session.get("state")
        != "payment_waiting_proof"
    ):

        return False


    if not media_id:

        send_message(
            phone,

            (
                "📸 יש לשלוח צילום מסך "
                "של אישור התשלום."
            )
        )

        return True


    payment_id = int(
        current_session.get(
            "data",
            {}
        ).get(
            "payment_id",
            0
        )
        or 0
    )


    with db() as conn:

        payment = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id=?
            """,

            (
                payment_id,
            )
        ).fetchone()


        if not payment:

            clear_session(
                phone
            )

            send_message(
                phone,
                "בקשת התשלום לא נמצאה."
            )

            return True


        conn.execute(
            """
            UPDATE payments

            SET
                proof_media_id=?,
                status=?,
                submitted_at=?

            WHERE id=?
            """,

            (
                media_id,
                PAY_WAITING_ADMIN,
                now_ts(),
                payment_id
            )
        )

        conn.commit()


    clear_session(
        phone
    )


    user = get_user(
        phone
    )


    send_message(
        phone,

        f"""
📸 אישור התשלום התקבל.

בקשת תשלום #{payment_id}
נשלחה לבדיקת המנהל.

המנוי עדיין לא הופעל.

לאחר שהמנהל יאשר את התשלום,
המנוי יופעל ויישלח אליך קישור לקבלה.
""".strip()
    )


    # שולחים למנהל קודם את פרטי הבקשה
    send_message(
        ADMIN_PHONE,

        f"""
💳 תשלום חדש ממתין לאישור

בקשה:
#{payment_id}

👤 שליח:
{user.get("full_name") if user else "-"}

📱 טלפון:
{phone}

💰 סכום:
{payment["amount"]:g} ₪

💳 אמצעי תשלום:
{payment["payment_method"]}

האסמכתא מצורפת בהודעה הבאה.
""".strip()
    )


    # שולחים את התמונה עצמה למנהל
    send_image_by_id(
        ADMIN_PHONE,
        media_id
    )


    send_buttons(
        ADMIN_PHONE,

        f"תשלום #{payment_id} - מה לבצע?",

        [
            (
                f"admin_payment_approve_"
                f"{payment_id}",

                "✅ אשר תשלום"
            ),

            (
                f"admin_payment_reject_"
                f"{payment_id}",

                "❌ דחה תשלום"
            ),
        ]
    )


    return True


# =========================================================
# קבלת פרטי תשלום
# =========================================================

def get_payment(
    payment_id
):

    with db() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id=?
            """,

            (
                payment_id,
            )
        ).fetchone()

    return row_to_dict(
        row
    )


# =========================================================
# אישור תשלום על ידי המנהל
# =========================================================

def approve_payment(
    payment_id
):

    payment = get_payment(
        payment_id
    )


    if not payment:

        return False


    if (
        payment.get("status")
        == PAY_APPROVED
    ):

        return False


    if (
        payment.get("status")
        != PAY_WAITING_ADMIN
    ):

        return False


    user = get_user_by_id(
        payment["user_id"]
    )


    if not user:

        return False


    current_time = now_ts()


    old_subscription_expiry = int(
        user.get(
            "subscription_expires_at"
        )
        or 0
    )


    # אם יש מנוי בתוקף - מוסיפים חודש מהסוף שלו.
    # אחרת - חודש ממועד האישור.
    if (
        old_subscription_expiry
        > current_time
    ):

        subscription_start = (
            old_subscription_expiry
        )

    else:

        subscription_start = (
            current_time
        )


    # חודש מנוי = 30 יום במערכת
    new_expiry = (
        subscription_start
        + (
            30
            * 86400
        )
    )


    # -----------------------------------------
    # קודם מפיקים קבלה
    # ורק לאחר שהמנהל לחץ אישור.
    # -----------------------------------------

    method = payment.get(
        "payment_method",
        ""
    )


    receipt_url = create_paperless_receipt(

        client_name=(
            user.get("full_name")
            or "לקוח"
        ),

        phone=(
            user.get("phone")
            or ""
        ),

        amount=(
            payment.get("amount")
            or 0
        ),

        payment_method=
            method,

        plan_name=
            BOT_NAME
    )


    # גם אם Paperless נכשל זמנית,
    # התשלום שהמנהל אישר עדיין נשמר.
    # נעדכן את המנהל שאין קישור לקבלה.
    with db() as conn:

        conn.execute(
            """
            UPDATE payments

            SET
                status=?,
                receipt_url=?,
                approved_at=?,
                approved_by=?

            WHERE id=?
            """,

            (
                PAY_APPROVED,
                receipt_url or "",
                current_time,
                ADMIN_PHONE,
                payment_id
            )
        )


        conn.execute(
            """
            UPDATE users

            SET
                subscription_expires_at=?,
                updated_at=?

            WHERE id=?
            """,

            (
                new_expiry,
                current_time,
                user["id"]
            )
        )

        conn.commit()


    log_admin_action(
        "APPROVE_PAYMENT",

        target_phone=
            user["phone"],

        reference_id=
            payment_id,

        notes=(
            f"{payment.get('amount')} "
            f"{method}"
        )
    )


    if receipt_url:

        send_message(
            user["phone"],

            f"""
✅ התשלום אושר על ידי המנהל.

המנוי שלך ב{BOT_NAME} הופעל בהצלחה.

💰 סכום:
{payment["amount"]:g} ₪

📅 המנוי בתוקף עד:
{format_date(new_expiry)}

🧾 הקבלה שלך:
{receipt_url}

תודה!
""".strip()
        )


        send_message(
            ADMIN_PHONE,

            f"""
✅ תשלום #{payment_id} אושר.

המנוי הופעל עד:
{format_date(new_expiry)}

🧾 הקבלה הופקה בהצלחה.
""".strip()
        )


    else:

        send_message(
            user["phone"],

            f"""
✅ התשלום אושר על ידי המנהל.

המנוי שלך ב{BOT_NAME} הופעל בהצלחה.

📅 המנוי בתוקף עד:
{format_date(new_expiry)}

⚠️ כרגע לא ניתן היה להפיק את קישור הקבלה.
ניתן לפנות לנציג במידת הצורך.
""".strip()
        )


        send_message(
            ADMIN_PHONE,

            f"""
⚠️ תשלום #{payment_id} אושר והמנוי הופעל,
אבל Paperless לא החזיר קישור לקבלה.

יש לבדוק את החיבור ל-Paperless.
""".strip()
        )


    return True


# =========================================================
# דחיית תשלום
# =========================================================

def reject_payment(
    payment_id
):

    payment = get_payment(
        payment_id
    )


    if not payment:

        return False


    if (
        payment.get("status")
        != PAY_WAITING_ADMIN
    ):

        return False


    user = get_user_by_id(
        payment["user_id"]
    )


    if not user:

        return False


    with db() as conn:

        conn.execute(
            """
            UPDATE payments

            SET
                status=?,
                rejected_at=?

            WHERE id=?
            """,

            (
                PAY_REJECTED,
                now_ts(),
                payment_id
            )
        )

        conn.commit()


    log_admin_action(
        "REJECT_PAYMENT",

        target_phone=
            user["phone"],

        reference_id=
            payment_id
    )


    send_message(
        user["phone"],

        f"""
❌ אישור התשלום #{payment_id}
לא אושר על ידי המנהל.

המנוי לא הופעל
ולא הופקה קבלה.

אם שילמת בפועל,
ניתן לבצע ניסיון חדש ולשלוח אסמכתא ברורה.
""".strip()
    )


    return True


# =========================================================
# תשלומים שממתינים לאישור
# =========================================================

def show_pending_payments(
    phone
):

    with db() as conn:

        rows = conn.execute(
            """
            SELECT
                payments.*,
                users.full_name,
                users.phone

            FROM payments

            JOIN users
                ON users.id=
                    payments.user_id

            WHERE payments.status=?

            ORDER BY
                payments.submitted_at ASC

            LIMIT 20
            """,

            (
                PAY_WAITING_ADMIN,
            )
        ).fetchall()


    if not rows:

        send_message(
            phone,
            "✅ אין תשלומים שממתינים לאישור."
        )

        return


    for row in rows:

        payment = dict(row)


        send_message(
            phone,

            f"""
💳 תשלום ממתין

בקשה:
#{payment["id"]}

👤:
{payment.get("full_name") or "-"}

📱:
{payment.get("phone") or "-"}

💰:
{payment["amount"]:g} ₪

אמצעי:
{payment["payment_method"]}
""".strip()
        )


        if payment.get(
            "proof_media_id"
        ):

            send_image_by_id(
                phone,
                payment[
                    "proof_media_id"
                ]
            )


        send_buttons(
            phone,

            f"תשלום #{payment['id']}",

            [
                (
                    f"admin_payment_approve_"
                    f"{payment['id']}",

                    "✅ אשר תשלום"
                ),

                (
                    f"admin_payment_reject_"
                    f"{payment['id']}",

                    "❌ דחה תשלום"
                ),
            ]
        )


# =========================================================
# פנייה לנציג
# =========================================================

def start_support_request(
    phone
):

    save_session(
        phone,

        "support_category",

        {}
    )


    send_list(
        phone,

        "💬 פנייה לנציג\n\nבחר נושא:",

        "בחירת נושא",

        [
            (
                "support_cat_shipment",
                "📦 בעיה במשלוח",
                "משלוח פעיל או שהושלם"
            ),

            (
                "support_cat_user",
                "👤 בעיה עם משתמש",
                "שליח או מזמין"
            ),

            (
                "support_cat_payment",
                "💳 תשלום / מנוי",
                "בעיה בתשלום"
            ),

            (
                "support_cat_account",
                "⚙️ חשבון",
                "בעיה בחשבון"
            ),

            (
                "support_cat_other",
                "💬 אחר",
                "נושא אחר"
            ),
        ]
    )


# =========================================================
# בחירת קטגוריית תמיכה
# =========================================================

def support_category_selected(
    phone,
    category
):

    save_session(
        phone,

        "support_message",

        {
            "category":
                category
        }
    )


    send_message(
        phone,

        """
✍️ כתוב עכשיו את ההודעה שברצונך לשלוח לנציג.

מומלץ לציין מספר משלוח אם הפנייה קשורה למשלוח.
""".strip()
    )


# =========================================================
# שמירת פנייה לנציג
# =========================================================

def handle_support_message(
    phone,
    text
):

    current_session = get_session(
        phone
    )


    if (
        current_session.get("state")
        != "support_message"
    ):

        return False


    message = (
        text
        or ""
    ).strip()


    if len(message) < 2:

        send_message(
            phone,
            "נא לכתוב את תוכן הפנייה."
        )

        return True


    data = current_session.get(
        "data",
        {}
    )


    category = data.get(
        "category",
        "אחר"
    )


    user = get_user(
        phone
    )


    role = (
        user.get("role")
        if user
        else ""
    )


    with db() as conn:

        cursor = conn.execute(
            """
            INSERT INTO support_requests (
                user_phone,
                user_role,
                category,
                message,
                status,
                created_at
            )

            VALUES (?, ?, ?, ?, 'OPEN', ?)
            """,

            (
                phone,
                role,
                category,
                message,
                now_ts()
            )
        )

        support_id = (
            cursor.lastrowid
        )

        conn.commit()


    clear_session(
        phone
    )


    send_message(
        phone,

        f"""
✅ הפנייה נשלחה לנציג.

מספר פנייה:
#{support_id}

כאשר המנהל ישיב,
התשובה תישלח אליך כאן.
""".strip()
    )


    send_buttons(
        ADMIN_PHONE,

        f"""
💬 פנייה חדשה לנציג

מספר:
#{support_id}

👤:
{user.get("full_name") if user else "-"}

📱:
{phone}

סוג משתמש:
{role or "-"}

נושא:
{category}

הודעה:
{message}
""".strip(),

        [
            (
                f"admin_support_reply_"
                f"{support_id}",

                "✍️ השב"
            ),

            (
                f"admin_support_close_"
                f"{support_id}",

                "✅ סגור פנייה"
            ),
        ]
    )


    return True
# =========================================================
# ניהול פניות על ידי המנהל
# =========================================================

def show_open_support_requests(
    phone
):

    with db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM support_requests

            WHERE status='OPEN'

            ORDER BY created_at ASC

            LIMIT 20
            """
        ).fetchall()


    if not rows:

        send_message(
            phone,
            "✅ אין כרגע פניות פתוחות."
        )

        return


    for row in rows:

        support = dict(row)


        send_buttons(
            phone,

            f"""
💬 פנייה #{support["id"]}

📱 משתמש:
{support["user_phone"]}

👤 סוג:
{support.get("user_role") or "-"}

📌 נושא:
{support.get("category") or "-"}

✍️ הודעה:
{support.get("message") or "-"}
""".strip(),

            [
                (
                    f"admin_support_reply_"
                    f"{support['id']}",
                    "✍️ השב"
                ),

                (
                    f"admin_support_close_"
                    f"{support['id']}",
                    "✅ סגור פנייה"
                ),
            ]
        )


# =========================================================
# התחלת תשובה לפנייה
# =========================================================

def start_admin_support_reply(
    phone,
    support_id
):

    if phone != ADMIN_PHONE:

        return False


    with db() as conn:

        support = conn.execute(
            """
            SELECT *
            FROM support_requests
            WHERE id=?
            """,
            (
                support_id,
            )
        ).fetchone()


    if not support:

        send_message(
            phone,
            "הפנייה לא נמצאה."
        )

        return True


    save_session(
        phone,

        "admin_support_reply_text",

        {
            "support_id":
                support_id
        }
    )


    send_message(
        phone,

        f"""
✍️ תשובה לפנייה #{support_id}

כתוב עכשיו את התשובה שתרצה לשלוח למשתמש.
""".strip()
    )


    return True


# =========================================================
# שליחת תשובת המנהל למשתמש
# =========================================================

def handle_admin_support_reply(
    phone,
    text
):

    if phone != ADMIN_PHONE:

        return False


    current_session = get_session(
        phone
    )


    if (
        current_session.get("state")
        != "admin_support_reply_text"
    ):

        return False


    reply = (
        text
        or ""
    ).strip()


    if not reply:

        send_message(
            phone,
            "נא לכתוב תשובה."
        )

        return True


    support_id = int(
        current_session.get(
            "data",
            {}
        ).get(
            "support_id",
            0
        )
        or 0
    )


    with db() as conn:

        support = conn.execute(
            """
            SELECT *
            FROM support_requests
            WHERE id=?
            """,
            (
                support_id,
            )
        ).fetchone()


        if not support:

            clear_session(
                phone
            )

            send_message(
                phone,
                "הפנייה לא נמצאה."
            )

            return True


        conn.execute(
            """
            UPDATE support_requests

            SET
                admin_reply=?,
                status='ANSWERED',
                replied_at=?

            WHERE id=?
            """,
            (
                reply,
                now_ts(),
                support_id
            )
        )

        conn.commit()


    clear_session(
        phone
    )


    send_message(
        support["user_phone"],

        f"""
💬 תשובה מתמיכת {BOT_NAME}

פנייה #{support_id}

{reply}

אם הבעיה לא נפתרה,
ניתן לפתוח פנייה חדשה.
""".strip()
    )


    send_message(
        phone,
        f"✅ התשובה לפנייה #{support_id} נשלחה."
    )


    return True


# =========================================================
# סגירת פנייה
# =========================================================

def close_support_request(
    phone,
    support_id
):

    if phone != ADMIN_PHONE:

        return False


    with db() as conn:

        support = conn.execute(
            """
            SELECT *
            FROM support_requests
            WHERE id=?
            """,
            (
                support_id,
            )
        ).fetchone()


        if not support:

            send_message(
                phone,
                "הפנייה לא נמצאה."
            )

            return True


        conn.execute(
            """
            UPDATE support_requests

            SET
                status='CLOSED',
                closed_at=?

            WHERE id=?
            """,
            (
                now_ts(),
                support_id
            )
        )

        conn.commit()


    send_message(
        phone,
        f"✅ פנייה #{support_id} נסגרה."
    )


    return True


# =========================================================
# שינוי מחיר מנוי
# =========================================================

def start_admin_set_price(
    phone
):

    save_session(
        phone,
        "admin_set_price_value",
        {}
    )


    send_message(
        phone,

        f"""
💰 מחיר המנוי הנוכחי:
{get_setting("subscription_price", "50")} ₪

שלח את המחיר החודשי החדש במספר בלבד.
""".strip()
    )


def handle_admin_set_price(
    phone,
    text
):

    try:

        price = float(
            (
                text
                or ""
            ).replace(
                ",",
                "."
            )
        )

    except Exception:

        price = 0


    if price <= 0:

        send_message(
            phone,
            "נא לשלוח מחיר תקין."
        )

        return True


    set_setting(
        "subscription_price",
        f"{price:g}"
    )


    clear_session(
        phone
    )


    log_admin_action(
        "SET_SUBSCRIPTION_PRICE",

        notes=
            f"{price:g}"
    )


    send_message(
        phone,

        f"""
✅ מחיר המנוי עודכן.

מחיר חדש:
{price:g} ₪ לחודש
""".strip()
    )


    show_admin_settings_menu(
        phone
    )


    return True


# =========================================================
# שינוי מספר ימי ניסיון
# =========================================================

def start_admin_set_trial(
    phone
):

    save_session(
        phone,
        "admin_set_trial_value",
        {}
    )


    send_message(
        phone,

        f"""
🎁 מספר ימי הניסיון הנוכחי:
{get_setting("trial_days", "60")}

שלח מספר ימים חדש.
""".strip()
    )


def handle_admin_set_trial(
    phone,
    text
):

    try:

        days = int(
            (
                text
                or ""
            ).strip()
        )

    except Exception:

        days = 0


    if (
        days < 0
        or days > 3650
    ):

        send_message(
            phone,
            "נא לשלוח מספר ימים תקין."
        )

        return True


    set_setting(
        "trial_days",
        str(days)
    )


    clear_session(
        phone
    )


    log_admin_action(
        "SET_TRIAL_DAYS",

        notes=
            str(days)
    )


    send_message(
        phone,

        f"""
✅ תקופת הניסיון עודכנה.

שליחים חדשים שיאושרו מעכשיו
יקבלו {days} ימי ניסיון.
""".strip()
    )


    show_admin_settings_menu(
        phone
    )


    return True


# =========================================================
# שינוי פרטי בנק
# =========================================================

def start_admin_set_bank(
    phone
):

    save_session(
        phone,
        "admin_set_bank_value",
        {}
    )


    send_message(
        phone,

        """
🏦 שלח את פרטי חשבון הבנק כפי שתרצה שיופיעו לשליח.

אפשר לכלול:
שם בנק
מספר בנק
סניף
חשבון
שם בעל החשבון
""".strip()
    )


def handle_admin_set_bank(
    phone,
    text
):

    value = (
        text
        or ""
    ).strip()


    if len(value) < 3:

        send_message(
            phone,
            "פרטי החשבון קצרים מדי."
        )

        return True


    set_setting(
        "bank_details",
        value
    )


    clear_session(
        phone
    )


    log_admin_action(
        "SET_BANK_DETAILS"
    )


    send_message(
        phone,
        "✅ פרטי חשבון הבנק עודכנו."
    )


    show_admin_settings_menu(
        phone
    )


    return True


# =========================================================
# שינוי מספר Bit
# =========================================================

def start_admin_set_bit(
    phone
):

    save_session(
        phone,
        "admin_set_bit_value",
        {}
    )


    send_message(
        phone,
        "📱 שלח את מספר הטלפון החדש לתשלום ב-Bit."
    )


def handle_admin_set_bit(
    phone,
    text
):

    value = normalize_phone(
        text
    )


    if len(value) < 9:

        send_message(
            phone,
            "מספר הטלפון לא נראה תקין."
        )

        return True


    set_setting(
        "bit_phone",
        value
    )


    clear_session(
        phone
    )


    log_admin_action(
        "SET_BIT_PHONE",

        notes=
            value
    )


    send_message(
        phone,
        "✅ מספר Bit עודכן."
    )


    show_admin_settings_menu(
        phone
    )


    return True


# =========================================================
# שינוי מספר PayBox
# =========================================================

def start_admin_set_paybox(
    phone
):

    save_session(
        phone,
        "admin_set_paybox_value",
        {}
    )


    send_message(
        phone,
        "📲 שלח את מספר הטלפון החדש לתשלום ב-PayBox."
    )


def handle_admin_set_paybox(
    phone,
    text
):

    value = normalize_phone(
        text
    )


    if len(value) < 9:

        send_message(
            phone,
            "מספר הטלפון לא נראה תקין."
        )

        return True


    set_setting(
        "paybox_phone",
        value
    )


    clear_session(
        phone
    )


    log_admin_action(
        "SET_PAYBOX_PHONE",

        notes=
            value
    )


    send_message(
        phone,
        "✅ מספר PayBox עודכן."
    )


    show_admin_settings_menu(
        phone
    )


    return True


# =========================================================
# הפעלה / כיבוי של הגדרה
# =========================================================

def toggle_setting(
    key
):

    current = get_setting(
        key,
        "1"
    )


    if current == "1":

        new_value = "0"

    else:

        new_value = "1"


    set_setting(
        key,
        new_value
    )


    return new_value


# =========================================================
# הפעלה / כיבוי מערכת מנויים
# =========================================================

def toggle_subscription_system(
    phone
):

    value = toggle_setting(
        "subscription_enabled"
    )


    if value == "1":

        text = (
            "✅ מערכת המנויים הופעלה."
        )

    else:

        text = (
            "🟢 מערכת המנויים כובתה.\n"
            "שליחים יכולים להשתמש במערכת ללא מנוי."
        )


    log_admin_action(
        "TOGGLE_SUBSCRIPTIONS",

        notes=
            value
    )


    send_message(
        phone,
        text
    )


    show_admin_settings_menu(
        phone
    )


# =========================================================
# הפעלה / כיבוי אמצעי תשלום
# =========================================================

def toggle_payment_method(
    phone,
    key,
    display_name
):

    value = toggle_setting(
        key
    )


    status = (
        "פעיל"
        if value == "1"
        else "כבוי"
    )


    send_message(
        phone,

        f"""
✅ {display_name}

מצב חדש:
{status}
""".strip()
    )


    log_admin_action(
        "TOGGLE_PAYMENT_METHOD",

        notes=
            f"{key}={value}"
    )


    show_payment_methods_admin(
        phone
    )


# =========================================================
# מצב תחזוקה
# =========================================================

def toggle_maintenance_mode(
    phone
):

    value = toggle_setting(
        "maintenance_mode"
    )


    if value == "1":

        message = (
            "🛠️ מצב תחזוקה הופעל."
        )

    else:

        message = (
            "✅ מצב תחזוקה כובה."
        )


    send_message(
        phone,
        message
    )


    log_admin_action(
        "TOGGLE_MAINTENANCE",

        notes=
            value
    )    
# =========================================================
# טיפול בפעולות המנהל
# =========================================================

def handle_admin_action(
    phone,
    text,
    action_id
):

    if phone != ADMIN_PHONE:
        return False

    current_session = get_session(
        phone
    )

    state = current_session.get(
        "state",
        ""
    )

    # -----------------------------------------
    # מצבים שבהם המנהל צריך להקליד טקסט
    # -----------------------------------------

    if (
        state == "admin_support_reply_text"
        and text
        and not action_id
    ):

        return handle_admin_support_reply(
            phone,
            text
        )


    if (
        state == "admin_set_price_value"
        and text
        and not action_id
    ):

        return handle_admin_set_price(
            phone,
            text
        )


    if (
        state == "admin_set_trial_value"
        and text
        and not action_id
    ):

        return handle_admin_set_trial(
            phone,
            text
        )


    if (
        state == "admin_set_bank_value"
        and text
        and not action_id
    ):

        return handle_admin_set_bank(
            phone,
            text
        )


    if (
        state == "admin_set_bit_value"
        and text
        and not action_id
    ):

        return handle_admin_set_bit(
            phone,
            text
        )


    if (
        state == "admin_set_paybox_value"
        and text
        and not action_id
    ):

        return handle_admin_set_paybox(
            phone,
            text
        )


    # -----------------------------------------
    # הוספת סדרן
    # -----------------------------------------

    if (
        state == "admin_dispatcher_add_phone"
        and text
        and not action_id
    ):

        target_phone = normalize_phone(
            text
        )

        if len(target_phone) < 9:

            send_message(
                phone,
                "❌ מספר הטלפון אינו תקין."
            )

            return True


        if add_dispatcher(
            target_phone
        ):

            clear_session(
                phone
            )

            send_message(
                phone,

                f"""
✅ הסדרן נוסף בהצלחה.

📱 {target_phone}
""".strip()
            )

            show_dispatcher_management_menu(
                phone
            )

        else:

            send_message(
                phone,
                "❌ לא ניתן להוסיף את המספר כסדרן."
            )

        return True


    # -----------------------------------------
    # הסרת סדרן
    # -----------------------------------------

    if (
        state == "admin_dispatcher_remove_phone"
        and text
        and not action_id
    ):

        target_phone = normalize_phone(
            text
        )


        if remove_dispatcher(
            target_phone
        ):

            clear_session(
                phone
            )

            send_message(
                phone,
                "✅ הרשאת הסדרן הוסרה."
            )

            show_dispatcher_management_menu(
                phone
            )

        else:

            send_message(
                phone,
                "❌ המספר אינו מוגדר כסדרן."
            )

        return True


    # -----------------------------------------
    # חסימת מספר
    # -----------------------------------------

    if (
        state == "admin_block_phone"
        and text
        and not action_id
    ):

        target_phone = normalize_phone(
            text
        )


        if target_phone == ADMIN_PHONE:

            send_message(
                phone,
                "❌ לא ניתן לחסום את מספר המנהל."
            )

            return True


        if block_user_by_phone(
            target_phone
        ):

            clear_session(
                phone
            )

            send_message(
                phone,
                f"🚫 המספר {target_phone} נחסם."
            )

            show_admin_menu(
                phone
            )

        else:

            send_message(
                phone,
                (
                    "❌ המשתמש לא נמצא במערכת.\n"
                    "שלח מספר של משתמש רשום."
                )
            )

        return True


    # -----------------------------------------
    # הסרת חסימה
    # -----------------------------------------

    if (
        state == "admin_unblock_phone"
        and text
        and not action_id
    ):

        target_phone = normalize_phone(
            text
        )


        if unblock_user_by_phone(
            target_phone
        ):

            clear_session(
                phone
            )

            send_message(
                phone,
                f"🔓 החסימה הוסרה מ-{target_phone}."
            )

            show_admin_menu(
                phone
            )

        else:

            send_message(
                phone,
                "❌ המשתמש לא נמצא."
            )

        return True


    # =====================================================
    # כפתורי תפריט מנהל
    # =====================================================

    if action_id == "admin_menu":

        clear_session(
            phone
        )

        show_admin_menu(
            phone
        )

        return True


    if action_id == "admin_pending_drivers":

        show_pending_drivers(
            phone
        )

        return True


    if action_id == "admin_dispatchers":

        show_dispatcher_management_menu(
            phone
        )

        return True


    if action_id == "admin_dispatcher_add":

        save_session(
            phone,
            "admin_dispatcher_add_phone",
            {}
        )

        send_message(
            phone,
            (
                "📱 שלח את מספר הטלפון "
                "שברצונך להוסיף כסדרן."
            )
        )

        return True


    if action_id == "admin_dispatcher_remove":

        save_session(
            phone,
            "admin_dispatcher_remove_phone",
            {}
        )

        send_message(
            phone,
            (
                "📱 שלח את מספר הטלפון "
                "של הסדרן שברצונך להסיר."
            )
        )

        return True


    if action_id == "admin_dispatcher_list":

        send_dispatcher_list(
            phone
        )

        return True


    if action_id == "admin_block_user":

        save_session(
            phone,
            "admin_block_phone",
            {}
        )

        send_message(
            phone,
            "🚫 שלח את מספר הטלפון שברצונך לחסום."
        )

        return True


    if action_id == "admin_unblock_user":

        save_session(
            phone,
            "admin_unblock_phone",
            {}
        )

        send_message(
            phone,
            "🔓 שלח את מספר הטלפון שברצונך לפתוח."
        )

        return True


    if action_id == "admin_blocked_list":

        send_blocked_users(
            phone
        )

        return True


    if action_id == "admin_payments":

        show_pending_payments(
            phone
        )

        return True


    if action_id == "admin_support":

        show_open_support_requests(
            phone
        )

        return True


    if action_id == "admin_statistics":

        send_admin_statistics(
            phone
        )

        return True


    if action_id == "admin_settings":

        show_admin_settings_menu(
            phone
        )

        return True


    if action_id == "admin_shipments":

        with db() as conn:

            rows = conn.execute(
                """
                SELECT *
                FROM shipments

                WHERE status IN (?, ?, ?)

                ORDER BY created_at DESC

                LIMIT 20
                """,
                (
                    SHIP_OPEN,
                    SHIP_HAS_INTEREST,
                    SHIP_ASSIGNED
                )
            ).fetchall()


        if not rows:

            send_message(
                phone,
                "📭 אין כרגע משלוחים פעילים."
            )

            return True


        for row in rows:

            shipment = dict(row)

            send_message(
                phone,

                f"""
📦 משלוח #{shipment["id"]}

סטטוס:
{shipment["status"]}

📍 {shipment["origin_city"]}
➡️ {shipment["destination_city"]}

💰 {shipment["price"]:g} ₪
""".strip()
            )

        return True


    # =====================================================
    # אישור / דחייה / חסימת שליח חדש
    # =====================================================

    if action_id.startswith(
        "admin_approve_driver_"
    ):

        try:

            user_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        if approve_driver(
            user_id
        ):

            send_message(
                phone,
                "✅ השליח אושר."
            )

        else:

            send_message(
                phone,
                "❌ לא ניתן לאשר את השליח."
            )

        return True


    if action_id.startswith(
        "admin_reject_driver_"
    ):

        try:

            user_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        if reject_driver(
            user_id
        ):

            send_message(
                phone,
                "❌ בקשת השליח נדחתה."
            )

        return True


    if action_id.startswith(
        "admin_block_driver_"
    ):

        try:

            user_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        target_user = get_user_by_id(
            user_id
        )


        if target_user:

            block_user_by_phone(
                target_user["phone"]
            )

            send_message(
                phone,
                "🚫 המשתמש נחסם."
            )

        return True


    # =====================================================
    # אישור תשלום
    # =====================================================

    if action_id.startswith(
        "admin_payment_approve_"
    ):

        try:

            payment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        if approve_payment(
            payment_id
        ):

            send_message(
                phone,
                "✅ התשלום טופל."
            )

        else:

            send_message(
                phone,
                (
                    "❌ לא ניתן לאשר את התשלום.\n"
                    "ייתכן שכבר טופל."
                )
            )

        return True


    if action_id.startswith(
        "admin_payment_reject_"
    ):

        try:

            payment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        if reject_payment(
            payment_id
        ):

            send_message(
                phone,
                "❌ התשלום נדחה."
            )

        return True


    # =====================================================
    # תמיכה
    # =====================================================

    if action_id.startswith(
        "admin_support_reply_"
    ):

        try:

            support_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        start_admin_support_reply(
            phone,
            support_id
        )

        return True


    if action_id.startswith(
        "admin_support_close_"
    ):

        try:

            support_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        close_support_request(
            phone,
            support_id
        )

        return True


    # =====================================================
    # הגדרות
    # =====================================================

    if action_id == "admin_set_price":

        start_admin_set_price(
            phone
        )

        return True


    if action_id == "admin_set_trial":

        start_admin_set_trial(
            phone
        )

        return True


    if action_id == "admin_set_bank":

        start_admin_set_bank(
            phone
        )

        return True


    if action_id == "admin_set_bit":

        start_admin_set_bit(
            phone
        )

        return True


    if action_id == "admin_set_paybox":

        start_admin_set_paybox(
            phone
        )

        return True


    if action_id == "admin_toggle_subscription":

        toggle_subscription_system(
            phone
        )

        return True


    if action_id == "admin_payment_methods":

        show_payment_methods_admin(
            phone
        )

        return True


    if action_id == "admin_toggle_bank":

        toggle_payment_method(
            phone,
            "bank_enabled",
            "העברה בנקאית"
        )

        return True


    if action_id == "admin_toggle_bit":

        toggle_payment_method(
            phone,
            "bit_enabled",
            "Bit"
        )

        return True


    if action_id == "admin_toggle_paybox":

        toggle_payment_method(
            phone,
            "paybox_enabled",
            "PayBox"
        )

        return True


    if action_id == "admin_maintenance":

        toggle_maintenance_mode(
            phone
        )

        return True


    return False


# =========================================================
# פעולות משתמש רגיל
# =========================================================

def handle_user_action(
    phone,
    user,
    text,
    action_id,
    media_id=""
):

    current_session = get_session(
        phone
    )

    state = current_session.get(
        "state",
        ""
    )

        if state == "driver_id_photo":
        if not media_id:
            send_message(
                phone,
                "📸 יש לשלוח צילום ברור של תעודת הזהות כתמונה ב-WhatsApp."
            )
            return True

        data = current_session.get("data", {}) or {}
        data["id_photo_media_id"] = media_id

        save_session(
            phone,
            "driver_selfie",
            data
        )

        send_message(
            phone,
            """🤳 צילום סלפי

צילום תעודת הזהות התקבל בהצלחה ✅

עכשיו יש לשלוח תמונת סלפי ברורה שלך כתמונה ב-WhatsApp."""
        )

        return True

    if state == "driver_selfie":
        if not media_id:
            send_message(
                phone,
                "🤳 יש לשלוח תמונת סלפי ברורה כתמונה ב-WhatsApp."
            )
            return True

        data = current_session.get("data", {}) or {}
        data["selfie_media_id"] = media_id

        save_session(
            phone,
            "driver_photos_ready",
            data
        )

        send_message(
            phone,
            """✅ התמונות התקבלו בהצלחה.

📄 צילום תעודת הזהות התקבל.
🤳 תמונת הסלפי התקבלה.

ההרשמה כמעט הושלמה."""
        )

        return True
    # =====================================================
    # תהליכים שממתינים לטקסט / תמונה
    # =====================================================

    if (
        state == "payment_waiting_proof"
    ):

        if media_id:

            return handle_payment_proof(
                phone,
                media_id
            )

        send_message(
            phone,
            "📸 נא לשלוח צילום מסך של אישור התשלום."
        )

        return True


    if (
        state == "support_message"
        and text
        and not action_id
    ):

        return handle_support_message(
            phone,
            text
        )


    if (
        state == "shipment_edit_value"
        and text
        and not action_id
    ):

        return handle_shipment_edit_value(
            phone,
            text
        )


    if (
        state == "driver_interest_eta"
        and text
        and not action_id
    ):

        return handle_driver_interest_eta(
            phone,
            text
        )


    if state.startswith(
        "shipment_"
    ):

        if handle_new_shipment(
            phone,
            text,
            action_id
        ):

            return True


    # הרשמה
    if handle_registration(
        phone,
        text,
        action_id
    ):

        return True


    # =====================================================
    # תפריטים
    # =====================================================

    if action_id == "customer_menu":

        show_customer_menu(
            phone
        )

        return True


    if action_id == "driver_menu":

        show_driver_menu(
            phone,
            user
        )

        return True


    # =====================================================
    # מזמין
    # =====================================================

    if action_id == "customer_new_shipment":

        start_new_shipment(
            phone
        )

        return True


    if action_id == "customer_my_shipments":

        show_customer_shipments(
            phone
        )

        return True


    if action_id == "customer_guide":

        send_message(
            phone,
            customer_guide()
        )

        return True


    # =====================================================
    # שליח
    # =====================================================

    if action_id == "driver_available":

        save_session(
            phone,
            "driver_available_city",
            {}
        )

        send_message(
            phone,
            (
                "📍 באיזו עיר אתה פנוי?\n\n"
                "לדוגמה: ירושלים"
            )
        )

        return True


    if (
        state == "driver_available_city"
        and text
        and not action_id
    ):

        clear_session(
            phone
        )

        set_driver_available(
            phone,
            text.strip()
        )

        return True


    if action_id == "driver_open_shipments":

        show_open_shipments_to_driver(
            phone
        )

        return True


    if action_id == "driver_my_shipments":

        show_driver_shipments(
            phone
        )

        return True


    if action_id == "driver_guide":

        send_message(
            phone,
            driver_guide()
        )

        return True


    if action_id == "driver_subscription":

        show_driver_subscription(
            phone,
            user
        )

        return True


    if action_id == "driver_pay_subscription":

        show_driver_payment_methods(
            phone
        )

        return True


    if action_id == "pay_bank":

        start_subscription_payment(
            phone,
            "bank"
        )

        return True


    if action_id == "pay_bit":

        start_subscription_payment(
            phone,
            "bit"
        )

        return True


    if action_id == "pay_paybox":

        start_subscription_payment(
            phone,
            "paybox"
        )

        return True


    # =====================================================
    # התעניינות שליח
    # =====================================================

    if action_id.startswith(
        "driver_interest_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        start_driver_interest(
            phone,
            shipment_id
        )

        return True


    # =====================================================
    # מזמין בוחר שליח
    # =====================================================

    if action_id.startswith(
        "customer_select_driver_"
    ):

        try:

            parts = action_id.split(
                "_"
            )

            shipment_id = int(
                parts[-2]
            )

            driver_id = int(
                parts[-1]
            )

        except Exception:

            return True


        select_driver_for_shipment(
            phone,
            shipment_id,
            driver_id
        )

        return True


    if action_id.startswith(
        "customer_view_interest_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        show_shipment_interests(
            phone,
            shipment_id
        )

        return True


    # =====================================================
    # עריכת משלוח
    # =====================================================

    if action_id.startswith(
        "customer_edit_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        show_edit_shipment_menu(
            phone,
            shipment_id
        )

        return True


    edit_map = {
        "edit_price_":
            "price",

        "edit_pickup_":
                         "pickup_address",

        "edit_dropoff_":
            "dropoff_address",

        "edit_time_":
            "pickup_time",

        "edit_package_":
            "package_description",

        "edit_notes_":
            "notes",
    }


    for prefix, field in edit_map.items():

        if action_id.startswith(
            prefix
        ):

            try:

                shipment_id = int(
                    action_id.rsplit(
                        "_",
                        1
                    )[1]
                )

            except Exception:

                return True


            start_shipment_edit(
                phone,
                shipment_id,
                field
            )

            return True


    # =====================================================
    # ביטול משלוח
    # =====================================================

    if action_id.startswith(
        "customer_cancel_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        cancel_shipment(
            phone,
            shipment_id
        )

        return True


    # =====================================================
    # השלמת משלוח
    # =====================================================

    if action_id.startswith(
        "customer_complete_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        complete_shipment(
            phone,
            shipment_id
        )

        return True


    # =====================================================
    # דירוג 3–5
    # =====================================================

    if action_id.startswith(
        "rate_more_"
    ):

        try:

            shipment_id = int(
                action_id.rsplit(
                    "_",
                    1
                )[1]
            )

        except Exception:

            return True


        show_more_rating_options(
            phone,
            shipment_id
        )

        return True


    # =====================================================
    # שמירת דירוג
    # action:
    # rate_123_5
    # =====================================================

    if action_id.startswith(
        "rate_"
    ):

        try:

            parts = action_id.split(
                "_"
            )

            shipment_id = int(
                parts[-2]
            )

            stars = int(
                parts[-1]
            )

        except Exception:

            return True


        save_driver_rating(
            phone,
            shipment_id,
            stars
        )

        return True


    # =====================================================
    # תמיכה
    # =====================================================

    if action_id == "support_new":

        start_support_request(
            phone
        )

        return True


    support_categories = {

        "support_cat_shipment":
            "בעיה במשלוח",

        "support_cat_user":
            "בעיה עם משתמש",

        "support_cat_payment":
            "תשלום / מנוי",

        "support_cat_account":
            "חשבון",

        "support_cat_other":
            "אחר",
    }


    if action_id in support_categories:

        support_category_selected(
            phone,
            support_categories[
                action_id
            ]
        )

        return True


    return False


# =========================================================
# חילוץ מידע מהודעת WhatsApp
# =========================================================

def extract_whatsapp_message(
    incoming
):

    phone = ""
    text = ""
    action_id = ""
    media_id = ""
    message_id = ""


    try:

        entry = incoming.get(
            "entry",
            []
        )[0]


        change = entry.get(
            "changes",
            []
        )[0]


        value = change.get(
            "value",
            {}
        )


        messages = value.get(
            "messages",
            []
        )


        if not messages:

            return {
                "phone": "",
                "text": "",
                "action_id": "",
                "media_id": "",
                "message_id": "",
            }


        message = messages[0]


        phone = normalize_phone(
            message.get(
                "from",
                ""
            )
        )


        message_id = message.get(
            "id",
            ""
        )


        message_type = message.get(
            "type",
            ""
        )


        # -----------------------------------------
        # הודעת טקסט
        # -----------------------------------------

        if message_type == "text":

            text = (
                message.get(
                    "text",
                    {}
                ).get(
                    "body",
                    ""
                )
                or ""
            ).strip()


        # -----------------------------------------
        # תמונה
        # -----------------------------------------

        elif message_type == "image":

            media_id = (
                message.get(
                    "image",
                    {}
                ).get(
                    "id",
                    ""
                )
                or ""
            )


            text = (
                message.get(
                    "image",
                    {}
                ).get(
                    "caption",
                    ""
                )
                or ""
            ).strip()


        # -----------------------------------------
        # כפתור / רשימה
        # -----------------------------------------

        elif message_type == "interactive":

            interactive = message.get(
                "interactive",
                {}
            )


            interactive_type = interactive.get(
                "type",
                ""
            )


            if interactive_type == "button_reply":

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


            elif interactive_type == "list_reply":

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


        # -----------------------------------------
        # תמיכה גם בכפתור מהסוג הישן
        # -----------------------------------------

        elif message_type == "button":

            button = message.get(
                "button",
                {}
            )

            action_id = (
                button.get(
                    "payload",
                    ""
                )
                or ""
            )

            text = (
                button.get(
                    "text",
                    ""
                )
                or ""
            )


    except Exception:

        traceback.print_exc()


    return {
        "phone":
            phone,

        "text":
            text,

        "action_id":
            action_id,

        "media_id":
            media_id,

        "message_id":
            message_id,
    }


# =========================================================
# GET - אימות Webhook של Meta
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
# POST - קבלת הודעות WhatsApp
# =========================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    incoming = (
        request.get_json(
            silent=True
        )
        or {}
    )


    parsed = extract_whatsapp_message(
        incoming
    )


    phone = parsed.get(
        "phone",
        ""
    )

    text = parsed.get(
        "text",
        ""
    )

    action_id = parsed.get(
        "action_id",
        ""
    )

    media_id = parsed.get(
        "media_id",
        ""
    )

    message_id = parsed.get(
        "message_id",
        ""
    )


    # אירועי סטטוס של WhatsApp
    # לא דורשים טיפול.
    if not phone:

        return (
            "ok",
            200
        )


    if is_duplicate_message(
        message_id
    ):

        return (
            "ok",
            200
        )


    try:

        # -----------------------------------------
        # המנהל מטופל ראשון
        # -----------------------------------------

        if phone == ADMIN_PHONE:

            if handle_admin_action(
                phone,
                text,
                action_id
            ):

                return (
                    "ok",
                    200
                )


            # אם המנהל שולח "תפריט"
            if (
                text.strip()
                in (
                    "תפריט",
                    "מנהל",
                    "היי",
                    "הי",
                    "שלום"
                )
                and not action_id
            ):

                clear_session(
                    phone
                )

                show_admin_menu(
                    phone
                )

                return (
                    "ok",
                    200
                )


            show_admin_menu(
                phone
            )

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # מצב תחזוקה
        # -----------------------------------------

        if (
            get_setting(
                "maintenance_mode",
                "0"
            )
            == "1"
        ):

            send_message(
                phone,

                f"""
🛠️ {BOT_NAME} נמצא כרגע בתחזוקה.

אנא נסה שוב מאוחר יותר.
""".strip()
            )

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # משתמש חסום
        # -----------------------------------------

        user = get_user(
            phone
        )


        if (
            user
            and int(
                user.get(
                    "is_blocked"
                )
                or 0
            )
            == 1
        ):

            send_message(
                phone,

                (
                    "🚫 החשבון שלך חסום במערכת."
                )
            )

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # "פנוי ירושלים" / "פ ירושלים"
        # -----------------------------------------

        if text.strip() == "תפוס" and not action_id:
            if user and user.get("role") in (ROLE_DRIVER, ROLE_DISPATCHER):
                set_driver_busy(phone)
                return ("ok", 200)
        city = parse_available_city(
            text
        )


        if city:

            if not user:

                show_role_choice(
                    phone
                )

                return (
                    "ok",
                    200
                )


            if (
                user.get("role")
                not in (
                    ROLE_DRIVER,
                    ROLE_DISPATCHER
                )
            ):

                send_message(
                    phone,

                    (
                        "פקודת 'פנוי' מיועדת "
                        "לשליחים ולסדרנים."
                    )
                )

                return (
                    "ok",
                    200
                )


            set_driver_available(
                phone,
                city
            )

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # משתמש חדש או תהליך הרשמה קיים
        # -----------------------------------------

        current_session = get_session(
            phone
        )


        if (
            not user
            or current_session.get(
                "state",
                ""
            ).startswith(
                (
                    "choose_role",
                    "customer_",
                    "driver_"
                )
            )
        ):

            if handle_registration(
                phone,
                text,
                action_id
            ):

                return (
                    "ok",
                    200
                )


            if not user:

                show_role_choice(
                    phone
                )

                return (
                    "ok",
                    200
                )


        # -----------------------------------------
        # פעולות משתמש
        # -----------------------------------------

        if handle_user_action(
            phone,
            user,
            text,
            action_id,
            media_id
        ):

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # מילים לפתיחת תפריט
        # -----------------------------------------

        if (
            text.strip()
            in (
                "תפריט",
                "היי",
                "הי",
                "שלום",
                "התחל",
                "start",
                "menu"
            )
            and not action_id
        ):

            clear_session(
                phone
            )

            show_menu_for_user(
                phone,
                user
            )

            return (
                "ok",
                200
            )


        # -----------------------------------------
        # ברירת מחדל
        # -----------------------------------------

        show_menu_for_user(
            phone,
            user
        )


    except Exception as exc:

        print(
            "WEBHOOK ERROR:",
            repr(exc),
            flush=True
        )

        traceback.print_exc()


        try:

            send_message(
                ADMIN_PHONE,

                f"""
⚠️ שגיאה ב-{BOT_NAME}

סוג:
{type(exc).__name__}

שגיאה:
{str(exc)[:500]}
""".strip()
            )

        except Exception:

            pass


    return (
        "ok",
        200
    )


# =========================================================
# בדיקת שרת
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        f"{BOT_NAME} is running",
        200
    )


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
