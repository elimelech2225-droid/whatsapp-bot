from flask import Flask, request
import os
import re
import time
import sqlite3
import requests

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
ADMIN_PHONE = re.sub(r"\D", "", os.environ.get("ADMIN_PHONE", ""))
GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v23.0")
DB_PATH = os.environ.get("DB_PATH", "bot.db")

ROLE_CUSTOMER = "CUSTOMER"
ROLE_DRIVER = "DRIVER"
ROLE_ADMIN = "ADMIN"

REG_IN_PROGRESS = "REGISTRATION_IN_PROGRESS"
REG_WAITING = "WAITING_ADMIN_APPROVAL"
REG_APPROVED = "APPROVED"
REG_REJECTED = "REJECTED"
REG_BLOCKED = "BLOCKED"

AVAIL_OFFLINE = "OFFLINE"
AVAIL_AVAILABLE = "AVAILABLE"
AVAIL_BUSY = "BUSY"


# =========================================================
# בסיס נתונים
# =========================================================

def now_ts():
    return int(time.time())


def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
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
            updated_at INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS driver_profiles (
            user_id INTEGER PRIMARY KEY,
            availability_status TEXT DEFAULT 'OFFLINE',
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
            proof_file_url TEXT DEFAULT '',
            submitted_at INTEGER DEFAULT 0,
            approved_at INTEGER DEFAULT 0,
            rejected_at INTEGER DEFAULT 0,
            rejection_reason TEXT DEFAULT '',
            approved_by_admin_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            driver_id INTEGER,
            status TEXT DEFAULT 'DRAFT',
            origin_city TEXT DEFAULT '',
            destination_city TEXT DEFAULT '',
            pickup_address TEXT DEFAULT '',
            dropoff_address TEXT DEFAULT '',
            package_description TEXT DEFAULT '',
            price INTEGER,
            created_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
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
            admin_id INTEGER
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


init_db()


# =========================================================
# כלי עזר
# =========================================================

def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")

    if digits.startswith("0"):
        return "972" + digits[1:]

    return digits


def get_user(phone):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone_number=?",
            (phone,)
        ).fetchone()

    return dict(row) if row else None


def get_session(phone):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE phone=?",
            (phone,)
        ).fetchone()

    return dict(row) if row else {}


def save_session(phone, **fields):
    current = get_session(phone)

    data = {
        "state": current.get("state", ""),
        "temp_role": current.get("temp_role", ""),
        "temp_full_name": current.get("temp_full_name", ""),
        "temp_business_name": current.get("temp_business_name", ""),
        "temp_email": current.get("temp_email", ""),
        "temp_city": current.get("temp_city", ""),
        "temp_vehicle_type": current.get("temp_vehicle_type", ""),
        "temp_vehicle_number": current.get("temp_vehicle_number", ""),
        "temp_service_areas": current.get("temp_service_areas", ""),
        "updated_at": now_ts(),
    }

    data.update(fields)

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
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

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
            data["updated_at"],
        ))


def clear_session(phone):
    with db() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE phone=?",
            (phone,)
        )


# =========================================================
# WhatsApp
# =========================================================

