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

1. לפני לחיצה על "אני מעוניין" יש לבדוק את פרטי המשלוח, המסלול, המחיר, המועד והזמינות שלך.

2. לחיצה על "אני מעוניין" מהווה הצהרה כי יש לך כוונה אמיתית ויכולת לבצע את המשלוח בהתאם לפרטים שפורסמו.

3. אין ללחוץ על "אני מעוניין" סתם או כאשר אינך בטוח שתוכל לבצע את המשלוח.

4. לאחר שהמזמין בחר בך, עליך לעמוד בהתחייבות ולעדכן בהקדם במקרה חריג שמונע את ביצוע המשלוח.

5. לחיצות סרק, אי-הגעה, ביטולים חוזרים לאחר התחייבות או מסירת זמני הגעה לא נכונים במכוון עלולים להביא להגבלת החשבון, להשעיה או לחסימה.

6. השליח אחראי לביצוע המשלוח שקיבל על עצמו ולשמירת המשלוח בזמן שהוא ברשותו.

7. באחריות השליח להחזיק רישיון, ביטוח וכל אישור אחר הנדרש לפי דין.

8. השליח מתחייב לשמור על פרטיות המזמין, הנמען ופרטי המשלוח.

9. {BOT_NAME} משמשת כפלטפורמה המקשרת בין מזמינים לשליחים ואינה צד לעסקה הישירה שביניהם.

10. האחריות להסכמות ולביצוע המשלוח מוטלת על הצדדים בהתאם לדין.

11. במקרה של בעיה ניתן לפנות לנציג דרך המערכת ואנו ננסה לסייע בבירור ובפתרון ככל שניתן.

12. השליח מאשר כי מערכת המנויים חלה על חשבון שליח בהתאם להגדרות המערכת.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים.
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