def api_url():
    return (
        f"https://graph.facebook.com/"
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
            timeout=20,
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


def send_buttons(phone, text, buttons):
    items = []

    for button_id, title in buttons[:3]:
        items.append({
            "type": "reply",
            "reply": {
                "id": button_id[:256],
                "title": title[:20],
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


def send_list(phone, text, button_text, sections):
    return send_payload({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": text
            },
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        },
    })


# =========================================================
# מניעת הודעות כפולות
# =========================================================

def is_duplicate(message_id):
    if not message_id:
        return False

    with db() as conn:
        conn.execute(
            "DELETE FROM processed_messages WHERE created_at < ?",
            (now_ts() - 86400,)
        )

        row = conn.execute(
            "SELECT 1 FROM processed_messages WHERE message_id=?",
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
                now_ts(),
            )
        )

    return False


# =========================================================
# הרשמה
# =========================================================

def role_label(role):
    if role == ROLE_CUSTOMER:
        return "לקוח / שולח"

    return "שליח"


def show_role_choice(phone):
    save_session(
        phone,
        state="choose_role"
    )

    send_buttons(
        phone,
        """ברוכים הבאים למערכת המשלוחים 🚚

לפני שמתחילים, יש לבחור כיצד ברצונך להירשם.

שים לב:
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
        ],
    )


def customer_agreement():
    return """הסכם שימוש ללקוח / שולח

1. אני מאשר שהפרטים שאמסור לגבי המשלוח נכונים.
2. אין למסור למשלוח פריטים אסורים, בלתי חוקיים או מסוכנים.
3. באחריותי למסור כתובות ופרטי איסוף ומסירה מדויקים.
4. המערכת משמשת לחיבור בין לקוחות לבין שליחים עצמאיים.
5. זמני המשלוח עשויים להשתנות עקב עומסים, מזג אוויר, זמינות שליחים ונסיבות נוספות.
6. בקשת ביטול אינה בהכרח ביטול אוטומטי וייתכן שתדרוש אישור מנהל.
7. אם שליח כבר קיבל את המשלוח, הביטול כפוף לאישור.
8. תשלומים ומנויים כפופים למסלול שנבחר ולתנאי השירות.
9. המערכת רשאית לחסום או להשעות משתמש שעושה שימוש לרעה בשירות.
10. פרטי משלוח רלוונטיים יועברו לשליח שמבצע את המשלוח.
11. אני מסכים לשמירת נתוני הרשמה, משלוחים, סטטוסים ותשלומים לצורך הפעלת השירות.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים."""


def driver_agreement():
    return """הסכם שימוש לשליח

1. אני מתחייב לבצע משלוחים שקיבלתי באחריות ובנאמנות.
2. אקבל רק משלוח שאני מסוגל ומתכוון לבצע.
3. אשמור על פרטיות הלקוח והנמען.
4. אפעל בהתאם לחוקי התעבורה ולכל דין החל עליי.
5. באחריותי להחזיק רישיון, ביטוח ואישורים תקפים כנדרש.
6. אשמור על המשלוח כל עוד הוא נמצא ברשותי.
7. לא אפתח, אשתמש, אעכב, אגנוב או אפגע במשלוח במכוון.
8. אעדכן את סטטוס המשלוח בצורה נכונה.
9. אדווח למנהל על כל תקלה או בעיה מהותית.
10. ידוע לי שהמערכת מחברת בין לקוחות לשליחים.
11. המערכת רשאית להשעות או לחסום שליח עקב הפרות, שימוש לרעה או בעיות שירות חוזרות.
12. שחרור ממשלוח שכבר קיבלתי עשוי לדרוש אישור מנהל.
13. אני מסכים לתנאי המנוי והתשלום הרלוונטיים.

בלחיצה על "אני מסכים" אני מאשר שקראתי והבנתי את התנאים."""


def create_pending_user(phone, session):
    role = session.get(
        "temp_role",
        ""
    )

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
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '1.0', ?, ?, ?)

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
        ))

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone_number=?
            """,
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
                INSERT INTO driver_profiles(
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
                user["id"],
                AVAIL_OFFLINE,
                1 if all_country else 0,
            ))

            conn.execute(
                """
                DELETE FROM driver_service_areas
                WHERE driver_id=?
                """,
                (user["id"],)
            )

            areas = session.get(
                "temp_service_areas",
                ""
            )

            if areas and not all_country:
                cities = [
                    city.strip()
                    for city in areas.split(",")
                    if city.strip()
                ]

                for city in cities:
                    conn.execute("""
                        INSERT OR IGNORE INTO driver_service_areas(
                            driver_id,
                            city,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, 1, ?, ?)
                    """, (
                        user["id"],
                        city,
                        now_ts(),
                        now_ts(),
                    ))

    clear_session(phone)

    return get_user(phone)


# =========================================================
# מנהל
# =========================================================

def notify_admin_new_registration(user):
    if not ADMIN_PHONE:
        print("ERROR: ADMIN_PHONE is not configured")
        return False

    extra = ""

    if user["role"] == ROLE_CUSTOMER:
        extra = (
            f"\nשם העסק: "
            f"{user.get('business_name') or '-'}"
        )

    else:
        with db() as conn:
            profile = conn.execute(
                """
                SELECT all_country
                FROM driver_profiles
                WHERE user_id=?
                """,
                (user["id"],)
            ).fetchone()

            areas = conn.execute(
                """
                SELECT city
                FROM driver_service_areas
                WHERE driver_id=?
                AND is_active=1
                ORDER BY city
                """,
                (user["id"],)
            ).fetchall()

        if (
            profile
            and profile["all_country"]
        ):
            area_text = "כל הארץ"

        else:
            area_text = (
                ", ".join(
                    row["city"]
                    for row in areas
                )
                or "-"
            )

        extra = (
            f"\nסוג רכב: "
            f"{user.get('vehicle_type') or '-'}"
            f"\nמספר רכב: "
            f"{user.get('vehicle_number') or '-'}"
            f"\nאזורי פעילות: "
            f"{area_text}"
        )

    return send_buttons(
        ADMIN_PHONE,
        f"""בקשת הרשמה חדשה 👤

מזהה משתמש: {user['id']}
שם: {user['full_name']}
טלפון: {user['phone_number']}
תפקיד: {role_label(user['role'])}
עיר: {user['city']}{extra}

לאשר את ההרשמה?""",
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
        ],
    )


def approve_user(user_id):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (user_id,)
        ).fetchone()

        if not row:
            return None

        conn.execute("""
            UPDATE users
            SET
                registration_status=?,
                admin_approved_at=?,
                updated_at=?,
                is_blocked=0
            WHERE id=?
        """, (
            REG_APPROVED,
            now_ts(),
            now_ts(),
            user_id,
        ))

        conn.execute("""
            INSERT INTO admin_actions(
                admin_phone,
                target_user_id,
                action_type,
                created_at
            )
            VALUES (?, ?, 'REGISTER_APPROVED', ?)
        """, (
            ADMIN_PHONE,
            user_id,
            now_ts(),
        ))

    return get_user(
        row["phone_number"]
    )


def reject_user(
    user_id,
    reason="לא צוין"
):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
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
            user_id,
        ))

        conn.execute("""
            INSERT INTO admin_actions(
                admin_phone,
                target_user_id,
                action_type,
                notes,
                created_at
            )
            VALUES (?, ?, 'REGISTER_REJECTED', ?, ?)
        """, (
            ADMIN_PHONE,
            user_id,
            reason,
            now_ts(),
        ))

    return get_user(
        row["phone_number"]
    )


def block_user(user_id):
    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
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
            user_id,
        ))

        conn.execute("""
            INSERT INTO admin_actions(
                admin_phone,
                target_user_id,
                action_type,
                created_at
            )
            VALUES (?, ?, 'USER_BLOCKED', ?)
        """, (
            ADMIN_PHONE,
            user_id,
            now_ts(),
        ))

    return get_user(
        row["phone_number"]
    )


def show_admin_menu(phone):
    send_list(
        phone,
        "תפריט מנהל 👑",
        "פתיחת תפריט",
        [
            {
                "title": "ניהול",
                "rows": [
                    {
                        "id": "admin_pending_users",
                        "title": "ממתינים לאישור",
                    },
                    {
                        "id": "admin_help",
                        "title": "עזרה למנהל",
                    },
                ],
            }
        ],
    )


def send_pending_users(phone):
    with db() as conn:
        rows = conn.execute("""
            SELECT
                id,
                full_name,
                phone_number,
                role,
                city
            FROM users

            WHERE registration_status=?

            ORDER BY created_at ASC

            LIMIT 20
        """, (
            REG_WAITING,
        )).fetchall()

    if not rows:
        send_message(
            phone,
            "אין כרגע משתמשים שממתינים לאישור ✅"
        )
        return

    send_message(
        phone,
        f"יש כרגע {len(rows)} משתמשים שממתינים לאישור."
    )

    for row in rows:
        send_buttons(
            phone,
            f"""בקשת הרשמה

מזהה: {row['id']}
שם: {row['full_name']}
טלפון: {row['phone_number']}
תפקיד: {role_label(row['role'])}
עיר: {row['city']}""",
            [
                (
                    f"approve_{row['id']}",
                    "אשר הרשמה"
                ),
                (
                    f"reject_{row['id']}",
                    "דחה הרשמה"
                ),
                (
                    f"block_{row['id']}",
                    "חסום משתמש"
                ),
            ],
        )


def handle_admin_action(
    phone,
    text,
    action_id
):
    if (
        not ADMIN_PHONE
        or phone != ADMIN_PHONE
    ):
        return False

    match = re.match(
        r"^(approve|reject|block)_(\d+)$",
        action_id or ""
    )

    if match:
        action = match.group(1)
        user_id = int(
            match.group(2)
        )

        if action == "approve":
            user = approve_user(
                user_id
            )

            if not user:
                send_message(
                    phone,
                    "המשתמש לא נמצא."
                )
                return True

            if user["role"] == ROLE_CUSTOMER:
                send_message(
                    user["phone_number"],
                    """ההרשמה שלך אושרה ✅

ברוך הבא למערכת.

כעת ניתן להתחיל להשתמש בשירות ולפתוח משלוחים."""
                )

            else:
                send_message(
                    user["phone_number"],
                    """ההרשמה שלך כשליח אושרה ✅

ברוך הבא למערכת.

כעת ניתן להיכנס לתפריט השליח ולהגדיר זמינות ואזורי פעילות."""
                )

            send_message(
                phone,
                f"המשתמש {user_id} אושר בהצלחה ✅"
            )

            return True

        if action == "reject":
            save_session(
                phone,
                state=
                    f"admin_reject_reason:{user_id}"
            )

            send_message(
                phone,
                """כתוב את סיבת הדחייה.

אם אינך רוצה לציין סיבה, כתוב:
ללא"""
            )

            return True

        if action == "block":
            user = block_user(
                user_id
            )

            if user:
                send_message(
                    user["phone_number"],
                    """החשבון שלך נחסם.

יש לפנות למנהל."""
                )

                send_message(
                    phone,
                    f"המשתמש {user_id} נחסם."
                )

            else:
                send_message(
                    phone,
                    "המשתמש לא נמצא."
                )

            return True

    session = get_session(phone)

    state = session.get(
        "state",
        ""
    )

    if state.startswith(
        "admin_reject_reason:"
    ):
        user_id = int(
            state.split(
                ":",
                1
            )[1]
        )

        reason = (
            "לא צוין"
            if text.strip() == "ללא"
            else text.strip()
        )

        user = reject_user(
            user_id,
            reason
        )

        clear_session(phone)

        if user:
            send_message(
                user["phone_number"],
                f"""ההרשמה לא אושרה.

סיבה:
{reason}

לפרטים נוספים ניתן לפנות למנהל."""
            )

            send_message(
                phone,
                f"המשתמש {user_id} נדחה."
            )

        else:
            send_message(
                phone,
                "המשתמש לא נמצא."
            )

        return True

    if action_id == "admin_pending_users":
        send_pending_users(
            phone
        )
        return True

    if action_id == "admin_help":
        send_message(
            phone,
            """מצב מנהל פעיל ✅

בקשות הרשמה חדשות יישלחו אליך כאן.

אפשר לאשר, לדחות או לחסום משתמש.

בהמשך גם בקשות ביטול ותשלומים יישלחו לכאן."""
        )

        return True

    return False


# =========================================================
# תפריט לקוח
# =========================================================

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
                        "title": "הזמנת משלוח חדש",
                    },
                    {
                        "id": "customer_my_shipments",
                        "title": "המשלוחים שלי",
                    },
                    {
                        "id": "customer_cancel",
                        "title": "בקשת ביטול",
                    },
                    {
                        "id": "customer_subscription",
                        "title": "מנוי ותשלומים",
                    },
                    {
                        "id": "customer_profile",
                        "title": "עדכון פרטים",
                    },
                    {
                        "id": "customer_support",
                        "title": "צור קשר / תמיכה",
                    },
                ],
            }
        ],
    )


# =========================================================
# תפריט שליח
# =========================================================

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
                        "title": "אני פנוי",
                    },
                    {
                        "id": "driver_offline",
                        "title": "אני לא פנוי",
                    },
                    {
                        "id": "driver_areas",
                        "title": "אזורי הפעילות שלי",
                    },
                    {
                        "id": "driver_open_shipments",
                        "title": "משלוחים פתוחים",
                    },
                    {
                        "id": "driver_my_shipments",
                        "title": "המשלוחים שלי",
                    },
                    {
                        "id": "driver_guide",
                        "title": "מדריך לשליח",
                    },
                    {
                        "id": "driver_subscription",
                        "title": "מנוי ותשלומים",
                    },
                    {
                        "id": "driver_profile",
                        "title": "עדכון פרטים",
                    },
                    {
                        "id": "driver_support",
                        "title": "צור קשר / תמיכה",
                    },
                ],
            }
        ],
    )


def set_driver_availability(
    phone,
    status
):
    user = get_user(phone)

    if (
        not user
        or user["role"] != ROLE_DRIVER
    ):
        return

    with db() as conn:
        conn.execute("""
            INSERT INTO driver_profiles(
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
            status,
        ))


def driver_guide_text():
    return """מדריך לשליח 🚚

• "אני פנוי" — מפעיל קבלת הצעות למשלוחים.

• "אני לא פנוי" — מפסיק קבלת הצעות חדשות.

• "אזורי הפעילות שלי" — מאפשר לבחור ערים או "כל הארץ".

• "משלוחים פתוחים" — יציג בהמשך משלוחים שמתאימים לאזורים ולזמינות שלך.

• לאחר קבלת משלוח יהיו שלבים:
אני בדרך לאיסוף
אספתי
בדרך ליעד
נמסר

• אם תרצה להשתחרר ממשלוח שכבר קיבלת, תישלח בקשה למנהל.

• "מנוי ותשלומים" — מיועד לבחירת מסלול ושליחת אישור תשלום.

• "צור קשר / תמיכה" — לפנייה למנהל."""


# =========================================================
# תהליך הרשמה
# =========================================================

def handle_registration(
    phone,
    text,
    action_id
):
    session = get_session(phone)

    state = session.get(
        "state",
        ""
    )

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
            "יש לבחור אחת מהאפשרויות באמצעות הכפתורים."
        )

        return True

    # =====================================================
    # לקוח
    # =====================================================

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
            'מה האימייל שלך? אם אין או לא רוצה למסור, כתוב "אין".'
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
            ],
        )

        return True

    if action_id == "customer_details_edit":
        save_session(
            phone,
            state="customer_name"
        )

        send_message(
            phone,
            "אין בעיה. נתחיל מחדש. מה השם המלא שלך?"
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
            ],
        )

        return True

    # =====================================================
    # שליח
    # =====================================================

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
                            "title": "רכב פרטי",
                        },
                        {
                            "id": "vehicle_motorcycle",
                            "title": "אופנוע / קטנוע",
                        },
                        {
                            "id": "vehicle_commercial",
                            "title": "רכב מסחרי",
                        },
                        {
                            "id": "vehicle_other",
                            "title": "אחר",
                        },
                    ],
                }
            ],
        )

        return True

    vehicle_map = {
        "vehicle_private":
            "רכב פרטי",

        "vehicle_motorcycle":
            "אופנוע / קטנוע",

        "vehicle_commercial":
            "רכב מסחרי",

        "vehicle_other":
            "אחר",
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
            'מה מספר הרכב? אם אינך רוצה למסור כרגע, כתוב "אין".'
        )

        return True

    if state == "driver_vehicle_number":
        vehicle_number = (
            ""
            if text.strip() == "אין"
            else text.strip()
        )

        save_session(
            phone,
            state="driver_areas",
            temp_vehicle_number=
                vehicle_number
        )

        send_message(
            phone,
            """באילו אזורים אתה רוצה לעבוד?

אפשר לרשום כמה ערים מופרדות בפסיקים.

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
            ],
        )

        return True

    # =====================================================
    # הסכם
    # =====================================================

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

        if user["role"] == ROLE_CUSTOMER:
            send_message(
                phone,
                """ההרשמה התקבלה ✅

החשבון שלך ממתין כעת לאישור מנהל.

לאחר אישור המנהל תקבל הודעה אוטומטית ולאחר מכן תוכל להשתמש במערכת."""
            )

        else:
            send_message(
                phone,
                """ההרשמה שלך כשליח התקבלה ✅

הפרטים הועברו למנהל לבדיקה.

עד לאישור המנהל לא ניתן לקבל משלוחים."""
            )

        notify_admin_new_registration(
            user
        )

        return True

    return False


# =========================================================
# משתמש מאושר
# =========================================================

def handle_approved_user(
    phone,
    user,
    text,
    action_id
):
    if (
        action_id == "driver_available"
        and user["role"] == ROLE_DRIVER
    ):
        set_driver_availability(
            phone,
            AVAIL_AVAILABLE
        )

        send_message(
            phone,
            "סומן שאתה פנוי לקבלת משלוחים ✅"
        )

        return

    if (
        action_id == "driver_offline"
        and user["role"] == ROLE_DRIVER
    ):
        set_driver_availability(
            phone,
            AVAIL_OFFLINE
        )

        send_message(
            phone,
            "לא יישלחו אליך משלוחים חדשים עד שתסמן שאתה פנוי."
        )

        return

    if (
        action_id == "driver_guide"
        and user["role"] == ROLE_DRIVER
    ):
        send_message(
            phone,
            driver_guide_text()
        )

        return

    if (
        action_id == "driver_areas"
        and user["role"] == ROLE_DRIVER
    ):
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

        if (
            profile
            and profile["all_country"]
        ):
            current = "כל הארץ"

        else:
            current = (
                ", ".join(
                    row["city"]
                    for row in rows
                )
                or "לא הוגדרו אזורים"
            )

        send_message(
            phone,
            f"""אזורי הפעילות שלך:

{current}

עריכת אזורים מלאה תתווסף בשלב הבא."""
        )

        return

    placeholder_ids = {
        "customer_new_delivery",
        "customer_my_shipments",
        "customer_cancel",
        "customer_subscription",
        "customer_profile",
        "customer_support",
        "driver_open_shipments",
        "driver_my_shipments",
        "driver_subscription",
        "driver_profile",
        "driver_support",
    }

    if action_id in placeholder_ids:
        send_message(
            phone,
            """האפשרות הזאת מוכנה בתפריט ותופעל בשלב הבא של הפיתוח."""
        )
        return

    clean = (
        text
        or ""
    ).strip().lower()

    if clean in {
        "תפריט",
        "שלום",
        "היי",
        "הי",
        "menu",
    }:
        if user["role"] == ROLE_CUSTOMER:
            show_customer_menu(phone)
        else:
            show_driver_menu(phone)

        return

    if user["role"] == ROLE_CUSTOMER:
        show_customer_menu(phone)
    else:
        show_driver_menu(phone)


# =========================================================
# קריאת הודעת WhatsApp
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
            msg.get(
                "from",
                ""
            )
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

        if msg_type == "text":
            text = (
                msg.get(
                    "text",
                    {}
                )
                .get(
                    "body",
                    ""
                )
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

        return {
            "phone": phone,
            "message_id": message_id,
            "text": text,
            "action_id": action_id,
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

@app.route(
    "/",
    methods=["GET"]
)
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
            challenge
            or "",
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

    phone = incoming[
        "phone"
    ]

    message_id = incoming[
        "message_id"
    ]

    text = incoming[
        "text"
    ]

    action_id = incoming[
        "action_id"
    ]

    if not phone:
        return "ok", 200

    if is_duplicate(
        message_id
    ):
        return "ok", 200

    try:

        # =====================================================
        # חשוב:
        # המנהל תמיד מקבל עדיפות לפני כל משתמש אחר
        # =====================================================

        if (
            ADMIN_PHONE
            and phone == ADMIN_PHONE
        ):

            if handle_admin_action(
                phone,
                text,
                action_id
            ):
                return "ok", 200

            clean = (
                text
                or ""
            ).strip().lower()

            if clean in {
                "ממתינים",
                "ממתינים לאישור",
            }:
                send_pending_users(
                    phone
                )
                return "ok", 200

            show_admin_menu(
                phone
            )

            return "ok", 200

        # =====================================================
        # משתמשים רגילים
        # =====================================================

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
                """החשבון שלך עדיין ממתין לאישור מנהל."""
            )

            return "ok", 200

        if (
            user["registration_status"]
            == REG_REJECTED
        ):
            send_message(
                phone,
                """החשבון שלך אינו מאושר כרגע."""
            )

            return "ok", 200

        if (
            user["registration_status"]
            != REG_APPROVED
        ):
            send_message(
                phone,
                """החשבון שלך עדיין לא פעיל."""
            )

            return "ok", 200

        handle_approved_user(
            phone,
            user,
            text,
            action_id
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
                """אירעה תקלה זמנית.

נסה שוב בעוד רגע."""
            )

        except Exception:
            pass

        return "ok", 200


# =========================================================
# הפעלה
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
