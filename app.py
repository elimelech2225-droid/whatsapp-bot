# ============================================================
# שליחובוט - Shaliachobot
# חלק 1A
# בסיס מערכת + הגדרות + ערים וכינויים + מסד נתונים
# ============================================================

import os
import re
import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify


# ============================================================
# Flask
# ============================================================

app = Flask(__name__)


# ============================================================
# משתני סביבה
# ============================================================

VERIFY_TOKEN = os.getenv(
    "WHATSAPP_VERIFY_TOKEN",
    ""
).strip()

WHATSAPP_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN",
    ""
).strip()

PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID",
    ""
).strip()

WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v23.0"
).strip()

ADMIN_PHONE = "972553155049"
PAPERLESS_API_KEY = os.getenv(
    "PAPERLESS_API_KEY",
    ""
).strip()

PAPERLESS_API_URL = (
    "https://pl-apis-prod-il.azurewebsites.net/api/invoices/create"
)
DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "/var/data/shaliachobot.db"
).strip()





# ============================================================
# תפקידים
# ============================================================

ROLE_CUSTOMER = "customer"
ROLE_DRIVER = "driver"
ROLE_DISPATCHER = "dispatcher"
ROLE_ADMIN = "admin"


# ============================================================
# סטטוס משתמש
# ============================================================

USER_PENDING = "pending"
USER_APPROVED = "approved"
USER_REJECTED = "rejected"
USER_BLOCKED = "blocked"
USER_RESET = "reset"


# ============================================================
# סטטוס משלוח
# ============================================================

SHIP_NEW = "new"
SHIP_OPEN = "open"
SHIP_ASSIGNED = "assigned"
SHIP_COMPLETED = "completed"
SHIP_CANCELLED = "cancelled"
SHIP_NEEDS_PRICE = "needs_price"


# ============================================================
# סטטוס התעניינות שליח
# ============================================================

INTEREST_PENDING = "pending"
INTEREST_SELECTED = "selected"
INTEREST_REJECTED = "rejected"


# ============================================================
# סטטוס פנייה
# ============================================================

SUPPORT_OPEN = "open"
SUPPORT_CLOSED = "closed"


# ============================================================
# סטטוס תשלום
# ============================================================

PAYMENT_PENDING = "pending"
PAYMENT_APPROVED = "approved"
PAYMENT_REJECTED = "rejected"
PAYMENT_REVIEW = "review"
SUB_ACTIVE = "active"
SUB_EXPIRED = "expired"
SUB_CANCELLED = "cancelled"

# ============================================================
# סוגי רכב
# ============================================================

VEHICLE_PRIVATE = "private"
VEHICLE_7_SEATS = "7_seats"
VEHICLE_SMALL_COMMERCIAL = "small_commercial"
VEHICLE_LARGE_COMMERCIAL = "large_commercial"


VEHICLE_LABELS = {
    VEHICLE_PRIVATE:
        "🚗 רכב פרטי",

    VEHICLE_7_SEATS:
        "🚙 רכב 7 מקומות",

    VEHICLE_SMALL_COMMERCIAL:
        "🚐 מסחרי קטן / ברלינגו",

    VEHICLE_LARGE_COMMERCIAL:
        "🚚 מסחרי גדול",
}


# ============================================================
# הגדרות ברירת מחדל
# ============================================================

DEFAULT_SETTINGS = {
    # --------------------------------------------------------
    # המערכת כולה
    # --------------------------------------------------------

    "system_enabled": "1",

    "maintenance_message":
        "🛠️ שליחובוט נמצא כרגע בתחזוקה.\n"
        "נחזור לפעילות בקרוב.",


    # --------------------------------------------------------
    # צד השליחים
    # --------------------------------------------------------

    "driver_side_enabled": "0",


    # --------------------------------------------------------
    # מערכת מנויים
    # --------------------------------------------------------

    "subscriptions_enabled": "0",

    "subscription_price": "0",

    "subscription_days": "30",

    "subscription_reminder_days": "1",


    # --------------------------------------------------------
    # תוספת עזרת שליח
    # --------------------------------------------------------

    "help_extra_private": "50",

    "help_extra_7_seats": "80",

    "help_extra_small_commercial": "80",

    "help_extra_large_commercial": "100",


    # --------------------------------------------------------
    # Bit
    # --------------------------------------------------------

    "bit_enabled": "1",

    "bit_details": "",


    # --------------------------------------------------------
    # PayBox
    # --------------------------------------------------------

    "paybox_enabled": "1",

    "paybox_details": "",


    # --------------------------------------------------------
    # העברה בנקאית
    # --------------------------------------------------------

    "bank_enabled": "1",

    "bank_details": "",


    


    # --------------------------------------------------------
    # התראות
    # --------------------------------------------------------

    "unassigned_alert_minutes": "30",
}


# ============================================================
# זמן
# ============================================================

def now_ts():
    return int(
        time.time()
    )


def now_text():
    return datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )


# ============================================================
# ניקוי מספר טלפון
# ============================================================

def normalize_phone(value):
    value = re.sub(
        r"\D",
        "",
        value or ""
    )

    if value.startswith("00"):
        value = value[2:]

    if value.startswith("0"):
        value = (
            "972"
            + value[1:]
        )

    return value


# ============================================================
# ניקוי טקסט
# ============================================================

def clean_text(value):
    value = (
        value
        or ""
    ).strip()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


# ============================================================
# נרמול בסיסי של מילות חיפוש
# ============================================================

def normalize_lookup_text(value):
    value = clean_text(
        value
    ).lower()

    value = value.replace(
        "־",
        "-"
    )

    value = value.replace(
        "״",
        '"'
    )

    value = value.replace(
        "׳",
        "'"
    )

    return value


# ============================================================
# כינויים מובנים לערים
#
# בנוסף לזה תהיה טבלה במסד שמנהל יכול לערוך מתוך הבוט.
# ============================================================

DEFAULT_CITY_ALIASES = {
    # תל אביב
    "תא": "תל אביב",
    'ת"א': "תל אביב",
    "תל אביב יפו": "תל אביב",
    "תל אביב-יפו": "תל אביב",

    # ראשון לציון
    "ראשון": "ראשון לציון",
    "ראשלצ": "ראשון לציון",
    'ראשל"צ': "ראשון לציון",

    # ירושלים
    "ים": "ירושלים",
    "י-ם": "ירושלים",

    # פתח תקווה
    "פת": "פתח תקווה",
    'פ"ת': "פתח תקווה",
    "פתח תקוה": "פתח תקווה",

    # בני ברק
    "בב": "בני ברק",
    'ב"ב': "בני ברק",
    "בני-ברק": "בני ברק",

    # בית שמש
    "בש": "בית שמש",
    'ב"שמש': "בית שמש",
    "בית-שמש": "בית שמש",

    # באר שבע
    "בשבע": "באר שבע",
    "באר שבע": "באר שבע",

    # מודיעין
    "מודיעין מכבים רעות":
        "מודיעין-מכבים-רעות",

    # קריות
    "קרית גת": "קריית גת",
    "קרית אונו": "קריית אונו",
    "קרית אתא": "קריית אתא",
    "קרית ים": "קריית ים",
    "קרית ביאליק": "קריית ביאליק",
    "קרית מוצקין": "קריית מוצקין",
    "קרית שמונה": "קריית שמונה",
}


# ============================================================
# חיבור למסד
# ============================================================

def db():
    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


# ============================================================
# יצירת מסד הנתונים
# ============================================================

def init_db():
    database_dir = os.path.dirname(
        DATABASE_PATH
    )

    if database_dir:
        os.makedirs(
            database_dir,
            exist_ok=True
        )

    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );


            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                phone TEXT NOT NULL UNIQUE,

                role TEXT NOT NULL DEFAULT 'customer',

                status TEXT NOT NULL DEFAULT 'pending',

                full_name TEXT DEFAULT '',

                business_name TEXT DEFAULT '',

                city TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                approved_at INTEGER DEFAULT 0,

                approved_by TEXT DEFAULT '',

                rejected_at INTEGER DEFAULT 0,

                rejected_by TEXT DEFAULT '',

                blocked_at INTEGER DEFAULT 0,

                blocked_by TEXT DEFAULT '',

                block_reason TEXT DEFAULT ''
            );
                
        
            CREATE INDEX IF NOT EXISTS idx_users_role
            ON users(role);


            CREATE INDEX IF NOT EXISTS idx_users_status
            ON users(status);


            CREATE TABLE IF NOT EXISTS driver_profiles (
                user_id INTEGER PRIMARY KEY,

                vehicle_type TEXT DEFAULT '',

                vehicle_year TEXT DEFAULT '',

                vehicle_description TEXT DEFAULT '',

                id_photo_media_id TEXT DEFAULT '',

                selfie_media_id TEXT DEFAULT '',

                is_available INTEGER DEFAULT 0,

                available_city TEXT DEFAULT '',

                completed_shipments INTEGER DEFAULT 0,

                cancelled_after_assignment INTEGER DEFAULT 0,

                rating_sum INTEGER DEFAULT 0,

                rating_count INTEGER DEFAULT 0,

                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS sessions (
                phone TEXT PRIMARY KEY,

                state TEXT NOT NULL DEFAULT '',

                data TEXT NOT NULL DEFAULT '{}',

                updated_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL UNIQUE,

                is_active INTEGER DEFAULT 1,

                created_by TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS city_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                city_name TEXT NOT NULL,

                alias TEXT NOT NULL UNIQUE,

                created_by TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0
            );


            CREATE INDEX IF NOT EXISTS idx_city_aliases_city
            ON city_aliases(city_name);


            CREATE TABLE IF NOT EXISTS route_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                city_from TEXT NOT NULL,

                city_to TEXT NOT NULL,

                price INTEGER NOT NULL,

                created_by TEXT DEFAULT '',

                created_by_role TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                updated_by TEXT DEFAULT '',

                updated_by_role TEXT DEFAULT '',

                updated_at INTEGER DEFAULT 0,

                UNIQUE(city_from, city_to)
            );
            CREATE TABLE IF NOT EXISTS vehicle_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                price_extra INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_route_prices_cities
            ON route_prices(
                city_from,
                city_to
            );


            CREATE TABLE IF NOT EXISTS route_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                route_price_id INTEGER DEFAULT 0,

                city_from TEXT NOT NULL,

                city_to TEXT NOT NULL,

                old_price INTEGER DEFAULT 0,

                new_price INTEGER DEFAULT 0,

                action TEXT NOT NULL,

                changed_by TEXT DEFAULT '',

                changed_by_role TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                publisher_id INTEGER NOT NULL,

                business_name TEXT DEFAULT '',

                status TEXT NOT NULL DEFAULT 'new',

                origin_city TEXT NOT NULL,

                destination_city TEXT NOT NULL,

                pickup_address TEXT NOT NULL,

                dropoff_address TEXT NOT NULL,

                pickup_time TEXT DEFAULT 'עכשיו',

                vehicle_type TEXT DEFAULT 'private',

                driver_help INTEGER DEFAULT 0,

                base_price INTEGER DEFAULT 0,

                help_extra INTEGER DEFAULT 0,

                final_price INTEGER DEFAULT 0,

                notes TEXT DEFAULT '',

                assigned_driver_id INTEGER,

                assigned_at INTEGER DEFAULT 0,

                completed_at INTEGER DEFAULT 0,

                cancelled_at INTEGER DEFAULT 0,

                cancellation_reason TEXT DEFAULT '',

                rating INTEGER DEFAULT 0,

                rated_at INTEGER DEFAULT 0,

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0,

                FOREIGN KEY(publisher_id)
                    REFERENCES users(id),

                FOREIGN KEY(assigned_driver_id)
                    REFERENCES users(id)
            );


            CREATE INDEX IF NOT EXISTS idx_shipments_status
            ON shipments(status);


            CREATE INDEX IF NOT EXISTS idx_shipments_publisher
            ON shipments(publisher_id);


            CREATE INDEX IF NOT EXISTS idx_shipments_driver
            ON shipments(assigned_driver_id);


            CREATE TABLE IF NOT EXISTS shipment_interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER NOT NULL,

                driver_id INTEGER NOT NULL,

                eta_text TEXT DEFAULT '',

                status TEXT NOT NULL DEFAULT 'pending',

                created_at INTEGER DEFAULT 0,

                updated_at INTEGER DEFAULT 0,

                UNIQUE(
                    shipment_id,
                    driver_id
                ),

                FOREIGN KEY(shipment_id)
                    REFERENCES shipments(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(driver_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS shipment_status_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER NOT NULL,

                status TEXT NOT NULL,

                changed_by TEXT DEFAULT '',

                note TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                FOREIGN KEY(shipment_id)
                    REFERENCES shipments(id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                shipment_id INTEGER NOT NULL UNIQUE,

                publisher_id INTEGER NOT NULL,

                driver_id INTEGER NOT NULL,

                rating INTEGER NOT NULL,

                created_at INTEGER DEFAULT 0,

                FOREIGN KEY(shipment_id)
                    REFERENCES shipments(id),

                FOREIGN KEY(publisher_id)
                    REFERENCES users(id),

                FOREIGN KEY(driver_id)
                    REFERENCES users(id)
            );


            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER,

                phone TEXT NOT NULL,

                shipment_id INTEGER,

                category TEXT DEFAULT '',

                message TEXT DEFAULT '',

                status TEXT NOT NULL DEFAULT 'open',

                created_at INTEGER DEFAULT 0,

                closed_at INTEGER DEFAULT 0,

                closed_by TEXT DEFAULT '',

                FOREIGN KEY(user_id)
                    REFERENCES users(id),

                FOREIGN KEY(shipment_id)
                    REFERENCES shipments(id)
            );


            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                payment_type TEXT NOT NULL DEFAULT 'subscription',

                payment_method TEXT DEFAULT '',

                amount INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL DEFAULT 'pending',

                proof_media_id TEXT DEFAULT '',

                payplus_transaction_uid TEXT DEFAULT '',

                receipt_url TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0,

                approved_at INTEGER DEFAULT 0,

                approved_by TEXT DEFAULT '',

                FOREIGN KEY(user_id)
                    REFERENCES users(id)
            );


            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                status TEXT NOT NULL DEFAULT 'active',

                start_at INTEGER NOT NULL,

                expires_at INTEGER NOT NULL,

                payment_id INTEGER,

                reminder_sent INTEGER DEFAULT 0,

                created_at INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT 0,

                FOREIGN KEY(user_id)
                    REFERENCES users(id),

                FOREIGN KEY(payment_id)
                    REFERENCES payments(id)
            );


            CREATE INDEX IF NOT EXISTS idx_subscriptions_user
            ON subscriptions(user_id);


            CREATE TABLE IF NOT EXISTS admin_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                notification_type TEXT NOT NULL,

                title TEXT NOT NULL,

                message TEXT DEFAULT '',

                entity_type TEXT DEFAULT '',

                entity_id INTEGER DEFAULT 0,

                is_read INTEGER DEFAULT 0,

                created_at INTEGER DEFAULT 0
            );


            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                actor_phone TEXT DEFAULT '',

                actor_role TEXT DEFAULT '',

                action TEXT NOT NULL,

                entity_type TEXT DEFAULT '',

                entity_id INTEGER DEFAULT 0,

                details TEXT DEFAULT '',

                created_at INTEGER DEFAULT 0
            );
            """
        )

        # ====================================================
        # הגדרות ברירת מחדל
        # ====================================================

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
                    str(value),
                )
            )


        # ====================================================
        # כינויים מובנים לערים
        # ====================================================

        for alias, city_name in DEFAULT_CITY_ALIASES.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO cities (
                    name,
                    is_active,
                    created_by,
                    created_at,
                    updated_at
                )
                VALUES (?, 1, ?, ?, ?)
                """,
                (
                    city_name,
                    "system",
                    now_ts(),
                    now_ts(),
                )
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO city_aliases (
                    city_name,
                    alias,
                    created_by,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (                    city_name,
                    alias,
                    "system",
                    now_ts(),
                )
            )

        # ====================================================
        # יצירת המנהל הראשי
        # ====================================================

        if ADMIN_PHONE:
            conn.execute(
                """
                INSERT INTO users (
                    phone,
                    role,
                    status,
                    full_name,
                    created_at,
                    approved_at,
                    approved_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(phone)
                DO UPDATE SET
                    role = excluded.role,
                    status = excluded.status
                """,
                (
                    ADMIN_PHONE,
                    ROLE_ADMIN,
                    USER_APPROVED,
                    "מנהל",
                    now_ts(),
                    now_ts(),
                    ADMIN_PHONE,
                )
            )

        subscription_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(subscriptions)"
            ).fetchall()
        }

        if "updated_at" not in subscription_columns:
            conn.execute(
                """
                ALTER TABLE subscriptions
                ADD COLUMN updated_at INTEGER DEFAULT 0
                """
            )        
        user_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "last_inbound_at" not in user_columns:
            conn.execute(
                """
                ALTER TABLE users
                ADD COLUMN last_inbound_at INTEGER DEFAULT 0
                """
            )        
        
        driver_profile_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(driver_profiles)"
            ).fetchall()
        }

        if "available_at" not in driver_profile_columns:
            conn.execute(
                """
                ALTER TABLE driver_profiles
                ADD COLUMN available_at INTEGER DEFAULT 0
                """
            )

        if "availability_reminder_sent" not in driver_profile_columns:
            conn.execute(
                """
                ALTER TABLE driver_profiles
                ADD COLUMN availability_reminder_sent INTEGER DEFAULT 0
                """
            )        
        
        conn.commit()


# ============================================================
# יצירת הטבלאות בעליית השרת
# ============================================================

init_db()


# ============================================================
# הגדרות מערכת
# ============================================================

def get_setting(
    key,
    default=""
):
    with db() as conn:
        row = conn.execute(
            """
            SELECT value
            FROM settings
            WHERE key = ?
            """,
            (
                key,
            )
        ).fetchone()

    if not row:
        return str(
            default
        )

    return str(
        row["value"]
    )


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
                value = excluded.value
            """,
            (
                key,
                str(value),
            )
        )

        conn.commit()


def setting_enabled(
    key,
    default="0"
):
    return (
        get_setting(
            key,
            default
        )
        == "1"
    )


# ============================================================
# Sessions
# ============================================================

def get_session(phone):
    phone = normalize_phone(
        phone
    )

    with db() as conn:
        row = conn.execute(
            """
            SELECT
                state,
                data
            FROM sessions
            WHERE phone = ?
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

    try:
        data = json.loads(
            row["data"]
            or "{}"
        )

    except Exception:
        data = {}

    if not isinstance(
        data,
        dict
    ):
        data = {}

    return {
        "state":
            row["state"]
            or "",

        "data":
            data,
    }


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
                state = excluded.state,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                phone,
                state or "",
                json.dumps(
                    data,
                    ensure_ascii=False
                ),
                now_ts(),
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
            WHERE phone = ?
            """,
            (
                phone,
            )
        )

        conn.commit()


# ============================================================
# משתמשים
# ============================================================

def get_user(phone):
    phone = normalize_phone(
        phone
    )

    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (
                phone,
            )
        ).fetchone()


def get_user_by_id(user_id):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            )
        ).fetchone()


def get_user_role(phone):
    user = get_user(
        phone
    )

    if not user:
        return ""

    return (
        user["role"]
        or ""
    )


def is_admin(phone):
    phone = normalize_phone(
        phone
    )

    if (
        ADMIN_PHONE
        and phone == ADMIN_PHONE
    ):
        return True

    user = get_user(
        phone
    )

    return bool(
        user
        and user["role"] == ROLE_ADMIN
        and user["status"] == USER_APPROVED
    )


def is_dispatcher(phone):
    user = get_user(
        phone
    )

    return bool(
        user
        and user["role"] == ROLE_DISPATCHER
        and user["status"] == USER_APPROVED
    )


def is_driver(phone):
    user = get_user(
        phone
    )

    return bool(
        user
        and user["role"] == ROLE_DRIVER
        and user["status"] == USER_APPROVED
    )


def is_customer(phone):
    user = get_user(
        phone
    )

    return bool(
        user
        and user["role"] == ROLE_CUSTOMER
        and user["status"] == USER_APPROVED
    )


def is_blocked(phone):
    user = get_user(
        phone
    )

    return bool(
        user
        and user["status"] == USER_BLOCKED
    )


# ============================================================
# ערים וכינויים
# ============================================================

def resolve_city(value):
    original = clean_text(
        value
    )

    if not original:
        return ""

    lookup = normalize_lookup_text(
        original
    )

    # קודם בודקים שם עיר רשמי
    with db() as conn:
        cities = conn.execute(
            """
            SELECT name
            FROM cities
            WHERE is_active = 1
            """
        ).fetchall()

        for city in cities:
            city_name = (
                city["name"]
                or ""
            )

            if (
                normalize_lookup_text(
                    city_name
                )
                == lookup
            ):
                return city_name

        # אחר כך כינויים
        aliases = conn.execute(
            """
            SELECT
                city_name,
                alias
            FROM city_aliases
            """
        ).fetchall()

        for row in aliases:
            if (
                normalize_lookup_text(
                    row["alias"]
                )
                == lookup
            ):
                return (
                    row["city_name"]
                    or original
                )

    # אם אין התאמה - לא ממציאים עיר אחרת
    return original


def add_city(
    city_name,
    actor_phone=""
):
    city_name = clean_text(
        city_name
    )

    if not city_name:
        return False

    with db() as conn:
        conn.execute(
            """
            INSERT INTO cities (
                name,
                is_active,
                created_by,
                created_at,
                updated_at
            )
            VALUES (?, 1, ?, ?, ?)

            ON CONFLICT(name)
            DO UPDATE SET
                is_active = 1,
                updated_at = excluded.updated_at
            """,
            (
                city_name,
                normalize_phone(
                    actor_phone
                ),
                now_ts(),
                now_ts(),
            )
        )

        conn.commit()

    return True


def add_city_alias(
    city_name,
    alias,
    actor_phone=""
):
    city_name = resolve_city(
        city_name
    )

    alias = clean_text(
        alias
    )

    if (
        not city_name
        or not alias
    ):
        return False

    add_city(
        city_name,
        actor_phone
    )

    with db() as conn:
        conn.execute(
            """
            INSERT INTO city_aliases (
                city_name,
                alias,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(alias)
            DO UPDATE SET
                city_name = excluded.city_name,
                created_by = excluded.created_by,
                created_at = excluded.created_at
            """,
            (
                city_name,
                alias,
                normalize_phone(
                    actor_phone
                ),
                now_ts(),
            )
        )

        conn.commit()

    return True


def delete_city_alias(alias):
    alias = clean_text(
        alias
    )

    with db() as conn:
        cursor = conn.execute(
            """
            DELETE FROM city_aliases
            WHERE alias = ?
            """,
            (
                alias,
            )
        )

        conn.commit()

        return (
            cursor.rowcount
            > 0
        )


# ============================================================
# מחירון
# ============================================================

def canonical_route(
    city_from,
    city_to
):
    city_from = resolve_city(
        city_from
    )

    city_to = resolve_city(
        city_to
    )

    if (
        not city_from
        or not city_to
    ):
        return (
            "",
            "",
        )

    # כך אותו מסלול נשמר פעם אחת בלבד,
    # בלי קשר לכיוון הנסיעה.
    ordered = sorted(
        [
            city_from,
            city_to,
        ],
        key=lambda value:
            normalize_lookup_text(
                value
            )
    )

    return (
        ordered[0],
        ordered[1],
    )


def get_route_price(
    city_from,
    city_to
):
    city_a, city_b = canonical_route(
        city_from,
        city_to
    )

    if (
        not city_a
        or not city_b
    ):
        return None

    with db() as conn:
        row = conn.execute(
            """
            SELECT price
            FROM route_prices
            WHERE
                city_from = ?
                AND city_to = ?
            LIMIT 1
            """,
            (
                city_a,
                city_b,
            )
        ).fetchone()

    if not row:
        return None

    return int(
        row["price"]
    )


def set_route_price(
    city_from,
    city_to,
    price,
    actor_phone="",
    actor_role=""
):
    city_a, city_b = canonical_route(
        city_from,
        city_to
    )

    if (
        not city_a
        or not city_b
    ):
        raise ValueError(
            "חסרה עיר מוצא או עיר יעד"
        )

    if city_a == city_b:
        raise ValueError(
            "עיר המוצא והיעד לא יכולות להיות זהות"
        )

    price = int(
        price
    )

    if price <= 0:
        raise ValueError(
            "המחיר חייב להיות גדול מ-0"
        )

    actor_phone = normalize_phone(
        actor_phone
    )

    with db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM route_prices
            WHERE
                city_from = ?
                AND city_to = ?
            LIMIT 1
            """,
            (
                city_a,
                city_b,
            )
        ).fetchone()

        current_time = now_ts()

        if existing:
            old_price = int(
                existing["price"]
            )

            conn.execute(
                """
                UPDATE route_prices
                SET
                    price = ?,
                    updated_by = ?,
                    updated_by_role = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    price,
                    actor_phone,
                    actor_role,
                    current_time,
                    existing["id"],
                )
            )

            route_price_id = int(
                existing["id"]
            )

            history_action = "update"

        else:
            cursor = conn.execute(
                """
                INSERT INTO route_prices (
                    city_from,
                    city_to,
                    price,
                    created_by,
                    created_by_role,
                    created_at,
                    updated_by,
                    updated_by_role,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    city_a,
                    city_b,
                    price,
                    actor_phone,
                    actor_role,
                    current_time,
                    actor_phone,
                    actor_role,
                    current_time,
                )
            )

            route_price_id = int(
                cursor.lastrowid
            )

            old_price = 0
            history_action = "create"

        conn.execute(
            """
            INSERT INTO route_price_history (
                route_price_id,
                city_from,
                city_to,
                old_price,
                new_price,
                action,
                changed_by,
                changed_by_role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                route_price_id,
                city_a,
                city_b,
                old_price,
                price,
                history_action,
                actor_phone,
                actor_role,
                current_time,
            )
        )

        conn.commit()

    return {
        "city_from": city_a,
        "city_to": city_b,
        "price": price,
    }


def delete_route_price(
    city_from,
    city_to,
    actor_phone="",
    actor_role=""
):
    city_a, city_b = canonical_route(
        city_from,
        city_to
    )

    if (
        not city_a
        or not city_b
    ):
        return False

    actor_phone = normalize_phone(
        actor_phone
    )

    with db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM route_prices
            WHERE
                city_from = ?
                AND city_to = ?
            LIMIT 1
            """,
            (
                city_a,
                city_b,
            )
        ).fetchone()

        if not existing:
            return False

        conn.execute(
            """
            INSERT INTO route_price_history (
                route_price_id,
                city_from,
                city_to,
                old_price,
                new_price,
                action,
                changed_by,
                changed_by_role,
                created_at
            )
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                existing["id"],
                city_a,
                city_b,
                int(
                    existing["price"]
                ),
                "delete",
                actor_phone,
                actor_role,
                now_ts(),
            )
        )

        conn.execute(
            """
            DELETE FROM route_prices
            WHERE id = ?
            """,
            (
                existing["id"],
            )
        )

        conn.commit()

    return True


# ============================================================
# תוספת עזרת שליח
# ============================================================

def get_driver_help_extra(
    vehicle_type
):
    mapping = {
        VEHICLE_PRIVATE:
            "help_extra_private",

        VEHICLE_7_SEATS:
            "help_extra_7_seats",

        VEHICLE_SMALL_COMMERCIAL:
            "help_extra_small_commercial",

        VEHICLE_LARGE_COMMERCIAL:
            "help_extra_large_commercial",
    }

    setting_key = mapping.get(
        vehicle_type,
        "help_extra_private"
    )

    try:
        return int(
            get_setting(
                setting_key,
                "0"
            )
        )

    except Exception:
        return 0


def calculate_shipment_price(
    origin_city,
    destination_city,
    vehicle_type,
    driver_help=False
):
    route_price = get_route_price(
        origin_city,
        destination_city
    )

    if route_price is None:
        return None

    # get_route_price מחזירה sqlite3.Row
    base_price = int(
        route_price["price"]
    )

    help_extra = 0

    if driver_help:
        help_extra = get_driver_help_extra(
            vehicle_type
        )

    final_price = (
        base_price
        + int(help_extra)
    )

    return {
        "base_price": base_price,
        "help_extra": int(help_extra),
        "final_price": int(final_price),
    }

# ============================================================
# דירוג שליח
# ============================================================

def get_driver_rating(
    driver_user_id
):
    with db() as conn:
        profile = conn.execute(
            """
            SELECT
                rating_sum,
                rating_count,
                completed_shipments
            FROM driver_profiles
            WHERE user_id = ?
            """,
            (
                driver_user_id,
            )
        ).fetchone()

    if not profile:
        return {
            "average": 0.0,
            "count": 0,
            "completed": 0,
        }

    count = int(
        profile["rating_count"]
        or 0
    )

    rating_sum = int(
        profile["rating_sum"]
        or 0
    )

    average = 0.0

    if count > 0:
        average = round(
            rating_sum / count,
            1
        )

    return {
        "average":
            average,

        "count":
            count,

        "completed":
            int(
                profile["completed_shipments"]
                or 0
            ),
    }


# ============================================================
# Audit log
# ============================================================

def log_action(
    actor_phone,
    action,
    entity_type="",
    entity_id=0,
    details=""
):
    actor_phone = normalize_phone(
        actor_phone
    )

    actor_role = get_user_role(
        actor_phone
    )

    with db() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                actor_phone,
                actor_role,
                action,
                entity_type,
                entity_id,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor_phone,
                actor_role,
                action,
                entity_type,
                int(
                    entity_id
                    or 0
                ),
                str(
                    details
                    or ""
                ),
                now_ts(),
            )
        )

        conn.commit()


# ============================================================
# התראות מנהל
# ============================================================

def create_admin_notification(
    notification_type,
    title,
    message="",
    entity_type="",
    entity_id=0
):
    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO admin_notifications (
                notification_type,
                title,
                message,
                entity_type,
                entity_id,
                is_read,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                notification_type,
                title,
                message,
                entity_type,
                int(
                    entity_id
                    or 0
                ),
                now_ts(),
            )
        )

        conn.commit()

        return int(
            cursor.lastrowid
        )


# ============================================================
# בדיקות הרשאה ומצב מערכת
# ============================================================

def can_manage_prices(phone):
    return (
        is_admin(phone)
        or is_dispatcher(phone)
    )


def system_is_enabled():
    return setting_enabled(
        "system_enabled",
        "1"
    )


def driver_side_is_enabled():
    return setting_enabled(
        "driver_side_enabled",
        "0"
    )


def subscriptions_are_enabled():
    return setting_enabled(
        "subscriptions_enabled",
        "0"
    )


# ============================================================
# מנויים
# ============================================================

def get_active_subscription(user_id):
    current_time = now_ts()

    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE
                user_id = ?
                AND status = 'active'
                AND expires_at > ?
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            (
                user_id,
                current_time,
            )
        ).fetchone()


def user_has_active_subscription(phone):
    user = get_user(
        phone
    )

    if not user:
        return False

    # מנהל וסדרן פטורים ממנוי
    if user["role"] in (
        ROLE_ADMIN,
        ROLE_DISPATCHER,
    ):
        return True

    # אם מערכת המנויים כבויה,
    # אין צורך במנוי פעיל.
    if not subscriptions_are_enabled():
        return True

    if user["role"] != ROLE_DRIVER:
        return True

    subscription = get_active_subscription(
        user["id"]
    )

    return bool(
        subscription
    )


def create_subscription(
    user_id,
    payment_id=None,
    days=None
):
    if days is None:
        try:
            days = int(
                get_setting(
                    "subscription_days",
                    "30"
                )
            )
        except Exception:
            days = 30

    start_at = now_ts()

    expires_at = int(
        (
            datetime.now()
            + timedelta(
                days=days
            )
        ).timestamp()
    )

    with db() as conn:
        # מבטלים מנויים פעילים ישנים
        conn.execute(
            """
            UPDATE subscriptions
            SET status = 'replaced'
            WHERE
                user_id = ?
                AND status = 'active'
            """,
            (
                user_id,
            )
        )

        cursor = conn.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                status,
                start_at,
                expires_at,
                payment_id,
                reminder_sent,
                created_at
            )
            VALUES (?, 'active', ?, ?, ?, 0, ?)
            """,
            (
                user_id,
                start_at,
                expires_at,
                payment_id,
                now_ts(),
            )
        )

        conn.commit()

        return int(
            cursor.lastrowid
        )


def get_subscription_status_text(phone):
    user = get_user(
        phone
    )

    if not user:
        return "לא נמצא משתמש"

    if user["role"] in (
        ROLE_ADMIN,
        ROLE_DISPATCHER,
    ):
        return "פטור ממנוי"

    if not subscriptions_are_enabled():
        return "מערכת המנויים כבויה"

    subscription = get_active_subscription(
        user["id"]
    )

    if not subscription:
        return "אין מנוי פעיל"

    expires_at = datetime.fromtimestamp(
        int(
            subscription["expires_at"]
        )
    )

    return (
        "מנוי פעיל עד "
        + expires_at.strftime(
            "%d/%m/%Y %H:%M"
        )
    )


# ============================================================
# פרופיל שליח
# ============================================================

def get_driver_profile(user_id):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM driver_profiles
            WHERE user_id = ?
            """,
            (
                user_id,
            )
        ).fetchone()


def create_or_update_driver_profile(
    user_id,
    vehicle_type="",
    vehicle_year="",
    vehicle_description="",
    id_photo_media_id="",
    selfie_media_id=""
):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO driver_profiles (
                user_id,
                vehicle_type,
                vehicle_year,
                vehicle_description,
                id_photo_media_id,
                selfie_media_id
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                vehicle_type =
                    excluded.vehicle_type,

                vehicle_year =
                    excluded.vehicle_year,

                vehicle_description =
                    excluded.vehicle_description,

                id_photo_media_id =
                    CASE
                        WHEN excluded.id_photo_media_id != ''
                        THEN excluded.id_photo_media_id
                        ELSE driver_profiles.id_photo_media_id
                    END,

                selfie_media_id =
                    CASE
                        WHEN excluded.selfie_media_id != ''
                        THEN excluded.selfie_media_id
                        ELSE driver_profiles.selfie_media_id
                    END
            """,
            (
                user_id,
                vehicle_type,
                vehicle_year,
                vehicle_description,
                id_photo_media_id,
                selfie_media_id,
            )
        )

        conn.commit()


def set_driver_available(
    user_id,
    is_available,
    city=""
):
    city = resolve_city(
        city
    )

    with db() as conn:
        conn.execute(
            """
            UPDATE driver_profiles
            SET
                is_available = ?,
                available_city = ?,
                available_at = ?,
                availability_reminder_sent = 0
            WHERE user_id = ?
            """,
            (
                1 if is_available else 0,
                city if is_available else "",
                now_ts() if is_available else 0,
                user_id,
            )
        )

        conn.commit()

def maintain_driver_availability():
    current_time = now_ts()

    reminder_after = 11 * 60 * 60
    expire_after = 12 * 60 * 60

    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                d.user_id,
                d.available_city,
                d.available_at,
                d.availability_reminder_sent,
                u.phone
            FROM driver_profiles d
            JOIN users u
                ON u.id = d.user_id
            WHERE
                d.is_available = 1
                AND d.available_at > 0
                AND u.status = ?
            """,
            (
                USER_APPROVED,
            )
        ).fetchall()

    for row in rows:
        elapsed = (
            current_time
            - int(row["available_at"] or 0)
        )

        # אחרי 12 שעות - הזמינות מתאפסת
        if elapsed >= expire_after:
            set_driver_available(
                row["user_id"],
                False,
                ""
            )
            continue

        # אחרי 11 שעות - תזכורת חד-פעמית
        if (
            elapsed >= reminder_after
            and not int(
                row["availability_reminder_sent"]
                or 0
            )
        ):
            send_message(
                row["phone"],
                (
                    "⏰ הזמינות שלך עומדת להסתיים בעוד שעה.\n\n"
                    f"📍 אזור נוכחי: {row['available_city']}\n\n"
                    "אם אתה עדיין פנוי, שלח שוב:\n"
                    f"פ {row['available_city']}"
                )
            )

            with db() as conn:
                conn.execute(
                    """
                    UPDATE driver_profiles
                    SET availability_reminder_sent = 1
                    WHERE user_id = ?
                    """,
                    (
                        row["user_id"],
                    )
                )
                conn.commit()

    return True

# ============================================================
# יצירה / עדכון משתמש
# ============================================================

def create_or_update_user(
    phone,
    role,
    status=USER_PENDING,
    full_name="",
    business_name="",
    city=""
):
    phone = normalize_phone(
        phone
    )

    full_name = clean_text(
        full_name
    )

    business_name = clean_text(
        business_name
    )

    city = resolve_city(
        city
    )

    with db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (
                phone,
            )
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE users
                SET
                    role = ?,
                    status = ?,
                    full_name = ?,
                    business_name = ?,
                    city = ?
                WHERE phone = ?
                """,
                (
                    role,
                    status,
                    full_name,
                    business_name,
                    city,
                    phone,
                )
            )

            user_id = int(
                existing["id"]
            )

        else:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    phone,
                    role,
                    status,
                    full_name,
                    business_name,
                    city,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    phone,
                    role,
                    status,
                    full_name,
                    business_name,
                    city,
                    now_ts(),
                )
            )

            user_id = int(
                cursor.lastrowid
            )

        conn.commit()

    return user_id


# ============================================================
# אישור משתמש
# ============================================================

def approve_user(
    user_id,
    admin_phone
):
    admin_phone = normalize_phone(
        admin_phone
    )

    with db() as conn:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            )
        ).fetchone()

        if not user:
            return False

        conn.execute(
            """
            UPDATE users
            SET
                status = ?,
                approved_at = ?,
                approved_by = ?,
                rejected_at = 0,
                rejected_by = ''
            WHERE id = ?
            """,
            (
                USER_APPROVED,
                now_ts(),
                admin_phone,
                user_id,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "APPROVE_USER",
        "user",
        user_id,
        f"role={user['role']}"
    )

    return True


# ============================================================
# דחיית משתמש
# ============================================================

def reject_user(
    user_id,
    admin_phone
):
    admin_phone = normalize_phone(
        admin_phone
    )

    with db() as conn:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            )
        ).fetchone()

        if not user:
            return False

        conn.execute(
            """
            UPDATE users
            SET
                status = ?,
                rejected_at = ?,
                rejected_by = ?
            WHERE id = ?
            """,
            (
                USER_REJECTED,
                now_ts(),
                admin_phone,
                user_id,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "REJECT_USER",
        "user",
        user_id,
        f"role={user['role']}"
    )

    return True


# ============================================================
# חסימת משתמש
# ============================================================

def block_user(
    phone,
    admin_phone,
    reason=""
):
    phone = normalize_phone(
        phone
    )

    admin_phone = normalize_phone(
        admin_phone
    )

    with db() as conn:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (
                phone,
            )
        ).fetchone()

        if not user:
            return False

        if user["role"] == ROLE_ADMIN:
            return False

        conn.execute(
            """
            UPDATE users
            SET
                status = ?,
                blocked_at = ?,
                blocked_by = ?,
                block_reason = ?
            WHERE phone = ?
            """,
            (
                USER_BLOCKED,
                now_ts(),
                admin_phone,
                clean_text(
                    reason
                ),
                phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "BLOCK_USER",
        "user",
        user["id"],
        reason
    )

    return True


# ============================================================
# הסרת חסימה
# ============================================================

def unblock_user(
    phone,
    admin_phone
):
    phone = normalize_phone(
        phone
    )

    admin_phone = normalize_phone(
        admin_phone
    )

    with db() as conn:
        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE phone = ?
            """,
            (
                phone,
            )
        ).fetchone()

        if not user:
            return False

        conn.execute(
            """
            UPDATE users
            SET
                status = ?,
                blocked_at = 0,
                blocked_by = '',
                block_reason = ''
            WHERE phone = ?
            """,
            (
                USER_APPROVED,
                phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "UNBLOCK_USER",
        "user",
        user["id"],
        ""
    )

    return True


# ============================================================
# סדרנים
# ============================================================

def make_dispatcher(
    phone,
    admin_phone
):
    phone = normalize_phone(
        phone
    )

    admin_phone = normalize_phone(
        admin_phone
    )

    user = get_user(
        phone
    )

    if user:
        with db() as conn:
            conn.execute(
                """
                UPDATE users
                SET
                    role = ?,
                    status = ?,
                    approved_at = ?,
                    approved_by = ?
                WHERE phone = ?
                """,
                (
                    ROLE_DISPATCHER,
                    USER_APPROVED,
                    now_ts(),
                    admin_phone,
                    phone,
                )
            )

            conn.commit()

        user_id = int(
            user["id"]
        )

    else:
        user_id = create_or_update_user(
            phone=phone,
            role=ROLE_DISPATCHER,
            status=USER_APPROVED
        )

        with db() as conn:
            conn.execute(
                """
                UPDATE users
                SET
                    approved_at = ?,
                    approved_by = ?
                WHERE id = ?
                """,
                (
                    now_ts(),
                    admin_phone,
                    user_id,
                )
            )

            conn.commit()

    log_action(
        admin_phone,
        "ADD_DISPATCHER",
        "user",
        user_id,
        phone
    )

    return user_id


def remove_dispatcher(
    phone,
    admin_phone
):
    phone = normalize_phone(
        phone
    )

    admin_phone = normalize_phone(
        admin_phone
    )

    user = get_user(
        phone
    )

    if (
        not user
        or user["role"] != ROLE_DISPATCHER
    ):
        return False

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET role = ?
            WHERE phone = ?
            """,
            (
                ROLE_CUSTOMER,
                phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "REMOVE_DISPATCHER",
        "user",
        user["id"],
        phone
    )

    return True


# ============================================================
# כותרת משלוח
# ============================================================

def shipment_title(shipment):
    business_name = clean_text(
        shipment["business_name"]
        if shipment
        else ""
    )

    if business_name:
        return (
            "📦 משלוח – "
            + business_name
        )

    return "📦 משלוח"


# ============================================================
# משלוחים - שליפה
# ============================================================

def get_shipment(shipment_id):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE id = ?
            """,
            (
                shipment_id,
            )
        ).fetchone()


def get_shipment_publisher(
    shipment_id
):
    with db() as conn:
        return conn.execute(
            """
            SELECT u.*
            FROM shipments s

            JOIN users u
                ON u.id = s.publisher_id

            WHERE s.id = ?
            """,
            (
                shipment_id,
            )
        ).fetchone()


def get_shipment_driver(
    shipment_id
):
    with db() as conn:
        return conn.execute(
            """
            SELECT
                u.*,
                d.vehicle_type,
                d.vehicle_year,
                d.vehicle_description,
                d.completed_shipments,
                d.rating_sum,
                d.rating_count
            FROM shipments s

            JOIN users u
                ON u.id = s.assigned_driver_id

            LEFT JOIN driver_profiles d
                ON d.user_id = u.id

            WHERE s.id = ?
            """,
            (
                shipment_id,
            )
        ).fetchone()


# ============================================================
# יצירת משלוח
# ============================================================

def create_shipment(
    publisher_id,
    origin_city,
    destination_city,
    pickup_address,
    dropoff_address,
    pickup_time,
    vehicle_type,
    driver_help,
    notes=""
):
    publisher = get_user_by_id(
        publisher_id
    )

    if not publisher:
        raise ValueError(
            "המפרסם לא נמצא"
        )

    origin_city = resolve_city(
        origin_city
    )

    destination_city = resolve_city(
        destination_city
    )

    price_data = calculate_shipment_price(
        origin_city,
        destination_city,
        vehicle_type,
        bool(
            driver_help
        )
    )

    if price_data is None:
        status = SHIP_NEEDS_PRICE

        base_price = 0
        help_extra = 0
        final_price = 0

    else:
        status = SHIP_NEW

        base_price = int(
            price_data["base_price"]
        )

        help_extra = int(
            price_data["help_extra"]
        )

        final_price = int(
            price_data["final_price"]
        )

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO shipments (
                publisher_id,
                business_name,
                status,
                origin_city,
                destination_city,
                pickup_address,
                dropoff_address,
                pickup_time,
                vehicle_type,
                driver_help,
                base_price,
                help_extra,
                final_price,
                notes,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                publisher_id,
                publisher["business_name"]
                or publisher["full_name"]
                or "",

                status,

                origin_city,
                destination_city,

                clean_text(
                    pickup_address
                ),

                clean_text(
                    dropoff_address
                ),

                clean_text(
                    pickup_time
                )
                or "עכשיו",

                vehicle_type,

                1 if driver_help else 0,

                base_price,
                help_extra,
                final_price,

                clean_text(
                    notes
                ),

                now_ts(),
                now_ts(),
            )
        )

        shipment_id = int(
            cursor.lastrowid
        )

        conn.execute(
            """
            INSERT INTO shipment_status_log (
                shipment_id,
                status,
                changed_by,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                status,
                publisher["phone"],
                "יצירת משלוח",
                now_ts(),
            )
        )

        conn.commit()

    if status == SHIP_NEEDS_PRICE:
        create_admin_notification(
            "shipment_needs_price",
            "💰 משלוח ללא מחיר",
            (
                f"{shipment_title(get_shipment(shipment_id))}\n"
                f"{origin_city} ↔ {destination_city}"
            ),
            "shipment",
            shipment_id
        )

    else:
        create_admin_notification(
            "new_shipment",
            "📦 משלוח חדש",
            (
                f"{shipment_title(get_shipment(shipment_id))}\n"
                f"{origin_city} ↔ {destination_city}\n"
                f"מחיר: {final_price} ₪"
            ),
            "shipment",
            shipment_id
        )

    return shipment_id


# ============================================================
# התעניינות שליח במשלוח
# ============================================================

def add_driver_interest(
    shipment_id,
    driver_id,
    eta_text
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        return False

    with db() as conn:
        conn.execute(
            """
            INSERT INTO shipment_interests (
                shipment_id,
                driver_id,
                eta_text,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(shipment_id, driver_id)
            DO UPDATE SET
                eta_text = excluded.eta_text,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                shipment_id,
                driver_id,
                clean_text(eta_text),
                INTEREST_PENDING,
                now_ts(),
                now_ts(),
            )
        )

        conn.commit()

    create_admin_notification(
        "driver_interest",
        "🙋 שליח מעוניין במשלוח",
        (
            f"שליח הביע עניין ב-"
            f"{shipment_title(shipment)}"
        ),
        "shipment",
        shipment_id
    )

    return True


# ============================================================
# רשימת מתעניינים במשלוח
# ============================================================

def get_shipment_interests(shipment_id):
    with db() as conn:
        return conn.execute(
            """
            SELECT
                i.*,
                u.phone,
                u.full_name,
                u.city,
                d.vehicle_type,
                d.vehicle_year,
                d.vehicle_description,
                d.completed_shipments,
                d.cancelled_after_assignment,
                d.rating_sum,
                d.rating_count
            FROM shipment_interests i

            JOIN users u
                ON u.id = i.driver_id

            LEFT JOIN driver_profiles d
                ON d.user_id = i.driver_id

            WHERE
                i.shipment_id = ?
                AND i.status = ?

            ORDER BY i.created_at ASC
            """,
            (
                shipment_id,
                INTEREST_PENDING,
            )
        ).fetchall()


# ============================================================
# בחירת שליח למשלוח
# ============================================================

def assign_driver_to_shipment(
    shipment_id,
    driver_id,
    actor_phone
):
    actor_phone = normalize_phone(
        actor_phone
    )

    shipment = get_shipment(
        shipment_id
    )

    driver = get_user_by_id(
        driver_id
    )

    if not shipment:
        raise ValueError(
            "המשלוח לא נמצא"
        )

    if not driver:
        raise ValueError(
            "השליח לא נמצא"
        )

    if driver["role"] not in (
        ROLE_DRIVER,
        ROLE_DISPATCHER,
    ):
        raise ValueError(
            "המשתמש אינו שליח"
        )

    if driver["status"] != USER_APPROVED:
        raise ValueError(
            "השליח אינו מאושר"
        )

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        raise ValueError(
            "המשלוח כבר אינו זמין לשיבוץ"
        )

    with db() as conn:
        conn.execute(
            """
            UPDATE shipments
            SET
                assigned_driver_id = ?,
                assigned_at = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                driver_id,
                now_ts(),
                SHIP_ASSIGNED,
                now_ts(),
                shipment_id,
            )
        )

        conn.execute(
            """
            UPDATE shipment_interests
            SET
                status = CASE
                    WHEN driver_id = ?
                    THEN ?
                    ELSE ?
                END,
                updated_at = ?
            WHERE shipment_id = ?
            """,
            (
                driver_id,
                INTEREST_SELECTED,
                INTEREST_REJECTED,
                now_ts(),
                shipment_id,
            )
        )

        conn.execute(
            """
            INSERT INTO shipment_status_log (
                shipment_id,
                status,
                changed_by,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                SHIP_ASSIGNED,
                actor_phone,
                (
                    "המשלוח שובץ לשליח "
                    + (
                        driver["full_name"]
                        or driver["phone"]
                    )
                ),
                now_ts(),
            )
        )

        conn.commit()

    log_action(
        actor_phone,
        "ASSIGN_DRIVER",
        "shipment",
        shipment_id,
        (
            f"driver_id={driver_id}; "
            f"driver_phone={driver['phone']}"
        )
    )

    create_admin_notification(
        "shipment_assigned",
        "🚚 משלוח שובץ לשליח",
        (
            f"{shipment_title(shipment)}\n"
            f"שליח: "
            f"{driver['full_name'] or driver['phone']}"
        ),
        "shipment",
        shipment_id
    )

    return True


# ============================================================
# סיום משלוח
# ============================================================

def complete_shipment(
    shipment_id,
    actor_phone
):
    actor_phone = normalize_phone(
        actor_phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if shipment["status"] == SHIP_COMPLETED:
        return True

    if shipment["status"] != SHIP_ASSIGNED:
        return False

    driver_id = shipment[
        "assigned_driver_id"
    ]

    if not driver_id:
        return False

    with db() as conn:
        conn.execute(
            """
            UPDATE shipments
            SET
                status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                SHIP_COMPLETED,
                now_ts(),
                now_ts(),
                shipment_id,
            )
        )

        conn.execute(
            """
            UPDATE driver_profiles
            SET
                completed_shipments =
                    completed_shipments + 1
            WHERE user_id = ?
            """,
            (
                driver_id,
            )
        )

        conn.execute(
            """
            INSERT INTO shipment_status_log (
                shipment_id,
                status,
                changed_by,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                SHIP_COMPLETED,
                actor_phone,
                "המשלוח הושלם",
                now_ts(),
            )
        )

        conn.commit()

    log_action(
        actor_phone,
        "COMPLETE_SHIPMENT",
        "shipment",
        shipment_id,
        ""
    )

    return True


# ============================================================
# דירוג שליח
# רק מפרסם המשלוח יכול לדרג
# וכל משלוח ניתן לדירוג פעם אחת בלבד
# ============================================================

def rate_shipment_driver(
    shipment_id,
    publisher_phone,
    rating
):
    publisher_phone = normalize_phone(
        publisher_phone
    )

    try:
        rating = int(
            rating
        )
    except Exception:
        raise ValueError(
            "דירוג לא תקין"
        )

    if rating < 1 or rating > 5:
        raise ValueError(
            "הדירוג חייב להיות בין 1 ל-5"
        )

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        raise ValueError(
            "המשלוח לא נמצא"
        )

    publisher = get_user_by_id(
        shipment["publisher_id"]
    )

    if not publisher:
        raise ValueError(
            "המפרסם לא נמצא"
        )

    if (
        normalize_phone(
            publisher["phone"]
        )
        != publisher_phone
    ):
        raise ValueError(
            "אין הרשאה לדרג משלוח זה"
        )

    if shipment["status"] != SHIP_COMPLETED:
        raise ValueError(
            "אפשר לדרג רק לאחר סיום המשלוח"
        )

    driver_id = shipment[
        "assigned_driver_id"
    ]

    if not driver_id:
        raise ValueError(
            "לא שובץ שליח למשלוח"
        )

    with db() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM ratings
            WHERE shipment_id = ?
            """,
            (
                shipment_id,
            )
        ).fetchone()

        if existing:
            raise ValueError(
                "השליח כבר דורג עבור משלוח זה"
            )

        conn.execute(
            """
            INSERT INTO ratings (
                shipment_id,
                publisher_id,
                driver_id,
                rating,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                shipment["publisher_id"],
                driver_id,
                rating,
                now_ts(),
            )
        )

        conn.execute(
            """
            UPDATE shipments
            SET
                rating = ?,
                rated_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                rating,
                now_ts(),
                now_ts(),
                shipment_id,
            )
        )

        conn.execute(
            """
            UPDATE driver_profiles
            SET
                rating_sum = rating_sum + ?,
                rating_count = rating_count + 1
            WHERE user_id = ?
            """,
            (
                rating,
                driver_id,
            )
        )

        conn.commit()

    return True


# ============================================================
# ביטול משלוח
# ============================================================

def cancel_shipment(
    shipment_id,
    actor_phone,
    reason=""
):
    actor_phone = normalize_phone(
        actor_phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if shipment["status"] in (
        SHIP_COMPLETED,
        SHIP_CANCELLED,
    ):
        return False

    assigned_driver_id = shipment[
        "assigned_driver_id"
    ]

    with db() as conn:
        conn.execute(
            """
            UPDATE shipments
            SET
                status = ?,
                cancelled_at = ?,
                cancellation_reason = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                SHIP_CANCELLED,
                now_ts(),
                clean_text(
                    reason
                ),
                now_ts(),
                shipment_id,
            )
        )

        conn.execute(
            """
            INSERT INTO shipment_status_log (
                shipment_id,
                status,
                changed_by,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                shipment_id,
                SHIP_CANCELLED,
                actor_phone,
                clean_text(
                    reason
                ),
                now_ts(),
            )
        )

        conn.commit()

    log_action(
        actor_phone,
        "CANCEL_SHIPMENT",
        "shipment",
        shipment_id,
        reason
    )

    if assigned_driver_id:
        create_admin_notification(
            "assigned_shipment_cancelled",
            "⚠️ משלוח משובץ בוטל",
            shipment_title(
                shipment
            ),
            "shipment",
            shipment_id
        )

    return True


# ============================================================
# פנייה לנציג
# ============================================================

def create_support_request(
    phone,
    category,
    message="",
    shipment_id=None
):
    phone = normalize_phone(
        phone
    )

    user = get_user(
        phone
    )

    user_id = (
        user["id"]
        if user
        else None
    )

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO support_requests (
                user_id,
                phone,
                shipment_id,
                category,
                message,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                phone,
                shipment_id,
                clean_text(
                    category
                ),
                clean_text(
                    message
                ),
                SUPPORT_OPEN,
                now_ts(),
            )
        )

        request_id = int(
            cursor.lastrowid
        )

        conn.commit()

    create_admin_notification(
        "support_request",
        "💬 פנייה חדשה לנציג",
        (
            f"טלפון: {phone}\n"
            f"נושא: {category}"
        ),
        "support",
        request_id
    )

    if ADMIN_PHONE:
        send_message(
            ADMIN_PHONE,
            (
                "💬 *פנייה חדשה לנציג*\n\n"
                f"📱 טלפון: {phone}\n"
                f"📌 נושא: {category}\n\n"
                f"📝 הודעה:\n{message}"
            )
        )    

    return request_id


# ============================================================
# סוף חלק 1
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 2A
# WhatsApp + הודעות + כפתורים + רשימות + מדיה
# ============================================================


# ============================================================
# כתובת WhatsApp Graph API
# ============================================================

def whatsapp_messages_url():
    return (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{PHONE_NUMBER_ID}/messages"
    )


def whatsapp_media_url(media_id):
    return (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{media_id}"
    )


# ============================================================
# Headers
# ============================================================

def whatsapp_headers():
    return {
        "Authorization":
            f"Bearer {WHATSAPP_TOKEN}",

        "Content-Type":
            "application/json",
    }


# ============================================================
# שליחת Payload ל-WhatsApp
# ============================================================

def send_whatsapp_payload(payload):
    if not WHATSAPP_TOKEN:
        print(
            "WHATSAPP ERROR: "
            "WHATSAPP_TOKEN is missing"
        )
        return None

    if not PHONE_NUMBER_ID:
        print(
            "WHATSAPP ERROR: "
            "PHONE_NUMBER_ID is missing"
        )
        return None

    try:
        response = requests.post(
            whatsapp_messages_url(),
            headers=whatsapp_headers(),
            json=payload,
            timeout=30
        )

        if not response.ok:
            print(
                "WHATSAPP SEND ERROR:",
                response.status_code,
                response.text
            )

            return None

        try:
            return response.json()

        except Exception:
            return {
                "ok": True,
                "text": response.text,
            }

    except Exception as exc:
        print(
            "WHATSAPP REQUEST ERROR:",
            repr(exc)
        )

        return None


# ============================================================
# הודעת טקסט
# ============================================================

def send_message(
    phone,
    text
):
    phone = normalize_phone(
        phone
    )

    text = str(
        text
        or ""
    ).strip()

    if not phone:
        return None

    if not text:
        return None

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "text",

        "text": {
            "preview_url":
                False,

            "body":
                text,
        },
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# הודעת כפתורים
# עד 3 כפתורים בהודעה אחת
# ============================================================

def send_buttons(
    phone,
    body,
    buttons,
    header=None,
    footer=None
):
    phone = normalize_phone(
        phone
    )

    whatsapp_buttons = []

    for button in buttons[:3]:
        if len(button) < 2:
            continue

        button_id = str(
            button[0]
        )[:256]

        title = str(
            button[1]
        )[:20]

        whatsapp_buttons.append(
            {
                "type":
                    "reply",

                "reply": {
                    "id":
                        button_id,

                    "title":
                        title,
                },
            }
        )

    if not whatsapp_buttons:
        return send_message(
            phone,
            body
        )

    interactive = {
        "type":
            "button",

        "body": {
            "text":
                str(
                    body
                    or ""
                )[:1024]
        },

        "action": {
            "buttons":
                whatsapp_buttons
        },
    }

    if header:
        interactive["header"] = {
            "type":
                "text",

            "text":
                str(
                    header
                )[:60],
        }

    if footer:
        interactive["footer"] = {
            "text":
                str(
                    footer
                )[:60],
        }

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "interactive",

        "interactive":
            interactive,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# הודעת רשימה
#
# rows:
# [
#   ("id", "כותרת", "תיאור"),
#   ...
# ]
# ============================================================

def send_list(
    phone,
    title,
    body,
    rows,
    button_text="בחר",
    footer=None
):
    phone = normalize_phone(
        phone
    )

    list_rows = []

    for row in rows:
        if len(row) < 2:
            continue

        row_id = str(
            row[0]
        )[:200]

        row_title = str(
            row[1]
        )[:24]

        row_description = ""

        if len(row) >= 3:
            row_description = str(
                row[2]
                or ""
            )[:72]

        item = {
            "id":
                row_id,

            "title":
                row_title,
        }

        if row_description:
            item["description"] = (
                row_description
            )

        list_rows.append(
            item
        )

    if not list_rows:
        return send_message(
            phone,
            body
        )

    # WhatsApp מאפשר עד 10 שורות ברשימה.
    list_rows = list_rows[:10]

    interactive = {
        "type":
            "list",

        "header": {
            "type":
                "text",

            "text":
                str(
                    title
                    or "שליחובוט"
                )[:60],
        },

        "body": {
            "text":
                str(
                    body
                    or ""
                )[:1024],
        },

        "action": {
            "button":
                str(
                    button_text
                    or "בחר"
                )[:20],

            "sections": [
                {
                    "title":
                        "אפשרויות",

                    "rows":
                        list_rows,
                }
            ],
        },
    }

    if footer:
        interactive["footer"] = {
            "text":
                str(
                    footer
                )[:60],
        }

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "interactive",

        "interactive":
            interactive,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# רשימה עם כמה קטגוריות
# ============================================================

def send_section_list(
    phone,
    title,
    body,
    sections,
    button_text="בחר",
    footer=None
):
    phone = normalize_phone(
        phone
    )

    whatsapp_sections = []

    for section in sections:
        section_title = str(
            section.get(
                "title",
                "אפשרויות"
            )
        )[:24]

        section_rows = []

        for row in section.get(
            "rows",
            []
        ):
            if len(row) < 2:
                continue

            item = {
                "id":
                    str(
                        row[0]
                    )[:200],

                "title":
                    str(
                        row[1]
                    )[:24],
            }

            if (
                len(row) >= 3
                and row[2]
            ):
                item["description"] = str(
                    row[2]
                )[:72]

            section_rows.append(
                item
            )

        if section_rows:
            whatsapp_sections.append(
                {
                    "title":
                        section_title,

                    "rows":
                        section_rows,
                }
            )

    if not whatsapp_sections:
        return send_message(
            phone,
            body
        )

    interactive = {
        "type":
            "list",

        "header": {
            "type":
                "text",

            "text":
                str(
                    title
                    or "שליחובוט"
                )[:60],
        },

        "body": {
            "text":
                str(
                    body
                    or ""
                )[:1024],
        },

        "action": {
            "button":
                str(
                    button_text
                    or "בחר"
                )[:20],

            "sections":
                whatsapp_sections,
        },
    }

    if footer:
        interactive["footer"] = {
            "text":
                str(
                    footer
                )[:60],
        }

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "interactive",

        "interactive":
            interactive,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# שליחת תמונה לפי media_id
# ============================================================

def send_image_by_media_id(
    phone,
    media_id,
    caption=""
):
    phone = normalize_phone(
        phone
    )

    if not media_id:
        return None

    image_data = {
        "id":
            media_id
    }

    if caption:
        image_data["caption"] = str(
            caption
        )[:1024]

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "image",

        "image":
            image_data,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# שליחת מסמך לפי media_id
# ============================================================

def send_document_by_media_id(
    phone,
    media_id,
    filename="document",
    caption=""
):
    phone = normalize_phone(
        phone
    )

    if not media_id:
        return None

    document_data = {
        "id":
            media_id,

        "filename":
            filename,
    }

    if caption:
        document_data["caption"] = str(
            caption
        )[:1024]

    payload = {
        "messaging_product":
            "whatsapp",

        "recipient_type":
            "individual",

        "to":
            phone,

        "type":
            "document",

        "document":
            document_data,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# קבלת מידע על מדיה
# ============================================================

def get_media_info(media_id):
    if not media_id:
        return None

    try:
        response = requests.get(
            whatsapp_media_url(
                media_id
            ),
            headers={
                "Authorization":
                    f"Bearer {WHATSAPP_TOKEN}"
            },
            timeout=30
        )

        if not response.ok:
            print(
                "MEDIA INFO ERROR:",
                response.status_code,
                response.text
            )

            return None

        return response.json()

    except Exception as exc:
        print(
            "MEDIA INFO REQUEST ERROR:",
            repr(exc)
        )

        return None


# ============================================================
# הורדת מדיה
# ============================================================

def download_whatsapp_media(
    media_id
):
    info = get_media_info(
        media_id
    )

    if not info:
        return None

    media_download_url = info.get(
        "url"
    )

    if not media_download_url:
        return None

    try:
        response = requests.get(
            media_download_url,
            headers={
                "Authorization":
                    f"Bearer {WHATSAPP_TOKEN}"
            },
            timeout=30
        )

        if not response.ok:
            print(
                "MEDIA DOWNLOAD ERROR:",
                response.status_code,
                response.text
            )

            return None

        return {
            "content":
                response.content,

            "mime_type":
                info.get(
                    "mime_type",
                    ""
                ),

            "sha256":
                info.get(
                    "sha256",
                    ""
                ),

            "file_size":
                info.get(
                    "file_size",
                    0
                ),
        }

    except Exception as exc:
        print(
            "MEDIA DOWNLOAD REQUEST ERROR:",
            repr(exc)
        )

        return None


# ============================================================
# סימון הודעה כנקראה
# ============================================================

def mark_message_as_read(
    message_id
):
    if not message_id:
        return None

    payload = {
        "messaging_product":
            "whatsapp",

        "status":
            "read",

        "message_id":
            message_id,
    }

    return send_whatsapp_payload(
        payload
    )


# ============================================================
# פענוח הודעת WhatsApp נכנסת
# ============================================================

def parse_incoming_message(message):
    result = {
        "message_id":
            message.get(
                "id",
                ""
            ),

        "from":
            normalize_phone(
                message.get(
                    "from",
                    ""
                )
            ),

        "type":
            message.get(
                "type",
                ""
            ),

        "text":
            "",

        "action_id":
            "",

        "media_id":
            "",

        "latitude":
            None,

        "longitude":
            None,

        "raw":
            message,
    }

    message_type = result[
        "type"
    ]

    # --------------------------------------------------------
    # טקסט
    # --------------------------------------------------------

    if message_type == "text":
        result["text"] = (
            message
            .get(
                "text",
                {}
            )
            .get(
                "body",
                ""
            )
        )

    # --------------------------------------------------------
    # כפתור / רשימה
    # --------------------------------------------------------

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

            result["action_id"] = reply.get(
                "id",
                ""
            )

            result["text"] = reply.get(
                "title",
                ""
            )

        elif interactive_type == "list_reply":
            reply = interactive.get(
                "list_reply",
                {}
            )

            result["action_id"] = reply.get(
                "id",
                ""
            )

            result["text"] = reply.get(
                "title",
                ""
            )

    # --------------------------------------------------------
    # כפתור ישן
    # --------------------------------------------------------

    elif message_type == "button":
        button = message.get(
            "button",
            {}
        )

        result["action_id"] = button.get(
            "payload",
            ""
        )

        result["text"] = button.get(
            "text",
            ""
        )

    # --------------------------------------------------------
    # תמונה
    # --------------------------------------------------------

    elif message_type == "image":
        image = message.get(
            "image",
            {}
        )

        result["media_id"] = image.get(
            "id",
            ""
        )

        result["text"] = image.get(
            "caption",
            ""
        )

    # --------------------------------------------------------
    # מסמך
    # --------------------------------------------------------

    elif message_type == "document":
        document = message.get(
            "document",
            {}
        )

        result["media_id"] = document.get(
            "id",
            ""
        )

        result["text"] = document.get(
            "caption",
            ""
        )

    # --------------------------------------------------------
    # מיקום
    # --------------------------------------------------------

    elif message_type == "location":
        location = message.get(
            "location",
            {}
        )

        result["latitude"] = location.get(
            "latitude"
        )

        result["longitude"] = location.get(
            "longitude"
        )

        result["text"] = location.get(
            "name",
            ""
        )

    return result


# ============================================================
# שליפת הודעות מתוך webhook
# ============================================================

def extract_webhook_messages(payload):
    messages = []

    try:
        entries = payload.get(
            "entry",
            []
        )

        for entry in entries:
            changes = entry.get(
                "changes",
                []
            )

            for change in changes:
                value = change.get(
                    "value",
                    {}
                )

                for message in value.get(
                    "messages",
                    []
                ):
                    messages.append(
                        message
                    )

    except Exception as exc:
        print(
            "WEBHOOK PARSE ERROR:",
            repr(exc)
        )

    return messages


# ============================================================
# הודעת תחזוקה
# ============================================================

def send_maintenance_message(phone):
    send_message(
        phone,
        get_setting(
            "maintenance_message",
            (
                "🛠️ שליחובוט נמצא כרגע "
                "בתחזוקה."
            )
        )
    )


# ============================================================
# הודעת משתמש חסום
# ============================================================

def send_blocked_message(phone):
    send_message(
        phone,
        (
            "🚫 החשבון שלך חסום כרגע "
            "לשימוש בשליחובוט.\n\n"
            "לפרטים נוספים ניתן לפנות "
            "למנהל המערכת."
        )
    )


# ============================================================
# הודעת ממתין לאישור
# ============================================================

def send_pending_approval_message(
    phone,
    role
):
    if role == ROLE_DRIVER:
        text = (
            "⏳ בקשת ההרשמה שלך כשליח "
            "ממתינה לאישור מנהל.\n\n"
            "לאחר האישור נעדכן אותך כאן."
        )

    else:
        text = (
            "⏳ בקשת ההרשמה שלך "
            "ממתינה לאישור מנהל.\n\n"
            "לאחר האישור נעדכן אותך כאן."
        )

    send_message(
        phone,
        text
    )


# ============================================================
# תפריט כניסה למשתמש חדש
# ============================================================

def show_role_choice(phone):
    clear_session(
        phone
    )

    send_buttons(
        phone,
        (
            "👋 ברוכים הבאים לשליחובוט\n\n"
            "מערכת חכמה לפרסום וניהול "
            "משלוחים.\n\n"
            "איך תרצה להשתמש במערכת?"
        ),
        [
            (
                "register_customer",
                "📦 מפרסם"
            ),
            (
                "register_driver",
                "🚗 שליח"
            ),
        ],
        header="שליחובוט",
        footer="בחר את סוג החשבון"
    )


# ============================================================
# תפריט מפרסם
# ============================================================

def show_customer_menu(phone):
    user = get_user(
        phone
    )

    business_name = ""

    if user:
        business_name = (
            user["business_name"]
            or user["full_name"]
            or ""
        )

    title = "📦 תפריט מפרסם"

    if business_name:
        title = (
            f"📦 {business_name}"
        )

    send_list(
        phone,
        title,
        "בחר פעולה:",
        [
            (
                "customer_new_shipment",
                "📦 פרסום משלוח",
                "יצירת משלוח חדש",
            ),
        (
            "customer_guide",
            "📖 מדריך למפרסם",
            "הסבר קצר על השימוש בשליחובוט",
        ),            
            
            (
                "customer_support",
                "💬 פנייה לנציג",
                "עזרה ושירות",
            ),
        ],
        button_text="פתח תפריט",
        footer="שליחובוט"
    )

def show_customer_guide(phone):
    send_message(
        phone,
        (
            "📖 *מדריך למפרסם – שליחובוט*\n\n"

            "📦 *איך מפרסמים משלוח?*\n"
            "לחץ על „פרסום משלוח” ומלא את הפרטים שהמערכת מבקשת: "
            "עיר וכתובת איסוף, עיר וכתובת יעד, זמן איסוף, סוג רכב ופרטים נוספים. "
            "בסיום יוצג סיכום המשלוח לאישור.\n\n"

            "💰 *מחיר המשלוח*\n"
            "המחיר מחושב לפי המחירון הקיים במערכת ובהתאם לפרטי המשלוח. "
            "לפני הפרסום יוצג לך המחיר ותוכל לאשר את המשלוח.\n\n"

            "👤 *איך בוחרים שליח?*\n"
            "כאשר שליח מתעניין במשלוח שלך, תקבל הודעה אוטומטית "
            "עם פרטי השליח ואפשרות לבחור בו.\n\n"

            "🚚 *לאחר בחירת שליח*\n"
            "לאחר שבחרת שליח, המערכת מעדכנת אותו ומעבירה את "
            "הפרטים הדרושים לביצוע המשלוח.\n\n"

            "❌ *ביטול משלוח*\n"
            "כל עוד המשלוח עדיין לא שובץ לשליח, ניתן לבטל אותו "
            "דרך האפשרויות שמופיעות בהודעות המשלוח.\n\n"

            "⭐ *בסיום המשלוח*\n"
            "לאחר סיום המשלוח ניתן לדרג את השליח בהתאם לשירות שקיבלת.\n\n"

            "💬 *צריכים עזרה?*\n"
            "לחץ על „פנייה לנציג”, כתוב את הפנייה והיא תועבר "
            "ישירות למנהל המערכת.\n\n"

            "📌 *חשוב לדעת*\n"
            "יש להזין פרטי משלוח מדויקים ולוודא שהכתובות והפרטים "
            "נכונים לפני אישור הפרסום."
        )
    )
# ============================================================
# תפריט שליח
# ============================================================

def show_driver_menu(phone):
    user = get_user(
        phone
    )

    if not user:
        show_role_choice(
            phone
        )
        return

    subscription_text = (
        get_subscription_status_text(
            phone
        )
    )

    send_list(
        phone,
        "🚗 תפריט שליח",
        (
            f"שלום {user['full_name'] or ''} 👋\n"
            f"💎 {subscription_text}\n\n"
            "בחר פעולה:"
        ),
        [
            
            (
                "driver_available_shipments",
                "📦 משלוחים זמינים",
                "צפייה במשלוחים שניתן לקחת",
            ),
            (
                "driver_my_shipments",
                "🚚 המשלוחים שלי",
                "משלוחים ששובצו אליך",
            ),
            (
                "driver_subscription",
                "💎 המנוי שלי",
                "סטטוס וחידוש מנוי",
            ),
            (
                "driver_profile",
                "👤 הפרופיל שלי",
                "פרטי רכב ודירוג",
            ),
            (
                "driver_guide",
                "📖 מדריך לשליח",
                "איך עובדים עם שליחובוט",
            ),            
            (
                "driver_support",
                "💬 פנייה לנציג",
                "עזרה ושירות",
            ),
        ],
        button_text="פתח תפריט",
        footer="שליחובוט"
    )

# ============================================================
# מדריך לשליח
# ============================================================

def show_driver_guide(phone):
    part_1 = (
        "📖 *מדריך לשליח – שליחובוט*\n\n"
        "🚗 *ברוכים הבאים לשליחובוט*\n"
        "כאן תוכל ללמוד איך לעבוד עם המערכת, "
        "לקבל משלוחים ולהשתמש בשליחובוט בצורה נכונה.\n\n"

        "━━━━━━━━━━━━━━\n"
        "🟢 *רוצה לקבל משלוחים?*\n\n"
        "כדי לסמן שאתה פנוי, שלח לבוט:\n"
        "*פ ירושלים*\n\n"
        "או:\n"
        "*פנוי ירושלים*\n\n"
        "במקום ירושלים רשום את העיר שבה אתה פנוי כרגע.\n\n"
        "לדוגמה:\n"
        "• פ תל אביב\n"
        "• פ ראשון לציון\n"
        "• פ נתניה\n\n"
        "לאחר מכן תקבל אישור שסומנת כפנוי "
        "ואת אזור הזמינות שלך.\n\n"
        "⏰ הזמינות נשמרת למשך *12 שעות*.\n"
        "כשעה לפני סיום הזמינות תקבל תזכורת.\n"
        "אם אתה עדיין פנוי, שלח שוב *פ + שם העיר* "
        "והזמינות תתחדש לעוד 12 שעות.\n\n"
        "אם לא חידשת, לאחר 12 שעות המערכת "
        "תסמן אותך אוטומטית כלא פנוי.\n\n"

        "━━━━━━━━━━━━━━\n"
        "🔴 *סיימת לעבוד או שאתה תפוס?*\n\n"
        "שלח לבוט אחת מהאפשרויות:\n"
        "• *תפוס*\n"
        "• *לא פנוי*\n"
        "• *לא זמין*\n\n"
        "לאחר מכן לא יישלחו אליך משלוחים חדשים.\n"
        "כשתרצה לחזור לעבוד, שלח שוב *פ + שם העיר*."
    )

    part_2 = (
        "📖 *מדריך לשליח – חלק 2*\n\n"

        "📦 *איך מקבלים משלוחים?*\n\n"
        "כאשר אתה מסומן כפנוי ומתפרסם משלוח "
        "שמתאים לנתונים שלך, המערכת יכולה לשלוח לך אותו.\n\n"
        "אפשר גם להיכנס לתפריט ולבחור:\n"
        "*📦 משלוחים זמינים*\n\n"
        "בפרטי המשלוח תוכל לראות:\n"
        "📍 עיר מוצא ויעד\n"
        "🏠 כתובת איסוף ומסירה\n"
        "🕐 זמן האיסוף\n"
        "🚗 סוג הרכב הנדרש\n"
        "🧤 האם נדרשת עזרת שליח\n"
        "📝 הערות למשלוח\n"
        "💵 המחיר לשליח\n\n"

        "━━━━━━━━━━━━━━\n"
        "💰 *בלי עמלות ובלי אחוזים מהמשלוח*\n\n"
        "בשליחובוט אנחנו עובדים *ללא עמלה מכל משלוח*.\n\n"
        "המפרסם פרסם משלוח ב־300 ₪?\n"
        "ביצעת את המשלוח ב־300 ₪?\n"
        "*כל ה־300 ₪ הם שלך.*\n\n"
        "אין אצלנו ניכוי של 10%, 12% או אחוז אחר "
        "ממחיר המשלוח.\n\n"
        "🍓 *בלי תותים, בלי הפתעות ובלי קיזוזים מהמשלוח.*\n\n"
        "המחיר שמוצג לך הוא המחיר שאתה מקבל "
        "עבור ביצוע המשלוח – *נטו לשליח*.\n\n"

        "━━━━━━━━━━━━━━\n"
        "🙋 *המשלוח מתאים לך?*\n\n"
        "לחץ על *🙋 מעוניין*.\n"
        "לאחר מכן בחר תוך כמה זמן תוכל להגיע:\n"
        "• 15 דקות\n"
        "• 30 דקות\n"
        "• זמן אחר\n\n"
        "אם בחרת זמן אחר, כתוב את זמן ההגעה שלך.\n\n"
        "⚠️ לחיצה על *מעוניין* לא אומרת שהמשלוח שלך.\n"
        "המפרסם או הסדרן בוחר את השליח המתאים "
        "מבין השליחים שהתעניינו."
    )

    part_3 = (
        "📖 *מדריך לשליח – חלק 3*\n\n"

        "🎉 *נבחרת למשלוח?*\n\n"
        "תקבל הודעה *🎉 נבחרת למשלוח!* "
        "ואת פרטי המשלוח ופרטי הקשר של המפרסם.\n\n"
        "אם סדרן בחר בך, תקבל גם הודעה "
        "שהסדרן בחר בך.\n\n"

        "━━━━━━━━━━━━━━\n"
        "🚚 *המשלוחים שלי*\n\n"
        "בתפריט בחר *🚚 המשלוחים שלי* כדי לראות "
        "את המשלוחים הפעילים ששובצו אליך.\n\n"

        "━━━━━━━━━━━━━━\n"
        "✅ *סיימת את המשלוח?*\n\n"
        "בסיום לחץ על *✅ סיימתי משלוח / המשלוח הושלם*.\n"
        "המשלוח ייספר כמשלוח שביצעת והמפרסם "
        "יוכל לדרג אותך ⭐\n\n"

        "━━━━━━━━━━━━━━\n"
        "👤 *הפרופיל שלי*\n"
        "כאן ניתן לראות את פרטי הרכב והדירוג שלך.\n\n"

        "💎 *המנוי שלי*\n"
        "כאן ניתן לבדוק את מצב המנוי ולחדש אותו.\n"
        "אם מערכת המנויים כבויה – *השימוש בשליחובוט חינם*.\n"
        "כאשר המנויים פעילים, שליח ללא מנוי פעיל "
        "לא יכול לצפות ולקחת משלוחים.\n\n"

        "💬 *צריך עזרה?*\n"
        "בחר *💬 פנייה לנציג* בתפריט.\n\n"

        "━━━━━━━━━━━━━━\n"
        "📌 *פקודות שכדאי לזכור*\n\n"
        "🟢 פ + עיר – סימון פנוי\n"
        "🟢 פנוי + עיר – סימון פנוי\n"
        "🔴 תפוס – הפסקת קבלת משלוחים\n"
        "🔴 לא פנוי – הפסקת קבלת משלוחים\n"
        "🔴 לא זמין – הפסקת קבלת משלוחים\n"
        "🏠 תפריט – חזרה לתפריט הראשי\n\n"

        "🚗 *שליחובוט – פשוט לעבוד, פשוט לקבל משלוחים.*"
    )

    send_message(
        phone,
        part_1
    )

    send_message(
        phone,
        part_2
    )

    send_buttons(
        phone,
        part_3,
        [
            (
                "driver_menu",
                "↩️ חזרה לתפריט"
            ),
        ],
        header="📖 מדריך לשליח"
    )
# ============================================================
# תפריט סדרן
# ============================================================

def show_dispatcher_menu(phone):
    send_list(
        phone,
        "👨‍💼 תפריט סדרן",
        "בחר פעולה:",
        [
            (
                "dispatcher_new_shipment",
                "📦 פרסום משלוח",
                "יצירת משלוח חדש",
            ),
            (
                "dispatcher_shipments",
                "🚚 ניהול משלוחים",
                "משלוחים פעילים ושיבוץ שליחים",
            ),
            (
                "dispatcher_price_list",
                "💰 ניהול מחירון",
                "הוספה, שינוי ובדיקת מחירים",
            ),
            (
                "dispatcher_driver_mode",
                "🚗 מצב שליח",
                "צפייה ולקיחת משלוחים",
            ),
            (
                "dispatcher_history",
                "📋 היסטוריה",
                "משלוחים קודמים",
            ),
            (
                "dispatcher_support",
                "💬 פנייה לנציג",
                "עזרה ושירות",
            ),
        ],
        button_text="פתח תפריט",
        footer="שליחובוט • סדרן"
    )


# ============================================================
# תפריט מנהל ראשי
# ============================================================

def show_admin_menu(phone):
    system_status = (
        "🟢 פעיל"
        if system_is_enabled()
        else "🔴 תחזוקה"
    )

    driver_status = (
        "🟢 פעיל"
        if driver_side_is_enabled()
        else "🔴 כבוי"
    )

    subscription_status = (
        "🟢 פעילה"
        if subscriptions_are_enabled()
        else "🔴 כבויה"
    )

    send_section_list(
        phone,
        "👑 תפריט מנהל - שליחובוט",
        (
            f"📋 מערכת: {system_status}\n"
            f"🚚 צד שליחים: {driver_status}\n"
            f"💎 מנויים: {subscription_status}\n\n"
            "בחר פעולה:"
        ),
        [
            {
                "title": "📦 משלוחים",
                "rows": [
                    (
                        "admin_shipments",
                        "📦 מרכז משלוחים",
                        "חדשים, פעילים, נסגרו ותשלום",
                    ),
                    
                ],
            },
            {
                "title": "👥 משתמשים",
                "rows": [
                    (
                        "admin_pending_users",
                        "👥 בקשות הרשמה",
                        "משתמשים חדשים שממתינים לאישור",
                    ),
                    (
                        "admin_drivers",
                        "🚗 ניהול שליחים",
                        "שליחים, מידע וסטטוס חשבון",
                    ),
                    (
                        "admin_dispatchers",
                        "👤 ניהול סדרנים",
                        "הוספה והסרת סדרנים",
                    ),
                    (
                        "admin_blocks",
                        "⛔ ניהול חסימות",
                        "חסימה, שחרור ורשימת חסומים",
                    ),
                ],
            },
            {
                "title": "⚙️ ניהול",
                "rows": [
                    (
                        "admin_prices",
                        "💰 ניהול מחירים",
                        "מחירים בין ערים",
                    ),
                    (
                        "admin_cities",
                        "🏙️ ערים וכינויים",
                        "ניהול שמות וקיצורי ערים",
                    ),
                    (
                        "admin_vehicle_types",
                        "🚗 ניהול סוגי רכב",
                        "הוספה, מחיקה והגדרת תעריפים",
                    ),                    
                    (
                        "admin_payments",
                        "💳 תשלומים ומנויים",
                        "ניהול Bit, PayBox, אשרורים ומנויים",
                    ),
                    (
                        "admin_more",
                        "⚙️ עוד אפשרויות",
                        "מערכת, נתונים, תמיכה ויומן פעילות",
                    ),
                ],
            },
        ],
        button_text="פתח",
        footer="שליחובוט • מנהל",
    )

def show_admin_vehicle_types(phone):
    if not is_admin(phone):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, name, price_extra
            FROM vehicle_types
            WHERE is_active = 1
            ORDER BY sort_order ASC, id ASC
            """
        ).fetchall()

    menu_rows = []

    for row in rows:
        menu_rows.append(
            (
                f"admin_vehicle_type_{row['id']}",
                row["name"],
                f"תוספת מחיר: ₪{row['price_extra']}",
            )
        )

    menu_rows.append(
        (
            "admin_vehicle_add",
            "➕ הוספת סוג רכב",
            "הגדרת סוג רכב חדש",
        )
    )

    send_section_list(
        phone,
        "🚗 ניהול סוגי רכב",
        "כאן ניתן להוסיף, לערוך ולמחוק סוגי רכב ולהגדיר את התעריף שלהם.",
        [
            {
                "title": "🚗 סוגי רכב",
                "rows": menu_rows,
            }
        ],
        button_text="בחר",
        footer="שליחובוט • מנהל",
    )    
def show_admin_more_menu(phone):
    send_section_list(
        phone,
        "⚙️ אפשרויות ניהול נוספות",
        "בחר פעולה:",
        [
            {
                "title": "⚙️ מערכת",
                "rows": [
                    (
                        "admin_system_settings",
                        "⚙️ הגדרות מערכת",
                        "מתגים והגדרות כלליות",
                    ),
                    (
                        "admin_statistics",
                        "📊 נתוני מערכת",
                        "משתמשים, משלוחים ומנויים",
                    ),
                    (
                        "admin_support",
                        "💬 תמיכה",
                        "פניות תמיכה",
                    ),
                    (
                        "admin_audit",
                        "📋 יומן פעילות",
                        "פעולות מנהל ומערכת",
                    ),
                (
                    "admin_delete_user",
                    "🗑️ מחיקת משתמש",
                    "מחיקת משתמש ואפשרות להרשמה מחדש",
                ),                    
                    (
                        "admin_menu",
                        "⬅️ חזרה לתפריט",
                        "חזרה לתפריט המנהל הראשי",
                    ),
                ],
            },
        ],
        button_text="פתח",
        footer="שליחובוט • מנהל",
    )

# ============================================================
# הצגת התפריט המתאים למשתמש
# ============================================================

def show_main_menu(phone):
    phone = normalize_phone(
        phone
    )

    if is_admin(
        phone
    ):
        show_admin_menu(
            phone
        )
        return

    user = get_user(
        phone
    )

    if not user or user["status"] == USER_RESET:
        show_role_choice(
            phone
        )
        return

    if user["status"] == USER_BLOCKED:
        send_blocked_message(
            phone
        )
        return

    if user["status"] == USER_PENDING:
        send_pending_approval_message(
            phone,
            user["role"]
        )
        return

    if user["status"] != USER_APPROVED:
        send_message(
            phone,
            "החשבון אינו פעיל כרגע."
        )
        return

    if user["role"] == ROLE_DISPATCHER:
        show_dispatcher_menu(
            phone
        )
        return

    if user["role"] == ROLE_DRIVER:
        show_driver_menu(
            phone
        )
        return

    show_customer_menu(
        phone
    )


# ============================================================
# סוף חלק 2A
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 2B
# תפריטים פנימיים - מנהל וסדרן
# ============================================================


# ============================================================
# מרכז משלוחים - מנהל
# ============================================================

def show_admin_shipments_menu(phone):
    send_list(
        phone,
        "📦 מרכז משלוחים",
        "איזה משלוחים תרצה לראות?",
        [
            (
                "admin_shipments_new",
                "🆕 משלוחים חדשים",
                "משלוחים שעדיין לא שובצו",
            ),
            (
                "admin_shipments_assigned",
                "🚚 שובצו לשליח",
                "משלוחים עם שליח שנבחר",
            ),
            (
                "admin_shipments_completed",
                "✅ הושלמו",
                "היסטוריית משלוחים שהושלמו",
            ),
            (
                "admin_shipments_cancelled",
                "❌ בוטלו",
                "משלוחים שבוטלו",
            ),
            (
                "admin_shipments_no_price",
                "💰 ללא מחיר",
                "מסלולים שמחכים למחירון",
            ),
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • מרכז משלוחים"
    )


# ============================================================
# ניהול מחירון
# משמש גם מנהל וגם סדרן
# ============================================================

def show_price_management_menu(
    phone,
    back_action="admin_menu"
):
    send_list(
        phone,
        "💰 ניהול מחירון",
        (
            "המחיר נשמר לשני הכיוונים.\n"
            "לדוגמה:\n"
            "ירושלים ↔ תל אביב"
        ),
        [
            (
                "price_add",
                "➕ הוספה / עדכון",
                "הוספת מסלול או שינוי מחיר",
            ),
            (
                "price_check",
                "🔎 בדיקת מחיר",
                "בדיקת מחיר בין שתי ערים",
            ),
            (
                "price_delete",
                "🗑️ מחיקת מחיר",
                "מחיקת מסלול מהמחירון",
            ),
            (
                "price_history",
                "📝 היסטוריית שינויים",
                "מי שינה מחיר ומתי",
            ),
            (
                back_action,
                "↩️ חזרה",
                "חזרה לתפריט הקודם",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • מחירון"
    )


# ============================================================
# ניהול ערים וכינויים
# ============================================================

def show_admin_cities_menu(phone):
    send_list(
        phone,
        "🏙️ ערים וכינויים",
        (
            "כאן ניתן להגדיר מילות מפתח "
            "וקיצורים לערים."
        ),
        [
            (
                "admin_city_add",
                "🏙️ הוספת עיר",
                "הוספת עיר חדשה למערכת",
            ),
            (
                "admin_alias_add",
                "➕ הוספת כינוי",
                "לדוגמה: ראשון = ראשון לציון",
            ),
            (
                "admin_alias_delete",
                "🗑️ מחיקת כינוי",
                "הסרת מילת מפתח",
            ),
            (
                "admin_alias_list",
                "📋 רשימת כינויים",
                "צפייה בערים ובמילות המפתח",
            ),
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • ערים"
    )


# ============================================================
# בקשות הרשמה
# ============================================================

def show_admin_pending_users_menu(phone):
    send_list(
        phone,
        "👥 בקשות הרשמה",
        "בחר איזה סוג בקשות להציג:",
        [
            (
                "admin_pending_customers",
                "🏢 מפרסמים",
                "בתי עסק ומפרסמים שממתינים",
            ),
            (
                "admin_pending_drivers",
                "🚗 שליחים",
                "כולל תעודה וסלפי",
            ),
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • הרשמות"
    )


# ============================================================
# ניהול סדרנים
# ============================================================

def show_admin_dispatchers_menu(phone):
    send_list(
        phone,
        "👨‍💼 ניהול סדרנים",
        "בחר פעולה:",
        [
            (
                "admin_dispatcher_add",
                "➕ הוספת סדרן",
                "הוספה לפי מספר טלפון",
            ),
            (
                "admin_dispatcher_remove",
                "➖ הסרת סדרן",
                "הסרת הרשאת סדרן",
            ),
            (
                "admin_dispatcher_list",
                "📋 רשימת סדרנים",
                "צפייה בכל הסדרנים",
            ),
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • סדרנים"
    )


# ============================================================
# ניהול חסימות
# ============================================================

def show_admin_blocks_menu(phone):
    send_list(
        phone,
        "🚫 ניהול חסימות",
        "בחר פעולה:",
        [
            (
                "admin_block_add",
                "🚫 חסימת משתמש",
                "חסימה לפי מספר טלפון",
            ),
            (
                "admin_block_remove",
                "🔓 הסרת חסימה",
                "שחרור משתמש חסום",
            ),
            (
                "admin_block_list",
                "📋 רשימת חסומים",
                "צפייה במשתמשים חסומים",
            ),
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • חסימות"
    )


# ============================================================
# תשלומים ומנויים
# ============================================================

def show_admin_payments_menu(phone):
    subscriptions_status = (
        "🟢 פעילה"
        if subscriptions_are_enabled()
        else "🔴 כבויה"
    )

    subscription_price = get_setting(
        "subscription_price",
        "0"
    )

    send_section_list(
        phone,
        "💳 תשלומים ומנויים",
        (
            f"💎 מערכת מנויים: "
            f"{subscriptions_status}\n"
            f"💰 מחיר חודשי: "
            f"{subscription_price} ₪"
        ),
        [
            {
                "title": "💎 מנויים",
                "rows": [
                    (
                        "admin_subscription_toggle",
                        "🔘 הפעלה / כיבוי",
                        "שינוי מצב מערכת המנויים",
                    ),
                    (
                        "admin_subscription_price",
                        "💰 מחיר מנוי",
                        "שינוי המחיר החודשי",
                    ),
                    (
                        "admin_pending_payments",
                        "⏳ תשלומים ממתינים",
                        "אישור ודחיית תשלומים",
                    ),
                ],
            },
            {
                "title": "💳 אמצעי תשלום",
                "rows": [
                    (
                        "admin_bit_settings",
                        "📱 Bit",
                        "פרטים והפעלה / כיבוי",
                    ),
                    (
                        "admin_paybox_settings",
                        "📲 PayBox",
                        "פרטים והפעלה / כיבוי",
                    ),
                    (
                        "admin_bank_settings",
                        "🏦 העברה בנקאית",
                        "פרטים והפעלה / כיבוי",
                    ),
                    
                        
                ],
            },
            {
                "title": "↩️ חזרה",
                "rows": [
                    (
                        "admin_menu",
                        "↩️ תפריט מנהל",
                        "חזרה",
                    ),
                ],
            },
        ],
        button_text="פתח",
        footer="שליחובוט • תשלומים"
    )


# ============================================================
# הגדרות מערכת
# ============================================================

def show_admin_system_settings(phone):
    system_status = (
        "🟢 פעיל"
        if system_is_enabled()
        else "🔴 תחזוקה"
    )

    driver_status = (
        "🟢 פעיל"
        if driver_side_is_enabled()
        else "🔴 כבוי"
    )

    subscriptions_status = (
        "🟢 פעילה"
        if subscriptions_are_enabled()
        else "🔴 כבויה"
    )

    send_list(
        phone,
        "⚙️ הגדרות מערכת",
        (
            f"🤖 שליחובוט: {system_status}\n"
            f"🚚 צד שליחים: {driver_status}\n"
            f"💎 מנויים: {subscriptions_status}"
        ),
        [
            (
                "admin_system_toggle",
                "🤖 מצב הבוט",
                "פעיל / מצב תחזוקה",
            ),
            (
                "admin_driver_side_toggle",
                "🚚 צד השליחים",
                "הפעלה / כיבוי הפצת משלוחים",
            ),
            (
                "admin_subscription_toggle",
                "💎 מערכת מנויים",
                "הפעלה / כיבוי מנויים",
            ),
            (
                "admin_help_prices",
                "🧤 תוספת עזרה",
                "שינוי תוספת המחיר לפי רכב",
            ),
            (
                "admin_maintenance_drivers",
                "🛠️ תחזוקה לשליחים",
                "שליחת הודעה לכל השליחים",
            ),
            (
                "admin_maintenance_publishers",
                "🛠️ תחזוקה למפרסמים",
                "שליחה למפרסמים ולסדרנים",
            ),            
            (
                "admin_menu",
                "↩️ חזרה",
                "חזרה לתפריט המנהל",
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • הגדרות"
    )


# ============================================================
# מרכז דורש טיפול
# ============================================================

def get_unread_admin_notifications(
    limit=20
):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM admin_notifications
            WHERE is_read = 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                int(limit),
            )
        ).fetchall()


def mark_admin_notification_read(
    notification_id
):
    with db() as conn:
        conn.execute(
            """
            UPDATE admin_notifications
            SET is_read = 1
            WHERE id = ?
            """,
            (
                notification_id,
            )
        )

        conn.commit()


def show_admin_attention(phone):
    notifications = (
        get_unread_admin_notifications(
            10
        )
    )

    if not notifications:
        send_buttons(
            phone,
            (
                "✅ אין כרגע פריטים "
                "שממתינים לטיפול."
            ),
            [
                (
                    "admin_menu",
                    "↩️ חזרה"
                ),
            ],
            header="🔔 דורש טיפול"
        )
        return

    rows = []

    for item in notifications:
        title = (
            item["title"]
            or "התראה"
        )

        rows.append(
            (
                f"admin_notification_{item['id']}",
                title[:24],
                (
                    item["message"]
                    or ""
                )[:72],
            )
        )

    send_list(
        phone,
        "🔔 דורש טיפול",
        "בחר פריט לפתיחה:",
        rows,
        button_text="פתח",
        footer="שליחובוט • מנהל"
    )


# ============================================================
# סטטיסטיקות מנהל
# ============================================================

def get_admin_statistics():
    with db() as conn:
        customers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = ?
            """,
            (
                ROLE_CUSTOMER,
            )
        ).fetchone()["total"]

        drivers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = ?
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
                role = ?
                AND status = ?
            """,
            (
                ROLE_DRIVER,
                USER_APPROVED,
            )
        ).fetchone()["total"]

        pending_drivers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE
                role = ?
                AND status = ?
            """,
            (
                ROLE_DRIVER,
                USER_PENDING,
            )
        ).fetchone()["total"]

        pending_customers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE
                role = ?
                AND status = ?
            """,
            (
                ROLE_CUSTOMER,
                USER_PENDING,
            )
        ).fetchone()["total"]

        dispatchers = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE
                role = ?
                AND status = ?
            """,
            (
                ROLE_DISPATCHER,
                USER_APPROVED,
            )
        ).fetchone()["total"]

        blocked = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE status = ?
            """,
            (
                USER_BLOCKED,
            )
        ).fetchone()["total"]

        open_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status IN (?, ?)
            """,
            (
                SHIP_NEW,
                SHIP_OPEN,
            )
        ).fetchone()["total"]

        assigned_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status = ?
            """,
            (
                SHIP_ASSIGNED,
            )
        ).fetchone()["total"]

        completed_shipments = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status = ?
            """,
            (
                SHIP_COMPLETED,
            )
        ).fetchone()["total"]

        no_price = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM shipments
            WHERE status = ?
            """,
            (
                SHIP_NEEDS_PRICE,
            )
        ).fetchone()["total"]

    return {
        "customers":
            int(customers),

        "drivers":
            int(drivers),

        "approved_drivers":
            int(approved_drivers),

        "pending_drivers":
            int(pending_drivers),

        "pending_customers":
            int(pending_customers),

        "dispatchers":
            int(dispatchers),

        "blocked":
            int(blocked),

        "open_shipments":
            int(open_shipments),

        "assigned_shipments":
            int(assigned_shipments),

        "completed_shipments":
            int(completed_shipments),

        "no_price":
            int(no_price),
    }


def send_admin_statistics(phone):
    stats = get_admin_statistics()

    send_buttons(
        phone,
        (
            "📊 נתוני מערכת\n\n"

            f"🏢 מפרסמים: "
            f"{stats['customers']}\n"

            f"⏳ מפרסמים ממתינים: "
            f"{stats['pending_customers']}\n\n"

            f"🚗 שליחים: "
            f"{stats['drivers']}\n"

            f"✅ שליחים מאושרים: "
            f"{stats['approved_drivers']}\n"

            f"⏳ שליחים ממתינים: "
            f"{stats['pending_drivers']}\n\n"

            f"👨‍💼 סדרנים: "
            f"{stats['dispatchers']}\n"

            f"🚫 חסומים: "
            f"{stats['blocked']}\n\n"

            f"📦 משלוחים פתוחים: "
            f"{stats['open_shipments']}\n"

            f"🚚 שובצו לשליח: "
            f"{stats['assigned_shipments']}\n"

            f"✅ הושלמו: "
            f"{stats['completed_shipments']}\n"

            f"💰 ללא מחיר: "
            f"{stats['no_price']}"
        ),
        [
            (
                "admin_menu",
                "↩️ חזרה"
            ),
        ],
        header="שליחובוט • נתונים"
    )

# ============================================================
# פניות לנציג - מנהל
# ============================================================

def show_admin_support_requests(phone):
    if not is_admin(phone):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM support_requests
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (SUPPORT_OPEN,)
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "✅ אין כרגע פניות פתוחות לנציג.",
            [
                (
                    "admin_more",
                    "↩️ חזרה"
                ),
            ],
            header="💬 פניות לנציג"
        )
        return

    menu_rows = []

    for item in rows:
        menu_rows.append(
            (
                f"admin_support_view_{item['id']}",
                f"פנייה #{item['id']}",
                (
                    f"{item['category'] or 'פנייה'} • "
                    f"{item['phone']}"
                )[:72],
            )
        )

    send_list(
        phone,
        "💬 פניות לנציג",
        "בחר פנייה לצפייה:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט • מנהל"
    )


def show_admin_support_request(phone, request_id):
    if not is_admin(phone):
        return

    with db() as conn:
        item = conn.execute(
            """
            SELECT *
            FROM support_requests
            WHERE id = ?
            LIMIT 1
            """,
            (request_id,)
        ).fetchone()

    if not item:
        send_message(
            phone,
            "❌ הפנייה לא נמצאה."
        )
        return

    send_buttons(
        phone,
        (
            f"💬 פנייה #{item['id']}\n\n"
            f"📱 טלפון: {item['phone']}\n"
            f"📌 נושא: {item['category'] or '-'}\n\n"
            f"📝 הודעה:\n{item['message'] or '-'}"
        ),
        [
            (
                f"admin_support_delete_{item['id']}",
                "🗑️ סגור ומחק"
            ),
            (
                "admin_support",
                "↩️ חזרה"
            ),
        ],
        header="פנייה לנציג"
    )


def delete_admin_support_request(phone, request_id):
    if not is_admin(phone):
        return False

    with db() as conn:
        cursor = conn.execute(
            """
            DELETE FROM support_requests
            WHERE id = ?
            """,
            (request_id,)
        )
        conn.commit()

    if cursor.rowcount:
        send_message(
            phone,
            "🗑️ הפנייה נסגרה ונמחקה מהמערכת."
        )
    else:
        send_message(
            phone,
            "❌ הפנייה לא נמצאה."
        )

    show_admin_support_requests(phone)
    return True
# ============================================================
# סוף חלק 2B
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 3A
# הרשמת מפרסמים ושליחים
# ============================================================


# ============================================================
# התחלת הרשמת מפרסם
# ============================================================

def start_customer_registration(phone):
    phone = normalize_phone(
        phone
    )

    save_session(
        phone,
        "register_customer_name",
        {}
    )

    send_message(
        phone,
        (
            "🏢 הרשמת מפרסם / בית עסק\n\n"
            "כדי לפרסם משלוחים בשליחובוט "
            "יש לעבור אישור מנהל.\n\n"
            "שלח עכשיו את השם המלא שלך."
        )
    )


# ============================================================
# התחלת הרשמת שליח
# ============================================================

def start_driver_registration(phone):
    phone = normalize_phone(
        phone
    )

    save_session(
        phone,
        "register_driver_name",
        {}
    )

    send_message(
        phone,
        (
            "🚗 הרשמת שליח\n\n"
            "ההרשמה כוללת פרטים אישיים, "
            "פרטי רכב, צילום תעודה וסלפי "
            "לצורך אימות.\n\n"
            "לאחר השלמת ההרשמה הבקשה "
            "תעבור לאישור מנהל.\n\n"
            "שלח עכשיו את השם המלא שלך."
        )
    )


# ============================================================
# עדכון נתוני session
# ============================================================

def update_session_data(
    phone,
    state,
    **kwargs
):
    current = get_session(
        phone
    )

    data = (
        current.get(
            "data",
            {}
        )
        or {}
    )

    data.update(
        kwargs
    )

    save_session(
        phone,
        state,
        data
    )

    return data


# ============================================================
# טיפול בהרשמת מפרסם
# ============================================================

def handle_customer_registration_state(
    phone,
    state,
    text
):
    text = clean_text(
        text
    )

    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # --------------------------------------------------------
    # שם מלא
    # --------------------------------------------------------

    if state == "register_customer_name":
        if len(text) < 2:
            send_message(
                phone,
                (
                    "❌ השם קצר מדי.\n"
                    "שלח שם מלא."
                )
            )
            return True

        update_session_data(
            phone,
            "register_customer_business",
            full_name=text
        )

        send_message(
            phone,
            (
                "🏢 מה שם בית העסק?\n\n"
                "אם אתה מפרסם באופן פרטי "
                "ואין לך בית עסק, כתוב:\n"
                "פרטי"
            )
        )

        return True

    # --------------------------------------------------------
    # שם עסק
    # --------------------------------------------------------

    if state == "register_customer_business":
        if len(text) < 2:
            send_message(
                phone,
                (
                    "❌ שלח שם בית עסק "
                    "או כתוב: פרטי"
                )
            )
            return True

        business_name = text

        if text in (
            "פרטי",
            "אין",
            "אין עסק",
            "ללא עסק",
        ):
            business_name = "פרטי"

        update_session_data(
            phone,
            "register_customer_city",
            business_name=business_name
        )

        send_message(
            phone,
            (
                "📍 מאיזו עיר אתה פועל?\n\n"
                "לדוגמה:\n"
                "ירושלים"
            )
        )

        return True

    # --------------------------------------------------------
    # עיר
    # --------------------------------------------------------

    if state == "register_customer_city":
        if len(text) < 2:
            send_message(
                phone,
                "❌ שלח שם עיר."
            )
            return True

        city = resolve_city(
            text
        )

        full_name = clean_text(
            data.get(
                "full_name",
                ""
            )
        )

        business_name = clean_text(
            data.get(
                "business_name",
                ""
            )
        )

        if not full_name:
            clear_session(
                phone
            )

            send_message(
                phone,
                (
                    "❌ פרטי ההרשמה אבדו.\n"
                    "יש להתחיל מחדש."
                )
            )

            show_role_choice(
                phone
            )

            return True

        save_session(
            phone,
            "register_customer_agreement",
            {
                "full_name": full_name,
                "business_name": business_name,
                "city": city,
            }
        )

        send_message(
            phone,
            (
                "📄 *הסכם שימוש למפרסם – שליחובוט*\n\n"
                "שליחובוט – א' א' שליחויות והפצה, משמשת כצד שלישי "
                "המגשר ומחבר בין מפרסמי משלוחים לבין שליחים הרשומים במערכת.\n\n"

                "🛡️ *שליחים מאומתים ובקרה*\n"
                "השליחים הפעילים במערכת עוברים תהליך הרשמה ואימות, "
                "מסירת הפרטים הנדרשים ואישור מנהל לפני תחילת פעילותם. "
                "המערכת מפעילה מנגנוני בקרה, דיווח ותמיכה.\n\n"

                "🚚 *פרסום ואיתור שליח*\n"
                "המערכת מאפשרת לפרסם משלוחים ולאתר שליחים מתוך המערכת. "
                "זמינות השליחים תלויה במיקום, בזמן ובנתוני המשלוח.\n\n"

                "💰 *מחירון והעלאת מחיר*\n"
                "המשלוחים מתפרסמים בהתאם למחירונים המוגדרים במערכת. "
                "אם לא נמצא שליח במחיר המוצע, ניתן להשתמש באפשרות "
                "העלאת מחיר ולהציע מחיר גבוה יותר לצורך איתור שליח.\n\n"

                "💳 *תשלום*\n"
                "התשלום עבור המשלוח מתבצע ישירות בין המפרסם לשליח "
                "בהתאם לסיכום ביניהם.\n\n"

                "⚖️ *חוקיות המשלוח*\n"
                "המפרסם מתחייב לפרסם ולמסור משלוחים חוקיים בלבד, "
                "ולא להעביר פריטים שהחזקתם או הובלתם אסורות על פי דין "
                "או מחייבות היתר שאינו קיים."
            )
        )

        send_buttons(
            phone,
            (
                "📄 *הסכם שימוש למפרסם – המשך*\n\n"

                "📦 *פרטי המשלוח*\n"
                "המפרסם מתחייב למסור פרטים נכונים ומלאים ולדאוג "
                "לאריזה מתאימה. יש לציין מראש פריט שביר, יקר ערך, "
                "רגיש או בעל דרישות מיוחדות.\n\n"

                "🆘 *אירוע חריג ותמיכה*\n"
                "במקרה של אי־מסירה, אובדן, נזק, חשד לגניבה, "
                "התנהלות חריגה או מחלוקת, יש לפנות מיידית לנציג "
                "שליחובוט. המערכת רשאית לבדוק את האירוע, לקבל תיעוד "
                "ולנקוט צעדים בהתאם לכללי המערכת.\n\n"

                "🔐 *פרטיות*\n"
                "לצורך הפעלת השירות וביצוע המשלוח, פרטי קשר, כתובות "
                "ופרטי משלוח הנחוצים לביצועו עשויים להיות מועברים "
                "לגורמים הרלוונטיים בהתאם לדין.\n\n"

                "🚫 שימוש לרעה, התחזות, מסירת מידע כוזב או פעילות "
                "בלתי חוקית עשויים להביא להגבלת פעילות או חסימת החשבון.\n\n"

                "בלחיצה על *„אני מסכים ומאשר”* אני מאשר שקראתי, "
                "הבנתי והסכמתי לתנאים."
            ),
            [
                (
                    "customer_agreement_accept",
                    "✅ אני מסכים ומאשר"
                ),
                (
                    "customer_agreement_reject",
                    "❌ איני מסכים"
                ),
            ]
        )        
        return True        
    return False


# ============================================================
# תפריט בחירת סוג רכב בהרשמת שליח
# ============================================================

def send_driver_vehicle_choice(phone):
    send_list(
        phone,
        "🚗 סוג הרכב",
        "בחר את סוג הרכב שלך:",
        [
            (
                "reg_vehicle_private",
                "🚗 רכב פרטי",
                "רכב פרטי רגיל",
            ),
            (
                "reg_vehicle_7_seats",
                "🚙 7 מקומות",
                "רכב 7 מקומות",
            ),
            (
                "reg_vehicle_small_commercial",
                "🚐 מסחרי קטן",
                "ברלינגו / קנגו וכדומה",
            ),
            (
                "reg_vehicle_large_commercial",
                "🚚 מסחרי גדול",
                "ויטו / טרנזיט וכדומה",
            ),
        ],
        button_text="בחר רכב",
        footer="שליחובוט • הרשמת שליח"
    )


# ============================================================
# טיפול בהרשמת שליח - טקסט ומדיה
# ============================================================

def handle_driver_registration_state(
    phone,
    state,
    text="",
    media_id="",
    message_type=""
):
    text = clean_text(
        text
    )

    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # --------------------------------------------------------
    # שם מלא
    # --------------------------------------------------------

    if state == "register_driver_name":
        if len(text) < 2:
            send_message(
                phone,
                (
                    "❌ השם קצר מדי.\n"
                    "שלח שם מלא."
                )
            )
            return True

        update_session_data(
            phone,
            "register_driver_city",
            full_name=text
        )

        send_message(
            phone,
            (
                "📍 באיזו עיר אתה גר / פועל?\n\n"
                "לדוגמה:\n"
                "ירושלים"
            )
        )

        return True

    # --------------------------------------------------------
    # עיר
    # --------------------------------------------------------

    if state == "register_driver_city":
        if len(text) < 2:
            send_message(
                phone,
                "❌ שלח שם עיר."
            )
            return True

        city = resolve_city(
            text
        )

        update_session_data(
            phone,
            "register_driver_vehicle",
            city=city
        )

        send_driver_vehicle_choice(
            phone
        )

        return True

    # --------------------------------------------------------
    # שנת רכב
    # --------------------------------------------------------

    if state == "register_driver_vehicle_year":
        year_text = re.sub(
            r"[^\d]",
            "",
            text
        )

        if len(year_text) != 4:
            send_message(
                phone,
                (
                    "❌ שלח שנת רכב ב-4 ספרות.\n"
                    "לדוגמה: 2022"
                )
            )
            return True

        year = int(
            year_text
        )

        current_year = datetime.now().year

        if (
            year < 1980
            or year > current_year + 1
        ):
            send_message(
                phone,
                (
                    "❌ שנת הרכב אינה תקינה.\n"
                    "נסה שוב."
                )
            )
            return True

        update_session_data(
            phone,
            "register_driver_vehicle_description",
            vehicle_year=str(year)
        )

        send_message(
            phone,
            (
                "🚘 כתוב בקצרה את דגם הרכב.\n\n"
                "לדוגמה:\n"
                "טויוטה קורולה לבנה\n\n"
                "או:\n"
                "סיטרואן ברלינגו"
            )
        )

        return True

    # --------------------------------------------------------
    # תיאור רכב
    # --------------------------------------------------------

    if state == "register_driver_vehicle_description":
        if len(text) < 2:
            send_message(
                phone,
                "❌ שלח תיאור קצר של הרכב."
            )
            return True

        update_session_data(
            phone,
            "register_driver_id_photo",
            vehicle_description=text
        )

        send_message(
            phone,
            (
                "🪪 עכשיו שלח צילום ברור "
                "של תעודה מזהה.\n\n"
                "יש לשלוח כתמונה."
            )
        )

        return True

    # --------------------------------------------------------
    # צילום תעודה
    # --------------------------------------------------------

    if state == "register_driver_id_photo":
        if (
            message_type != "image"
            or not media_id
        ):
            send_message(
                phone,
                (
                    "❌ יש לשלוח צילום תעודה "
                    "כתמונה."
                )
            )
            return True

        update_session_data(
            phone,
            "register_driver_selfie",
            id_photo_media_id=media_id
        )

        send_message(
            phone,
            (
                "🤳 מצוין.\n\n"
                "עכשיו שלח סלפי ברור שלך "
                "לצורך אימות ההרשמה."
            )
        )

        return True

    # --------------------------------------------------------
    # סלפי
    # --------------------------------------------------------

    if state == "register_driver_selfie":
        if (
            message_type != "image"
            or not media_id
        ):
            send_message(
                phone,
                (
                    "❌ יש לשלוח סלפי "
                    "כתמונה."
                )
            )
            return True

        full_name = clean_text(
            data.get(
                "full_name",
                ""
            )
        )

        city = resolve_city(
            data.get(
                "city",
                ""
            )
        )

        vehicle_type = clean_text(
            data.get(
                "vehicle_type",
                ""
            )
        )

        vehicle_year = clean_text(
            data.get(
                "vehicle_year",
                ""
            )
        )

        vehicle_description = clean_text(
            data.get(
                "vehicle_description",
                ""
            )
        )

        id_photo_media_id = clean_text(
            data.get(
                "id_photo_media_id",
                ""
            )
        )

        if (
            not full_name
            or not city
            or not vehicle_type
            or not vehicle_year
            or not id_photo_media_id
        ):
            clear_session(
                phone
            )

            send_message(
                phone,
                (
                    "❌ פרטי ההרשמה אבדו.\n"
                    "יש להתחיל את ההרשמה מחדש."
                )
            )

            show_role_choice(
                phone
            )

            return True

        user_id = create_or_update_user(
            phone=phone,
            role=ROLE_DRIVER,
            status=USER_PENDING,
            full_name=full_name,
            business_name="",
            city=city
        )

        create_or_update_driver_profile(
            user_id=user_id,
            vehicle_type=vehicle_type,
            vehicle_year=vehicle_year,
            vehicle_description=vehicle_description,
            id_photo_media_id=id_photo_media_id,
            selfie_media_id=media_id
        )
        notify_admin_about_registration(user_id)
        clear_session(
            phone
        )

        vehicle_label = VEHICLE_LABELS.get(
            vehicle_type,
            vehicle_type
        )

        create_admin_notification(
            "driver_registration",
            "🚗 בקשת שליח חדשה",
            (
                f"שם: {full_name}\n"
                f"טלפון: {normalize_phone(phone)}\n"
                f"עיר: {city}\n"
                f"רכב: {vehicle_label}\n"
                f"שנה: {vehicle_year}"
            ),
            "user",
            user_id
        )

        send_message(
            phone,
            (
                "✅ בקשת ההרשמה כשליח "
                "התקבלה בהצלחה.\n\n"
                f"👤 {full_name}\n"
                f"📍 {city}\n"
                f"🚗 {vehicle_label}\n"
                f"📅 שנת רכב: {vehicle_year}\n\n"
                "הפרטים והתמונות הועברו "
                "לאישור מנהל.\n"
                "לאחר האישור נעדכן אותך כאן."
            )
        )

        return True

    return False


# ============================================================
# בחירת סוג רכב בהרשמת שליח
# ============================================================

def handle_driver_registration_action(
    phone,
    action_id
):
    vehicle_map = {
        "reg_vehicle_private":
            VEHICLE_PRIVATE,

        "reg_vehicle_7_seats":
            VEHICLE_7_SEATS,

        "reg_vehicle_small_commercial":
            VEHICLE_SMALL_COMMERCIAL,

        "reg_vehicle_large_commercial":
            VEHICLE_LARGE_COMMERCIAL,
    }

    if action_id not in vehicle_map:
        return False

    session = get_session(
        phone
    )

    if session.get(
        "state"
    ) != "register_driver_vehicle":
        return False

    vehicle_type = vehicle_map[
        action_id
    ]

    update_session_data(
        phone,
        "register_driver_vehicle_year",
        vehicle_type=vehicle_type
    )

    vehicle_label = VEHICLE_LABELS.get(
        vehicle_type,
        vehicle_type
    )

    send_message(
        phone,
        (
            f"🚗 נבחר: {vehicle_label}\n\n"
            "מה שנת הרכב?\n"
            "לדוגמה: 2022"
        )
    )

    return True


# ============================================================
# שליחת בקשת מפרסם למנהל
# ============================================================

def send_customer_registration_to_admin(
    user_id
):
    user = get_user_by_id(
        user_id
    )

    if not user:
        return False

    if not ADMIN_PHONE:
        return False

    send_buttons(
        ADMIN_PHONE,
        (
            "🏢 בקשת הרשמה חדשה – מפרסם\n\n"
            f"👤 שם: "
            f"{user['full_name'] or '-'}\n"
            f"🏢 עסק: "
            f"{user['business_name'] or '-'}\n"
            f"📱 טלפון: "
            f"{user['phone']}\n"
            f"📍 עיר: "
            f"{user['city'] or '-'}"
        ),
        [
            (
                f"approve_user_{user_id}",
                "✅ אישור"
            ),
            (
                f"reject_user_{user_id}",
                "❌ דחייה"
            ),
        ],
        header="שליחובוט • הרשמה"
    )

    return True


# ============================================================
# שליחת בקשת שליח למנהל
# ============================================================

def send_driver_registration_to_admin(
    user_id
):
    user = get_user_by_id(
        user_id
    )

    profile = get_driver_profile(
        user_id
    )

    if (
        not user
        or not profile
        or not ADMIN_PHONE
    ):
        return False

    vehicle_label = VEHICLE_LABELS.get(
        profile["vehicle_type"],
        profile["vehicle_type"]
        or "-"
    )

    send_message(
        ADMIN_PHONE,
        (
            "🚗 בקשת הרשמה חדשה – שליח\n\n"
            f"👤 שם: "
            f"{user['full_name'] or '-'}\n"
            f"📱 טלפון: "
            f"{user['phone']}\n"
            f"📍 עיר: "
            f"{user['city'] or '-'}\n"
            f"🚗 רכב: "
            f"{vehicle_label}\n"
            f"📅 שנה: "
            f"{profile['vehicle_year'] or '-'}\n"
            f"📝 תיאור: "
            f"{profile['vehicle_description'] or '-'}"
        )
    )

    if profile["id_photo_media_id"]:
        send_image_by_media_id(
            ADMIN_PHONE,
            profile["id_photo_media_id"],
            "🪪 צילום תעודה"
        )

    if profile["selfie_media_id"]:
        send_image_by_media_id(
            ADMIN_PHONE,
            profile["selfie_media_id"],
            "🤳 סלפי אימות"
        )

    send_buttons(
        ADMIN_PHONE,
        (
            "בחר פעולה עבור בקשת "
            f"השליח {user['full_name'] or ''}:"
        ),
        [
            (
                f"approve_user_{user_id}",
                "✅ אישור"
            ),
            (
                f"reject_user_{user_id}",
                "❌ דחייה"
            ),
        ],
        header="אישור שליח"
    )

    return True


# ============================================================
# שליחת בקשת הרשמה לפי סוג משתמש
# ============================================================

def notify_admin_about_registration(
    user_id
):
    user = get_user_by_id(
        user_id
    )

    if not user:
        return False

    if user["role"] == ROLE_DRIVER:
        return send_driver_registration_to_admin(
            user_id
        )

    if user["role"] == ROLE_CUSTOMER:
        return send_customer_registration_to_admin(
            user_id
        )

    return False


# ============================================================
# חלק 3B
# אישור ודחיית הרשמות + הצגת בקשות למנהל
# ============================================================


# ============================================================
# רשימת מפרסמים שממתינים לאישור
# ============================================================

def show_pending_customers(phone):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM users
            WHERE
                role = ?
                AND status = ?
            ORDER BY created_at ASC
            LIMIT 10
            """,
            (
                ROLE_CUSTOMER,
                USER_PENDING,
            )
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "✅ אין כרגע מפרסמים שממתינים לאישור.",
            [
                (
                    "admin_pending_users",
                    "↩️ חזרה"
                ),
            ],
            header="🏢 מפרסמים ממתינים"
        )
        return

    menu_rows = []

    for user in rows:
        business_name = (
            user["business_name"]
            or user["full_name"]
            or "מפרסם"
        )

        menu_rows.append(
            (
                f"admin_view_pending_{user['id']}",
                business_name[:24],
                (
                    f"{user['phone']} • "
                    f"{user['city'] or '-'}"
                )[:72],
            )
        )

    send_list(
        phone,
        "🏢 מפרסמים ממתינים",
        "בחר בקשה לצפייה:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט • הרשמות"
    )


# ============================================================
# רשימת שליחים שממתינים לאישור
# ============================================================

def show_pending_drivers(phone):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                u.*,
                d.vehicle_type,
                d.vehicle_year
            FROM users u

            LEFT JOIN driver_profiles d
                ON d.user_id = u.id

            WHERE
                u.role = ?
                AND u.status = ?

            ORDER BY u.created_at ASC
            LIMIT 10
            """,
            (
                ROLE_DRIVER,
                USER_PENDING,
            )
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "✅ אין כרגע שליחים שממתינים לאישור.",
            [
                (
                    "admin_pending_users",
                    "↩️ חזרה"
                ),
            ],
            header="🚗 שליחים ממתינים"
        )
        return

    menu_rows = []

    for user in rows:
        vehicle_label = VEHICLE_LABELS.get(
            user["vehicle_type"],
            user["vehicle_type"]
            or "רכב לא צוין"
        )

        menu_rows.append(
            (
                f"admin_view_pending_{user['id']}",
                (
                    user["full_name"]
                    or "שליח"
                )[:24],
                (
                    f"{vehicle_label} • "
                    f"{user['city'] or '-'}"
                )[:72],
            )
        )

    send_list(
        phone,
        "🚗 שליחים ממתינים",
        "בחר בקשה לצפייה:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט • הרשמות"
    )


# ============================================================
# הצגת בקשת הרשמה מסוימת למנהל
# ============================================================

def show_pending_user_details(
    admin_phone,
    user_id
):
    user = get_user_by_id(
        user_id
    )

    if not user:
        send_message(
            admin_phone,
            "❌ המשתמש לא נמצא."
        )
        return

    if user["role"] == ROLE_DRIVER:
        profile = get_driver_profile(
            user_id
        )

        if not profile:
            send_message(
                admin_phone,
                "❌ פרופיל השליח לא נמצא."
            )
            return

        vehicle_label = VEHICLE_LABELS.get(
            profile["vehicle_type"],
            profile["vehicle_type"]
            or "-"
        )

        send_message(
            admin_phone,
            (
                "🚗 בקשת הרשמת שליח\n\n"
                f"👤 שם: {user['full_name'] or '-'}\n"
                f"📱 טלפון: {user['phone']}\n"
                f"📍 עיר: {user['city'] or '-'}\n"
                f"🚗 רכב: {vehicle_label}\n"
                f"📅 שנה: {profile['vehicle_year'] or '-'}\n"
                f"📝 תיאור: "
                f"{profile['vehicle_description'] or '-'}"
            )
        )

        if profile["id_photo_media_id"]:
            send_image_by_media_id(
                admin_phone,
                profile["id_photo_media_id"],
                "🪪 צילום תעודה"
            )

        if profile["selfie_media_id"]:
            send_image_by_media_id(
                admin_phone,
                profile["selfie_media_id"],
                "🤳 סלפי אימות"
            )

        send_buttons(
            admin_phone,
            "בחר מה לעשות עם בקשת השליח:",
            [
                (
                    f"approve_user_{user_id}",
                    "✅ אישור"
                ),
                (
                    f"reject_user_{user_id}",
                    "❌ דחייה"
                ),
            ],
            header="אישור שליח"
        )

        return

    send_buttons(
        admin_phone,
        (
            "🏢 בקשת הרשמת מפרסם\n\n"
            f"👤 שם: {user['full_name'] or '-'}\n"
            f"🏢 עסק: {user['business_name'] or '-'}\n"
            f"📱 טלפון: {user['phone']}\n"
            f"📍 עיר: {user['city'] or '-'}"
        ),
        [
            (
                f"approve_user_{user_id}",
                "✅ אישור"
            ),
            (
                f"reject_user_{user_id}",
                "❌ דחייה"
            ),
        ],
        header="אישור מפרסם"
    )


# ============================================================
# אישור הרשמה ע"י מנהל
# ============================================================

def admin_approve_registration(
    admin_phone,
    user_id
):
    if not is_admin(
        admin_phone
    ):
        return False

    user = get_user_by_id(
        user_id
    )

    if not user:
        send_message(
            admin_phone,
            "❌ המשתמש לא נמצא."
        )
        return True

    if user["status"] == USER_APPROVED:
        send_message(
            admin_phone,
            "ℹ️ המשתמש כבר מאושר."
        )
        return True

    if not approve_user(
        user_id,
        admin_phone
    ):
        send_message(
            admin_phone,
            "❌ לא ניתן היה לאשר את המשתמש."
        )
        return True

    if user["role"] == ROLE_DRIVER:
        send_message(
            user["phone"],
            (
                "🎉 ההרשמה שלך כשליח אושרה!\n\n"
                "ברוך הבא לשליחובוט 🚗\n"
                "כעת ניתן להיכנס לתפריט השליח."
            )
        )

        show_driver_menu(
            user["phone"]
        )

        role_text = "שליח"

    else:
        business_name = (
            user["business_name"]
            or user["full_name"]
            or ""
        )

        send_message(
            user["phone"],
            (
                "🎉 בקשת ההרשמה שלך אושרה!\n\n"
                f"🏢 {business_name}\n"
                "כעת ניתן לפרסם ולנהל משלוחים "
                "בשליחובוט."
            )
        )

        show_customer_menu(
            user["phone"]
        )

        role_text = "מפרסם"

    send_message(
        admin_phone,
        (
            f"✅ {role_text} אושר בהצלחה.\n\n"
            f"👤 {user['full_name'] or '-'}\n"
            f"📱 {user['phone']}"
        )
    )

    return True


# ============================================================
# דחיית הרשמה ע"י מנהל
# ============================================================

def admin_reject_registration(
    admin_phone,
    user_id
):
    if not is_admin(
        admin_phone
    ):
        return False

    user = get_user_by_id(
        user_id
    )

    if not user:
        send_message(
            admin_phone,
            "❌ המשתמש לא נמצא."
        )
        return True

    if not reject_user(
        user_id,
        admin_phone
    ):
        send_message(
            admin_phone,
            "❌ לא ניתן היה לדחות את הבקשה."
        )
        return True

    send_message(
        user["phone"],
        (
            "❌ בקשת ההרשמה שלך "
            "לשליחובוט לא אושרה כרגע.\n\n"
            "לפרטים נוספים ניתן לפנות לנציג."
        )
    )

    send_message(
        admin_phone,
        (
            "❌ בקשת ההרשמה נדחתה.\n\n"
            f"👤 {user['full_name'] or '-'}\n"
            f"📱 {user['phone']}"
        )
    )

    return True


# ============================================================
# טיפול בכפתורי אישור / דחייה / צפייה
# ============================================================

def handle_admin_registration_action(
    phone,
    action_id
):
    if not is_admin(
        phone
    ):
        return False

    if action_id.startswith(
        "admin_view_pending_"
    ):
        raw_id = action_id.replace(
            "admin_view_pending_",
            "",
            1
        )

        if raw_id.isdigit():
            show_pending_user_details(
                phone,
                int(raw_id)
            )

            return True

    if action_id.startswith(
        "approve_user_"
    ):
        raw_id = action_id.replace(
            "approve_user_",
            "",
            1
        )

        if raw_id.isdigit():
            return admin_approve_registration(
                phone,
                int(raw_id)
            )

    if action_id.startswith(
        "reject_user_"
    ):
        raw_id = action_id.replace(
            "reject_user_",
            "",
            1
        )

        if raw_id.isdigit():
            return admin_reject_registration(
                phone,
                int(raw_id)
            )

    return False


# ============================================================
# סוף חלק 3
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 4A
# יצירת משלוח - זרימה מלאה
# ============================================================


# ============================================================
# התחלת יצירת משלוח
# ============================================================

def start_new_shipment(phone):
    phone = normalize_phone(
        phone
    )

    user = get_user(
        phone
    )

    if not user:
        send_message(
            phone,
            "❌ המשתמש לא נמצא."
        )
        return

    if user["status"] != USER_APPROVED:
        send_message(
            phone,
            "⏳ החשבון עדיין אינו מאושר."
        )
        return

    if user["role"] not in (
        ROLE_CUSTOMER,
        ROLE_DISPATCHER,
        ROLE_ADMIN,
    ):
        send_message(
            phone,
            "❌ אין הרשאה לפרסם משלוח."
        )
        return

    save_session(
        phone,
        "shipment_origin_city",
        {}
    )

    send_message(
        phone,
        (
            "📦 יצירת משלוח חדש\n\n"
            "📍 מאיזו עיר המשלוח יוצא?\n\n"
            "אפשר לכתוב גם קיצור שהוגדר "
            "במערכת.\n"
            "לדוגמה: ירושלים / ים"
        )
    )


# ============================================================
# בחירת זמן איסוף
# ============================================================

def send_pickup_time_choice(phone):
    send_buttons(
        phone,
        (
            "🕐 מתי המשלוח צריך לצאת?"
        ),
        [
            (
                "shipment_time_now",
                "⚡ עכשיו"
            ),
            (
                "shipment_time_today",
                "📅 היום"
            ),
            (
                "shipment_time_other",
                "📝 זמן אחר"
            ),
        ],
        header="זמן איסוף"
    )


# ============================================================
# בחירת סוג רכב למשלוח
# ============================================================

def send_shipment_vehicle_choice(phone):
    send_list(
        phone,
        "🚗 סוג רכב נדרש",
        "איזה רכב מתאים למשלוח?",
        [
            (
                "shipment_vehicle_private",
                "🚗 רכב פרטי",
                "משלוח שמתאים לרכב פרטי",
            ),
            (
                "shipment_vehicle_7_seats",
                "🚙 7 מקומות",
                "למשלוח גדול יותר",
            ),
            (
                "shipment_vehicle_small",
                "🚐 מסחרי קטן",
                "ברלינגו / קנגו וכדומה",
            ),
            (
                "shipment_vehicle_large",
                "🚚 מסחרי גדול",
                "ויטו / טרנזיט וכדומה",
            ),
        ],
        button_text="בחר רכב",
        footer="שליחובוט • משלוח חדש"
    )


# ============================================================
# בחירת עזרת שליח
# ============================================================

def send_driver_help_choice(
    phone,
    vehicle_type
):
    extra = get_driver_help_extra(
        vehicle_type
    )

    send_buttons(
        phone,
        (
            "🧤 האם נדרשת עזרת השליח "
            "בהעמסה או בפריקה?\n\n"
            f"תוספת במקרה של עזרה: "
            f"{extra} ₪"
        ),
        [
            (
                "shipment_help_yes",
                "✅ צריך עזרה"
            ),
            (
                "shipment_help_no",
                "❌ לא צריך"
            ),
        ],
        header="עזרת שליח"
    )


# ============================================================
# בחירת הערות
# ============================================================

def send_notes_choice(phone):
    send_buttons(
        phone,
        "📝 האם יש הערה מיוחדת למשלוח?",
        [
            (
                "shipment_notes_none",
                "ללא הערות"
            ),
            (
                "shipment_notes_add",
                "✍️ הוסף הערה"
            ),
        ],
        header="הערות"
    )


# ============================================================
# בניית סיכום משלוח לפני פרסום
# ============================================================

def build_shipment_summary(data):
    origin_city = resolve_city(
        data.get(
            "origin_city",
            ""
        )
    )

    destination_city = resolve_city(
        data.get(
            "destination_city",
            ""
        )
    )

    pickup_address = clean_text(
        data.get(
            "pickup_address",
            ""
        )
    )

    dropoff_address = clean_text(
        data.get(
            "dropoff_address",
            ""
        )
    )

    pickup_time = clean_text(
        data.get(
            "pickup_time",
            "עכשיו"
        )
    )

    vehicle_type = data.get(
        "vehicle_type",
        VEHICLE_PRIVATE
    )

    vehicle_label = VEHICLE_LABELS.get(
        vehicle_type,
        vehicle_type
    )

    driver_help = bool(
        data.get(
            "driver_help",
            False
        )
    )

    notes = clean_text(
        data.get(
            "notes",
            ""
        )
    )

    price_data = calculate_shipment_price(
        origin_city,
        destination_city,
        vehicle_type,
        driver_help
    )

    lines = [
        "📦 סיכום המשלוח",
        "",
        f"📍 מוצא: {origin_city}",
        f"🏠 איסוף: {pickup_address}",
        "",
        f"📍 יעד: {destination_city}",
        f"🏠 מסירה: {dropoff_address}",
        "",
        f"🕐 זמן: {pickup_time}",
        f"🚗 רכב: {vehicle_label}",
        (
            "🧤 עזרת שליח: כן"
            if driver_help
            else "🧤 עזרת שליח: לא"
        ),
    ]

    if notes:
        lines.extend(
            [
                "",
                f"📝 הערה: {notes}",
            ]
        )

    lines.append(
        ""
    )

    if price_data is None:
        lines.extend(
            [
                "💰 מחיר: ממתין לתמחור",
                "",
                (
                    "המסלול עדיין לא קיים "
                    "במחירון."
                ),
            ]
        )

    else:
        if price_data["help_extra"] > 0:
            lines.append(
                (
                    f"💰 מחיר מסלול: "
                    f"{price_data['base_price']} ₪"
                )
            )

            lines.append(
                (
                    f"🧤 תוספת עזרה: "
                    f"{price_data['help_extra']} ₪"
                )
            )

        lines.append(
            (
                f"💵 מחיר סופי: "
                f"{price_data['final_price']} ₪"
            )
        )

    return (
        "\n".join(
            lines
        ),
        price_data,
    )


# ============================================================
# הצגת סיכום
# ============================================================

def show_new_shipment_summary(phone):
    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    summary, price_data = build_shipment_summary(
        data
    )

    if price_data is None:
        send_buttons(
            phone,
            (
                summary
                + "\n\n"
                + "ניתן לשלוח את הבקשה "
                + "לתמחור מנהל/סדרן."
            ),
            [
                (
                    "shipment_confirm",
                    "✅ שלח לתמחור"
                ),
                (
                    "shipment_cancel",
                    "❌ ביטול"
                ),
            ],
            header="אישור משלוח"
        )
        return

    send_list(
        phone,
        "📦 אישור משלוח",
        summary,
        [
            (
                "shipment_confirm",
                "✅ פרסם משלוח",
                "פרסום המשלוח לשליחים"
            ),
            (
                "shipment_edit",
                "✏️ עריכה",
                "חזרה לעריכת המשלוח"
            ),
            (
                "shipment_cancel",
                "❌ ביטול",
                "ביטול יצירת המשלוח"
            ),
        ],
        button_text="בחר פעולה",
        footer="שליחובוט"
    )

# ============================================================
# טיפול בטקסט במהלך יצירת משלוח
# ============================================================

def handle_new_shipment_state(
    phone,
    state,
    text
):
    text = clean_text(
        text
    )

    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # --------------------------------------------------------
    # עיר מוצא
    # --------------------------------------------------------

    if state == "shipment_origin_city":
        if len(text) < 2:
            send_message(
                phone,
                "❌ שלח עיר מוצא."
            )
            return True

        origin_city = resolve_city(
            text
        )

        update_session_data(
            phone,
            "shipment_pickup_address",
            origin_city=origin_city
        )

        send_message(
            phone,
            (
                f"📍 עיר מוצא: {origin_city}\n\n"
                "🏠 מה כתובת האיסוף המלאה?\n\n"
                "לדוגמה:\n"
                "יפו 25 ירושלים"
            )
        )

        return True

    # --------------------------------------------------------
    # כתובת איסוף
    # --------------------------------------------------------

    if state == "shipment_pickup_address":
        if len(text) < 3:
            send_message(
                phone,
                (
                    "❌ כתובת האיסוף קצרה מדי.\n"
                    "שלח כתובת מלאה."
                )
            )
            return True

        update_session_data(
            phone,
            "shipment_destination_city",
            pickup_address=text
        )

        send_message(
            phone,
            (
                "📍 לאיזו עיר המשלוח מיועד?\n\n"
                "לדוגמה:\n"
                "תל אביב"
            )
        )

        return True

    # --------------------------------------------------------
    # עיר יעד
    # --------------------------------------------------------

    if state == "shipment_destination_city":
        if len(text) < 2:
            send_message(
                phone,
                "❌ שלח עיר יעד."
            )
            return True

        destination_city = resolve_city(
            text
        )

        update_session_data(
            phone,
            "shipment_dropoff_address",
            destination_city=destination_city
        )

        send_message(
            phone,
            (
                f"📍 עיר יעד: "
                f"{destination_city}\n\n"
                "🏠 מה כתובת המסירה המלאה?"
            )
        )

        return True

    # --------------------------------------------------------
    # כתובת מסירה
    # --------------------------------------------------------

    if state == "shipment_dropoff_address":
        if len(text) < 3:
            send_message(
                phone,
                (
                    "❌ כתובת המסירה קצרה מדי.\n"
                    "שלח כתובת מלאה."
                )
            )
            return True

        update_session_data(
            phone,
            "shipment_pickup_time_choice",
            dropoff_address=text
        )

        send_pickup_time_choice(
            phone
        )

        return True

    # --------------------------------------------------------
    # זמן מותאם אישית
    # --------------------------------------------------------

    if state == "shipment_custom_time":
        if len(text) < 2:
            send_message(
                phone,
                (
                    "❌ כתוב מתי המשלוח "
                    "צריך לצאת."
                )
            )
            return True

        update_session_data(
            phone,
            "shipment_vehicle_choice",
            pickup_time=text
        )

        send_shipment_vehicle_choice(
            phone
        )

        return True

    # --------------------------------------------------------
    # הערה חופשית
    # --------------------------------------------------------

    if state == "shipment_notes_text":
        if len(text) > 500:
            send_message(
                phone,
                (
                    "❌ ההערה ארוכה מדי.\n"
                    "עד 500 תווים."
                )
            )
            return True

        update_session_data(
            phone,
            "shipment_summary",
            notes=text
        )

        show_new_shipment_summary(
            phone
        )

        return True

    return False


# ============================================================
# טיפול בכפתורים במהלך יצירת משלוח
# ============================================================

def handle_new_shipment_action(
    phone,
    action_id
):
    session = get_session(
        phone
    )

    state = session.get(
        "state",
        ""
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # --------------------------------------------------------
    # זמן איסוף
    # --------------------------------------------------------

    if (
        state == "shipment_pickup_time_choice"
        and action_id == "shipment_time_now"
    ):
        update_session_data(
            phone,
            "shipment_vehicle_choice",
            pickup_time="עכשיו"
        )

        send_shipment_vehicle_choice(
            phone
        )

        return True

    if (
        state == "shipment_pickup_time_choice"
        and action_id == "shipment_time_today"
    ):
        update_session_data(
            phone,
            "shipment_vehicle_choice",
            pickup_time="היום"
        )

        send_shipment_vehicle_choice(
            phone
        )

        return True

    if (
        state == "shipment_pickup_time_choice"
        and action_id == "shipment_time_other"
    ):
        save_session(
            phone,
            "shipment_custom_time",
            data
        )

        send_message(
            phone,
            (
                "🕐 כתוב את זמן האיסוף.\n\n"
                "לדוגמה:\n"
                "היום בשעה 18:30\n"
                "או\n"
                "מחר בבוקר"
            )
        )

        return True

    # --------------------------------------------------------
    # סוג רכב
    # --------------------------------------------------------

    vehicle_actions = {
        "shipment_vehicle_private":
            VEHICLE_PRIVATE,

        "shipment_vehicle_7_seats":
            VEHICLE_7_SEATS,

        "shipment_vehicle_small":
            VEHICLE_SMALL_COMMERCIAL,

        "shipment_vehicle_large":
            VEHICLE_LARGE_COMMERCIAL,
    }

    if (
        state == "shipment_vehicle_choice"
        and action_id in vehicle_actions
    ):
        vehicle_type = vehicle_actions[
            action_id
        ]

        update_session_data(
            phone,
            "shipment_help_choice",
            vehicle_type=vehicle_type
        )

        send_driver_help_choice(
            phone,
            vehicle_type
        )

        return True

    # --------------------------------------------------------
    # עזרת שליח
    # --------------------------------------------------------

    if (
        state == "shipment_help_choice"
        and action_id == "shipment_help_yes"
    ):
        update_session_data(
            phone,
            "shipment_notes_choice",
            driver_help=True
        )

        send_notes_choice(
            phone
        )

        return True

    if (
        state == "shipment_help_choice"
        and action_id == "shipment_help_no"
    ):
        update_session_data(
            phone,
            "shipment_notes_choice",
            driver_help=False
        )

        send_notes_choice(
            phone
        )

        return True

    # --------------------------------------------------------
    # הערות
    # --------------------------------------------------------

    if (
        state == "shipment_notes_choice"
        and action_id == "shipment_notes_none"
    ):
        update_session_data(
            phone,
            "shipment_summary",
            notes=""
        )

        show_new_shipment_summary(
            phone
        )

        return True

    if (
        state == "shipment_notes_choice"
        and action_id == "shipment_notes_add"
    ):
        save_session(
            phone,
            "shipment_notes_text",
            data
        )

        send_message(
            phone,
            (
                "📝 כתוב את ההערה "
                "שברצונך להוסיף למשלוח."
            )
        )

        return True

    # --------------------------------------------------------
    # ביטול
    # --------------------------------------------------------

    if action_id == "shipment_cancel":
        clear_session(
            phone
        )

        send_message(
            phone,
            "❌ יצירת המשלוח בוטלה."
        )

        show_main_menu(
            phone
        )

        return True

    # --------------------------------------------------------
    # עריכת משלוח לפני פרסום
    # מתחילים מחדש כדי למנוע נתונים חלקיים.
    # --------------------------------------------------------

    if (
        state == "shipment_summary"
        and action_id == "shipment_edit"
    ):
        start_new_shipment(
            phone
        )

        return True

    # --------------------------------------------------------
    # אישור ויצירת המשלוח
    # --------------------------------------------------------

    if (
        state == "shipment_summary"
        and action_id == "shipment_confirm"
    ):
        user = get_user(
            phone
        )

        if not user:
            clear_session(
                phone
            )

            send_message(
                phone,
                "❌ המשתמש לא נמצא."
            )

            return True

        required_fields = [
            "origin_city",
            "pickup_address",
            "destination_city",
            "dropoff_address",
            "pickup_time",
            "vehicle_type",
        ]

        for field in required_fields:
            if not data.get(
                field
            ):
                send_message(
                    phone,
                    (
                        "❌ חסרים פרטים במשלוח.\n"
                        "יש להתחיל את יצירת "
                        "המשלוח מחדש."
                    )
                )

                start_new_shipment(
                    phone
                )

                return True

        try:
            shipment_id = create_shipment(
                publisher_id=user["id"],

                origin_city=data[
                    "origin_city"
                ],

                destination_city=data[
                    "destination_city"
                ],

                pickup_address=data[
                    "pickup_address"
                ],

                dropoff_address=data[
                    "dropoff_address"
                ],

                pickup_time=data[
                    "pickup_time"
                ],

                vehicle_type=data[
                    "vehicle_type"
                ],

                driver_help=bool(
                    data.get(
                        "driver_help",
                        False
                    )
                ),

                notes=data.get(
                    "notes",
                    ""
                )
            )

        except Exception as exc:
            print(
                "CREATE SHIPMENT ERROR:",
                repr(exc)
            )

            send_message(
                phone,
                (
                    "❌ אירעה שגיאה ביצירת "
                    "המשלוח.\n"
                    "נסה שוב."
                )
            )

            return True

        clear_session(
            phone
        )

        shipment = get_shipment(
            shipment_id
        )

        if not shipment:
            send_message(
                phone,
                "❌ המשלוח לא נמצא לאחר היצירה."
            )
            return True

        if (
            shipment["status"]
            == SHIP_NEEDS_PRICE
        ):
            send_message(                phone,
                (
                    "⏳ המשלוח נשמר וממתין לתמחור.\n\n"
                    f"📦 {shipment['business_name'] or user['full_name'] or 'משלוח'}\n"
                    f"📍 {shipment['origin_city']} → "
                    f"{shipment['destination_city']}\n\n"
                    "ברגע שמנהל או סדרן יוסיף מחיר "
                    "למסלול, ניתן יהיה לפרסם את המשלוח."
                )
            )

            # התראה מיידית למנהל
            if ADMIN_PHONE:
                send_buttons(
                    ADMIN_PHONE,
                    (
                        "💰 משלוח חדש דורש תמחור\n\n"
                        f"🏢 מפרסם: "
                        f"{shipment['business_name'] or user['full_name'] or '-'}\n"
                        f"📱 טלפון: {user['phone']}\n\n"
                        f"📍 מוצא: {shipment['origin_city']}\n"
                        f"📍 יעד: {shipment['destination_city']}\n"
                        f"🏠 איסוף: {shipment['pickup_address']}\n"
                        f"🏠 מסירה: {shipment['dropoff_address']}"
                    ),
                    [
                        (
                            f"admin_price_shipment_{shipment_id}",
                            "💰 הוסף מחיר"
                        ),
                        (
                            f"admin_view_shipment_{shipment_id}",
                            "📦 פרטים"
                        ),
                    ],
                    header="נדרש תמחור"
                )

            return True

        # ----------------------------------------------------
        # המשלוח מתומחר ומוכן לפרסום
        # ----------------------------------------------------

        distribute_shipment_to_drivers(
            shipment_id
        )

        send_buttons(
            phone,
            (
                "✅ המשלוח נוצר בהצלחה!\n\n"
                f"📦 {shipment['business_name'] or user['full_name'] or 'משלוח'}\n"
                f"📍 {shipment['origin_city']} → "
                f"{shipment['destination_city']}\n"
                f"💵 מחיר: {shipment['final_price']} ₪\n\n"
                "המשלוח הופץ לשליחים המתאימים."
            ),
            [
                (
                    f"customer_cancel_shipment_{shipment_id}",
                    "❌ בטל משלוח"
                ),
            ],
            header="📦 המשלוח פורסם"
        )        

        # מנהל רואה גם את מספר הטלפון של המפרסם
        if ADMIN_PHONE:
            send_buttons(
                ADMIN_PHONE,
                (
                    "📦 משלוח חדש\n\n"
                    f"🏢 מפרסם: "
                    f"{shipment['business_name'] or user['full_name'] or '-'}\n"
                    f"📱 טלפון: {user['phone']}\n\n"
                    f"📍 {shipment['origin_city']} → "
                    f"{shipment['destination_city']}\n"
                    f"🏠 איסוף: {shipment['pickup_address']}\n"
                    f"🏠 מסירה: {shipment['dropoff_address']}\n"
                    f"🕐 {shipment['pickup_time']}\n"
                    f"💵 {shipment['final_price']} ₪"
                ),
                [
                    (
                        f"admin_view_shipment_{shipment_id}",
                        "📦 ניהול"
                    ),
                ],
                header="שליחובוט • משלוח חדש"
            )

        return True

    return False


# ============================================================
# הצגת פרטי משלוח מלאים
# ============================================================

def build_shipment_details_text(
    shipment,
    include_publisher_phone=False,
    include_driver=False
):
    if not shipment:
        return "❌ המשלוח לא נמצא."

    publisher = get_user_by_id(
        shipment["publisher_id"]
    )

    vehicle_label = VEHICLE_LABELS.get(
        shipment["vehicle_type"],
        shipment["vehicle_type"]
        or "-"
    )

    business_name = (
        shipment["business_name"]
        or (
            publisher["business_name"]
            if publisher
            else ""
        )
        or (
            publisher["full_name"]
            if publisher
            else ""
        )
        or "מפרסם"
    )

    lines = [
        f"📦 משלוח – {business_name}",
        "",
        f"📍 מוצא: {shipment['origin_city']}",
        f"🏠 איסוף: {shipment['pickup_address']}",
        "",
        f"📍 יעד: {shipment['destination_city']}",
        f"🏠 מסירה: {shipment['dropoff_address']}",
        "",
        f"🕐 זמן: {shipment['pickup_time']}",
        f"🚗 רכב: {vehicle_label}",
        (
            "🧤 עזרת שליח: כן"
            if shipment["driver_help"]
            else "🧤 עזרת שליח: לא"
        ),
    ]

    if shipment["notes"]:
        lines.append(
            f"📝 הערה: {shipment['notes']}"
        )

    lines.extend(
        [
            "",
            f"💵 מחיר: {shipment['final_price']} ₪",
        ]
    )

    if (
        include_publisher_phone
        and publisher
    ):
        lines.extend(
            [
                "",
                f"📱 טלפון מפרסם: {publisher['phone']}",
            ]
        )

    if (
        include_driver
        and shipment["assigned_driver_id"]
    ):
        driver = get_shipment_driver(
            shipment["id"]
        )

        if driver:
            rating_count = int(
                driver["rating_count"]
                or 0
            )

            rating_sum = int(
                driver["rating_sum"]
                or 0
            )

            rating_text = "ללא דירוג"

            if rating_count > 0:
                rating_text = (
                    f"{round(rating_sum / rating_count, 1)} ⭐ "
                    f"({rating_count} דירוגים)"
                )

            lines.extend(
                [
                    "",
                    "🚗 השליח שנבחר:",
                    f"👤 {driver['full_name'] or '-'}",
                    f"📱 {driver['phone']}",
                    (
                        f"🚘 "
                        f"{VEHICLE_LABELS.get(driver['vehicle_type'], driver['vehicle_type'] or '-')}"
                    ),
                    f"⭐ {rating_text}",
                ]
            )

    return "\n".join(
        lines
    )


# ============================================================
# סוף חלק 4
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 5A
# הפצת משלוחים + התעניינות שליח + זמן הגעה
# ============================================================


# ============================================================
# בדיקה האם שליח מתאים למשלוח
# ============================================================

def driver_matches_shipment(
    driver_user,
    driver_profile,
    shipment
):
    if not driver_user:
        return False

    if not driver_profile:
        return False

    if driver_user["status"] != USER_APPROVED:
        return False

    if driver_user["role"] not in (
        ROLE_DRIVER,
        ROLE_DISPATCHER,
    ):
        return False

    if not int(
        driver_profile["is_available"]
        or 0
    ):
        return False
    driver_city = resolve_city(
        driver_profile["available_city"]
        or ""
    )

    shipment_city = resolve_city(
        shipment["origin_city"]
        or ""
    )

    if (
        not driver_city
        or driver_city != shipment_city
    ):
        return False
    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        return False

    required_vehicle = (
        shipment["vehicle_type"]
        or VEHICLE_PRIVATE
    )

    driver_vehicle = (
        driver_profile["vehicle_type"]
        or ""
    )

    # סדר גודל רכבים
    vehicle_rank = {
        VEHICLE_PRIVATE: 1,
        VEHICLE_7_SEATS: 2,
        VEHICLE_SMALL_COMMERCIAL: 3,
        VEHICLE_LARGE_COMMERCIAL: 4,
    }

    required_rank = vehicle_rank.get(
        required_vehicle,
        1
    )

    driver_rank = vehicle_rank.get(
        driver_vehicle,
        0
    )

    if driver_rank < required_rank:
        return False

    return True


# ============================================================
# שליפת שליחים זמינים שמתאימים למשלוח
# ============================================================

def get_matching_available_drivers(
    shipment
):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                u.*,

                d.vehicle_type,
                d.vehicle_year,
                d.vehicle_description,
                d.is_available,
                d.available_city,
                d.completed_shipments,
                d.rating_sum,
                d.rating_count

            FROM users u

            JOIN driver_profiles d
                ON d.user_id = u.id

            WHERE
                u.status = ?
                AND u.role IN (?, ?)
                AND d.is_available = 1

            ORDER BY
                d.rating_count DESC,
                d.completed_shipments DESC,
                u.created_at ASC
            """,
            (
                USER_APPROVED,
                ROLE_DRIVER,
                ROLE_DISPATCHER,
            )
        ).fetchall()

    matches = []

    for row in rows:
        if driver_matches_shipment(
            row,
            row,
            shipment
        ):
            matches.append(
                row
            )

    return matches


# ============================================================
# טקסט משלוח לשליח לפני חשיפת פרטים
#
# חשוב:
# אין מספר טלפון של המפרסם
# ואין פרטים פרטיים מעבר לנדרש.
# ============================================================

def build_driver_shipment_preview(
    shipment
):
    vehicle_label = VEHICLE_LABELS.get(
        shipment["vehicle_type"],
        shipment["vehicle_type"]
        or "-"
    )

    business_name = (
        shipment["business_name"]
        or "מפרסם"
    )

    lines = [
        f"📦 משלוח – {business_name}",
        "",
        (
            f"📍 {shipment['origin_city']} "
            f"→ {shipment['destination_city']}"
        ),
        "",
        f"🏠 איסוף: {shipment['pickup_address']}",
        f"🏁 מסירה: {shipment['dropoff_address']}",
        "",
        f"🕐 זמן: {shipment['pickup_time']}",
        f"🚗 רכב נדרש: {vehicle_label}",
    ]

    if shipment["driver_help"]:
        lines.append(
            "🧤 נדרשת עזרת שליח"
        )

    if shipment["notes"]:
        lines.extend(
            [
                "",
                f"📝 {shipment['notes']}",
            ]
        )

    lines.extend(
        [
            "",
            f"💵 מחיר: {shipment['final_price']} ₪",
        ]
    )

    return "\n".join(
        lines
    )


# ============================================================
# שליחת משלוח לשליח אחד
# ============================================================

def send_shipment_to_driver(
    driver_phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return False

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        return False

    if int(
        shipment["final_price"]
        or 0
    ) <= 0:
        return False

    preview = build_driver_shipment_preview(
        shipment
    )

    send_buttons(
        driver_phone,
        preview,
        [
            (
                f"driver_interest_{shipment_id}",
                "🙋 מעוניין"
            ),
            (
                f"driver_skip_{shipment_id}",
                "לא מתאים"
            ),
        ],
        header="משלוח זמין",
        footer="הפרטים המלאים ייחשפו לאחר בחירה"
    )

    return True


# ============================================================
# הפצת משלוח לשליחים
# ============================================================

def distribute_shipment_to_drivers(
    shipment_id
):
    if not driver_side_is_enabled():
        return {
            "sent": 0,
            "reason": "driver_side_disabled",
        }

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return {
            "sent": 0,
            "reason": "shipment_not_found",
        }

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        return {
            "sent": 0,
            "reason": "shipment_not_open",
        }

    if int(
        shipment["final_price"]
        or 0
    ) <= 0:
        return {
            "sent": 0,
            "reason": "shipment_has_no_price",
        }

    drivers = get_matching_available_drivers(
        shipment
    )

    sent = 0

    for driver in drivers:
        # אם מערכת המנויים פעילה,
        # שליח רגיל חייב מנוי פעיל.
        if (
            driver["role"] == ROLE_DRIVER
            and not user_has_active_subscription(
                driver["phone"]
            )
        ):
            continue

        try:
            result = send_shipment_to_driver(
                driver["phone"],
                shipment_id
            )

            if result:
                sent += 1

        except Exception as exc:
            print(
                "SHIPMENT DISTRIBUTION ERROR:",
                driver["phone"],
                repr(exc)
            )

    with db() as conn:
        if shipment["status"] == SHIP_NEW:
            conn.execute(
                """
                UPDATE shipments
                SET
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    SHIP_OPEN,
                    now_ts(),
                    shipment_id,
                )
            )

            conn.execute(
                """
                INSERT INTO shipment_status_log (
                    shipment_id,
                    status,
                    changed_by,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    shipment_id,
                    SHIP_OPEN,
                    "system",
                    (
                        f"המשלוח הופץ ל-{sent} "
                        f"שליחים"
                    ),
                    now_ts(),
                )
            )

            conn.commit()

    return {
        "sent": sent,
        "reason": "ok",
    }


# ============================================================
# משלוחים זמינים לשליח
# ============================================================

def get_available_shipments_for_driver(
    phone,
    limit=10
):
    user = get_user(
        phone
    )

    if not user:
        return []

    profile = get_driver_profile(
        user["id"]
    )

    if not profile:
        return []

    with db() as conn:
        shipments = conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE
                status IN (?, ?)
                AND final_price > 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                SHIP_NEW,
                SHIP_OPEN,
                int(limit),
            )
        ).fetchall()

    result = []

    for shipment in shipments:
        if driver_matches_shipment(
            user,
            profile,
            shipment
        ):
            result.append(
                shipment
            )

    return result


# ============================================================
# הצגת משלוחים זמינים לשליח
# ============================================================

def show_available_shipments_for_driver(
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
        user["role"] == ROLE_DRIVER
        and not user_has_active_subscription(
            phone
        )
    ):
        send_buttons(
            phone,
            (
                "💎 אין לך מנוי פעיל.\n\n"
                "כדי לצפות ולקחת משלוחים "
                "יש לחדש את המנוי."
            ),
            [
                (
                    "driver_subscription",
                    "💎 חידוש מנוי"
                ),
                (
                    "driver_menu",
                    "↩️ חזרה"
                ),
            ],
            header="המנוי אינו פעיל"
        )

        return

    shipments = (
        get_available_shipments_for_driver(
            phone,
            10
        )
    )

    if not shipments:
        send_buttons(
            phone,
            (
                "📭 אין כרגע משלוחים זמינים "
                "שמתאימים לרכב שלך."
            ),
            [
                (
                    "driver_menu",
                    "↩️ חזרה"
                ),
            ],
            header="משלוחים זמינים"
        )

        return

    rows = []

    for shipment in shipments:
        business_name = (
            shipment["business_name"]
            or "משלוח"
        )

        route = (
            f"{shipment['origin_city']} → "
            f"{shipment['destination_city']}"
        )

        rows.append(
            (
                f"driver_view_shipment_{shipment['id']}",
                business_name[:24],
                (
                    f"{route} • "
                    f"{shipment['final_price']} ₪"
                )[:72],
            )
        )

    send_list(
        phone,
        "📦 משלוחים זמינים",
        "בחר משלוח לצפייה:",
        rows,
        button_text="פתח",
        footer="שליחובוט • שליח"
    )


# ============================================================
# צפייה במשלוח מצד שליח
# ============================================================

def show_driver_shipment(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        send_message(
            phone,
            (
                "ℹ️ המשלוח כבר אינו זמין."
            )
        )
        return

    send_buttons(
        phone,
        build_driver_shipment_preview(
            shipment
        ),
        [
            (
                f"driver_interest_{shipment_id}",
                "🙋 מעוניין"
            ),
            (
                "driver_available_shipments",
                "↩️ חזרה"
            ),
        ],
        header="פרטי משלוח"
    )


# ============================================================
# שליח לחץ "מעוניין"
# ============================================================

def start_driver_interest(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    if not user:
        return False

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    if shipment["status"] not in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        send_message(
            phone,
            "ℹ️ המשלוח כבר אינו זמין."
        )
        return True

    if (
        user["role"] == ROLE_DRIVER
        and not user_has_active_subscription(
            phone
        )
    ):
        send_message(
            phone,
            (
                "💎 נדרש מנוי פעיל "
                "כדי לקחת משלוחים."
            )
        )
        return True

    save_session(
        phone,
        "driver_interest_eta",
        {
            "shipment_id":
                shipment_id,
        }
    )

    send_buttons(
        phone,
        (
            "⏱️ תוך כמה זמן תוכל להגיע "
            "לנקודת האיסוף?"
        ),
        [
            (
                "driver_eta_15",
                "15 דקות"
            ),
            (
                "driver_eta_30",
                "30 דקות"
            ),
            (
                "driver_eta_other",
                "זמן אחר"
            ),
        ],
        header="זמן הגעה"
    )

    return True


# ============================================================
# שליחת ההתעניינות למפרסם
# ============================================================

def notify_publisher_driver_interested(
    shipment_id,
    driver_id,
    eta_text
):
    shipment = get_shipment(
        shipment_id
    )

    publisher = get_shipment_publisher(
        shipment_id
    )

    driver = get_user_by_id(
        driver_id
    )

    profile = get_driver_profile(
        driver_id
    )

    if (
        not shipment
        or not publisher
        or not driver
    ):
        return False

    rating = get_driver_rating(
        driver_id
    )

    vehicle_label = "-"

    if profile:
        vehicle_label = VEHICLE_LABELS.get(
            profile["vehicle_type"],
            profile["vehicle_type"]
            or "-"
        )

    rating_text = "חדש ללא דירוג"

    if rating["count"] > 0:
        rating_text = (
            f"{rating['average']} ⭐ "
            f"({rating['count']} דירוגים)"
        )

    send_buttons(
        publisher["phone"],
        (
            f"🙋 שליח מעוניין ב-"
            f"{shipment_title(shipment)}\n\n"
            f"👤 שליח: "
            f"{driver['full_name'] or 'שליח'}\n"
            f"🚗 רכב: {vehicle_label}\n"
            f"⏱️ זמן הגעה: {eta_text}\n"
            f"⭐ דירוג: {rating_text}\n"
            f"📦 משלוחים שהושלמו: "
            f"{rating['completed']}\n\n"
            "מספר הטלפון של השליח "
            "ייחשף רק לאחר שתבחר בו."
        ),
        [
            (
                (
                    f"publisher_choose_driver_"
                    f"{shipment_id}_{driver_id}"
                ),
                "✅ בחר שליח"
            ),
            (
                (
                    f"publisher_view_interests_"
                    f"{shipment_id}"
                ),
                "👥 כל השליחים"
            ),
        ],
        header="שליח מעוניין"
    )

    return True


# ============================================================
# שמירת זמן הגעה של שליח
# ============================================================

def submit_driver_interest(
    phone,
    shipment_id,
    eta_text
):
    user = get_user(
        phone
    )

    if not user:
        return False

    success = add_driver_interest(
        shipment_id,
        user["id"],
        eta_text
    )

    if not success:
        send_message(
            phone,
            (
                "ℹ️ לא ניתן להגיש התעניינות "
                "במשלוח הזה כרגע."
            )
        )
        return True

    clear_session(
        phone
    )

    send_message(
        phone,
        (
            "✅ ההתעניינות שלך נשלחה "
            "למפרסם.\n\n"
            "אם המפרסם יבחר בך, "
            "תקבל כאן את פרטי הקשר "
            "והודעת השיבוץ."
        )
    )

    notify_publisher_driver_interested(
        shipment_id,
        user["id"],
        eta_text
    )

    return True


# ============================================================
# טיפול בכפתורי זמן הגעה
# ============================================================

def handle_driver_interest_action(
    phone,
    action_id
):
    session = get_session(
        phone
    )

    state = session.get(
        "state",
        ""
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    if state != "driver_interest_eta":
        return False

    shipment_id = data.get(
        "shipment_id"
    )

    if not shipment_id:
        clear_session(
            phone
        )

        return False

    if action_id == "driver_eta_15":
        return submit_driver_interest(
            phone,
            int(shipment_id),
            "15 דקות"
        )

    if action_id == "driver_eta_30":
        return submit_driver_interest(
            phone,
            int(shipment_id),
            "30 דקות"
        )

    if action_id == "driver_eta_other":
        save_session(
            phone,
            "driver_interest_eta_custom",
            data
        )

        send_message(
            phone,
            (
                "⏱️ כתוב תוך כמה זמן "
                "תוכל להגיע.\n\n"
                "לדוגמה:\n"
                "45 דקות"
            )
        )

        return True

    return False


# ============================================================
# זמן הגעה חופשי
# ============================================================

def handle_driver_interest_text(
    phone,
    state,
    text
):
    if state != "driver_interest_eta_custom":
        return False

    text = clean_text(
        text
    )

    if len(text) < 2:
        send_message(
            phone,
            "❌ כתוב זמן הגעה."
        )
        return True

    session = get_session(
        phone
    )

    shipment_id = (
        session
        .get(
            "data",
            {}
        )
        .get(
            "shipment_id"
        )
    )

    if not shipment_id:
        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "❌ פרטי המשלוח אבדו. "
                "נסה שוב."
            )
        )

        return True

    return submit_driver_interest(
        phone,
        int(shipment_id),
        text
    )


# ============================================================
# סוף חלק 5A
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 5B
# בחירת שליח + חשיפת פרטים + ניהול מתעניינים
# ============================================================


# ============================================================
# הצגת כל השליחים שהתעניינו במשלוח
# ============================================================

def show_shipment_interests_to_publisher(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    publisher = get_shipment_publisher(
        shipment_id
    )

    if not publisher:
        send_message(
            phone,
            "❌ מפרסם המשלוח לא נמצא."
        )
        return

    phone = normalize_phone(
        phone
    )

    allowed = (
        normalize_phone(
            publisher["phone"]
        ) == phone
        or is_admin(phone)
        or is_dispatcher(phone)
    )

    if not allowed:
        send_message(
            phone,
            "❌ אין הרשאה לצפות בשליחים."
        )
        return

    interests = get_shipment_interests(
        shipment_id
    )

    if not interests:
        send_buttons(
            phone,
            "📭 עדיין אין שליחים שהתעניינו במשלוח.",
            [
                (
                    "customer_active_shipments",
                    "↩️ חזרה"
                ),
            ],
            header=shipment_title(
                shipment
            )
        )
        return

    rows = []

    for interest in interests:
        rating_count = int(
            interest["rating_count"]
            or 0
        )

        rating_sum = int(
            interest["rating_sum"]
            or 0
        )

        if rating_count > 0:
            rating_text = (
                f"{round(rating_sum / rating_count, 1)}⭐"
            )
        else:
            rating_text = "חדש"

        driver_name = (
            interest["full_name"]
            or "שליח"
        )

        rows.append(
            (
                (
                    f"publisher_interest_"
                    f"{shipment_id}_"
                    f"{interest['driver_id']}"
                ),
                driver_name[:24],
                (
                    f"{interest['eta_text']} • "
                    f"{rating_text} • "
                    f"{interest['completed_shipments'] or 0} משלוחים"
                )[:72],
            )
        )

    send_list(
        phone,
        "👥 שליחים מעוניינים",
        (
            f"{shipment_title(shipment)}\n"
            "בחר שליח לצפייה:"
        ),
        rows,
        button_text="פתח",
        footer="שליחובוט"
    )


# ============================================================
# פרטי שליח לפני בחירה
# ============================================================

def show_interested_driver_details(
    phone,
    shipment_id,
    driver_id
):
    shipment = get_shipment(
        shipment_id
    )

    driver = get_user_by_id(
        driver_id
    )

    profile = get_driver_profile(
        driver_id
    )

    if (
        not shipment
        or not driver
    ):
        send_message(
            phone,
            "❌ הפרטים לא נמצאו."
        )
        return

    rating = get_driver_rating(
        driver_id
    )

    vehicle_label = "-"

    if profile:
        vehicle_label = VEHICLE_LABELS.get(
            profile["vehicle_type"],
            profile["vehicle_type"]
            or "-"
        )

    eta_text = "-"

    with db() as conn:
        interest = conn.execute(
            """
            SELECT *
            FROM shipment_interests
            WHERE
                shipment_id = ?
                AND driver_id = ?
            LIMIT 1
            """,
            (
                shipment_id,
                driver_id,
            )
        ).fetchone()

    if interest:
        eta_text = (
            interest["eta_text"]
            or "-"
        )

    if rating["count"] > 0:
        rating_text = (
            f"{rating['average']} ⭐ "
            f"({rating['count']} דירוגים)"
        )
    else:
        rating_text = "חדש ללא דירוג"

    send_buttons(
        phone,
        (
            "🚗 פרטי השליח\n\n"
            f"👤 {driver['full_name'] or 'שליח'}\n"
            f"🚘 רכב: {vehicle_label}\n"
            f"📅 שנת רכב: "
            f"{profile['vehicle_year'] if profile else '-'}\n"
            f"⏱️ זמן הגעה: {eta_text}\n"
            f"⭐ דירוג: {rating_text}\n"
            f"📦 משלוחים שהושלמו: "
            f"{rating['completed']}\n\n"
            "📱 מספר הטלפון ייחשף "
            "רק לאחר בחירת השליח."
        ),
        [
            (
                (
                    f"publisher_choose_driver_"
                    f"{shipment_id}_{driver_id}"
                ),
                "✅ בחר שליח"
            ),
            (
                (
                    f"publisher_view_interests_"
                    f"{shipment_id}"
                ),
                "↩️ חזרה"
            ),
        ],
        header=shipment_title(
            shipment
        )
    )


# ============================================================
# בחירת שליח ע"י המפרסם / מנהל / סדרן
# ============================================================

def choose_driver_for_shipment(
    phone,
    shipment_id,
    driver_id
):
    phone = normalize_phone(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    publisher = get_shipment_publisher(
        shipment_id
    )

    driver = get_user_by_id(
        driver_id
    )

    if (
        not publisher
        or not driver
    ):
        send_message(
            phone,
            "❌ פרטי המשתמש אינם זמינים."
        )
        return True

    is_publisher = (
        normalize_phone(
            publisher["phone"]
        )
        == phone
    )

    if not (
        is_publisher
        or is_admin(phone)
        or is_dispatcher(phone)
    ):
        send_message(
            phone,
            "❌ אין לך הרשאה לבחור שליח."
        )
        return True

    try:
        assign_driver_to_shipment(
            shipment_id,
            driver_id,
            phone
        )

    except Exception as exc:
        send_message(
            phone,
            (
                "❌ לא ניתן לבחור את השליח.\n"
                f"{str(exc)}"
            )
        )

        return True

    shipment = get_shipment(
        shipment_id
    )

    # --------------------------------------------------------
    # הודעה לשליח שנבחר
    # --------------------------------------------------------

    send_buttons(
    driver["phone"],
    (
        "🎉 נבחרת למשלוח!\n\n"
        f"{shipment_title(shipment)}\n\n"
        f"📍 מוצא: {shipment['origin_city']}\n"
        f"🏠 איסוף: {shipment['pickup_address']}\n\n"
        f"📍 יעד: {shipment['destination_city']}\n"
        f"🏠 מסירה: {shipment['dropoff_address']}\n\n"
        f"🕐 זמן: {shipment['pickup_time']}\n"
        f"💵 מחיר: {shipment['final_price']} ₪\n\n"
        f"🏢 מפרסם: "
        f"{publisher['business_name'] or publisher['full_name'] or '-'}\n"
        f"📱 טלפון מפרסם: {publisher['phone']}\n\n"
        "בסיום המשלוח לחץ על הכפתור למטה.\n"
        "⭐ לאחר הסיום המפרסם יוכל לדרג אותך."
    ),
    [
        (
            f"driver_complete_{shipment_id}",
            "✅ סיימתי משלוח"
        ),
    ],
    header="🚚 משלוח פעיל"
)

    # --------------------------------------------------------
    # הודעה למפרסם + מספר השליח
    # --------------------------------------------------------

    send_message(
        publisher["phone"],
        (
            "✅ השליח נבחר בהצלחה.\n\n"
            f"{shipment_title(shipment)}\n\n"
            f"👤 שליח: "
            f"{driver['full_name'] or '-'}\n"
            f"📱 טלפון שליח: "
            f"{driver['phone']}\n\n"
            "הפרטים נחשפו לשני הצדדים."
        )
    )

    # --------------------------------------------------------
    # הודעה למנהל עם שני מספרי הטלפון
    # --------------------------------------------------------

    if ADMIN_PHONE:
        send_message(
            ADMIN_PHONE,
            (
                "🚚 משלוח נתפס\n\n"
                f"{shipment_title(shipment)}\n\n"
                f"🏢 מפרסם: "
                f"{publisher['business_name'] or publisher['full_name'] or '-'}\n"
                f"📱 מפרסם: "
                f"{publisher['phone']}\n\n"
                f"👤 שליח: "
                f"{driver['full_name'] or '-'}\n"
                f"📱 שליח: "
                f"{driver['phone']}\n\n"
                f"📍 {shipment['origin_city']} → "
                f"{shipment['destination_city']}\n"
                f"💵 {shipment['final_price']} ₪"
            )
        )

    # --------------------------------------------------------
    # אם סדרן בחר את השליח
    # שולחים לשליח הודעה מפורשת שהסדרן בחר בו
    # --------------------------------------------------------

    if is_dispatcher(
        phone
    ):
        send_message(
            driver["phone"],
            (
                "👨‍💼 הסדרן בחר בך למשלוח.\n"
                "פרטי המשלוח ופרטי המפרסם "
                "נשלחו אליך בפרטי."
            )
        )

    return True


# ============================================================
# משלוחים ששובצו לשליח
# ============================================================

def show_my_assigned_shipments(
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
                assigned_driver_id = ?
                AND status = ?
            ORDER BY assigned_at DESC
            LIMIT 10
            """,
            (
                user["id"],
                SHIP_ASSIGNED,
            )
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "📭 אין לך כרגע משלוחים פעילים.",
            [
                (
                    "driver_menu",
                    "↩️ חזרה"
                ),
            ],
            header="🚚 המשלוחים שלי"
        )
        return

    menu_rows = []

    for shipment in rows:
        menu_rows.append(
            (
                (
                    f"driver_assigned_shipment_"
                    f"{shipment['id']}"
                ),
                (
                    shipment["business_name"]
                    or "משלוח"
                )[:24],
                (
                    f"{shipment['origin_city']} → "
                    f"{shipment['destination_city']} • "
                    f"{shipment['final_price']} ₪"
                )[:72],
            )
        )

    send_list(
        phone,
        "🚚 המשלוחים שלי",
        "בחר משלוח:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט • שליח"
    )


# ============================================================
# פרטי משלוח לאחר שיבוץ לשליח
# ============================================================

def show_assigned_shipment_to_driver(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    if (
        shipment["assigned_driver_id"]
        != user["id"]
        and not is_admin(phone)
        and not is_dispatcher(phone)
    ):
        send_message(
            phone,
            "❌ אין הרשאה לצפות במשלוח."
        )
        return

    publisher = get_shipment_publisher(
        shipment_id
    )

    text = build_shipment_details_text(
        shipment,
        include_publisher_phone=True,
        include_driver=False
    )

    if publisher:
        text += (
            "\n\n"
            f"🏢 מפרסם: "
            f"{publisher['business_name'] or publisher['full_name'] or '-'}"
        )

    send_buttons(
        phone,
        text,
        [
            (
                f"driver_complete_{shipment_id}",
                "✅ המשלוח הושלם"
            ),
            (
                "driver_my_shipments",
                "↩️ חזרה"
            ),
        ],
        header="🚚 משלוח פעיל"
    )


# ============================================================
# טיפול בכפתורי חלק 5
# ============================================================

def handle_shipment_driver_actions(
    phone,
    action_id
):
    # צפייה במשלוח זמין
    if action_id.startswith(
        "driver_view_shipment_"
    ):
        raw_id = action_id.replace(
            "driver_view_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_driver_shipment(
                phone,
                int(raw_id)
            )
            return True

    # מעוניין
    if action_id.startswith(
        "driver_interest_"
    ):
        raw_id = action_id.replace(
            "driver_interest_",
            "",
            1
        )

        if raw_id.isdigit():
            return start_driver_interest(
                phone,
                int(raw_id)
            )

    # לא מתאים
    if action_id.startswith(
        "driver_skip_"
    ):
        send_message(
            phone,
            "👍 המשלוח הוסר מהמסך שלך."
        )
        return True

    # רשימת מתעניינים
    if action_id.startswith(
        "publisher_view_interests_"
    ):
        raw_id = action_id.replace(
            "publisher_view_interests_",
            "",
            1
        )

        if raw_id.isdigit():
            show_shipment_interests_to_publisher(
                phone,
                int(raw_id)
            )
            return True

    # צפייה בשליח שהתעניין
    if action_id.startswith(
        "publisher_interest_"
    ):
        raw = action_id.replace(
            "publisher_interest_",
            "",
            1
        )

        parts = raw.split(
            "_"
        )

        if (
            len(parts) == 2
            and parts[0].isdigit()
            and parts[1].isdigit()
        ):
            show_interested_driver_details(
                phone,
                int(parts[0]),
                int(parts[1])
            )
            return True

    # בחירת שליח
    if action_id.startswith(
        "publisher_choose_driver_"
    ):
        raw = action_id.replace(
            "publisher_choose_driver_",
            "",
            1
        )

        parts = raw.split(
            "_"
        )

        if (
            len(parts) == 2
            and parts[0].isdigit()
            and parts[1].isdigit()
        ):
            return choose_driver_for_shipment(
                phone,
                int(parts[0]),
                int(parts[1])
            )

    # משלוח פעיל של השליח
    if action_id.startswith(
        "driver_assigned_shipment_"
    ):
        raw_id = action_id.replace(
            "driver_assigned_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_assigned_shipment_to_driver(
                phone,
                int(raw_id)
            )
            return True

    return False


# ============================================================
# סוף חלק 5
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 6A
# סיום משלוח + דירוג שליח + ניהול משלוח למפרסם
# ============================================================


# ============================================================
# משלוחים פעילים של מפרסם
# ============================================================

def get_customer_active_shipments(
    phone,
    limit=10
):
    user = get_user(
        phone
    )

    if not user:
        return []

    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE
                publisher_id = ?
                AND status IN (?, ?, ?, ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                user["id"],
                SHIP_NEW,
                SHIP_OPEN,
                SHIP_ASSIGNED,
                SHIP_NEEDS_PRICE,
                int(limit),
            )
        ).fetchall()


# ============================================================
# הצגת משלוחים פעילים למפרסם
# ============================================================

def show_customer_active_shipments(
    phone
):
    shipments = (
        get_customer_active_shipments(
            phone,
            10
        )
    )

    if not shipments:
        send_buttons(
            phone,
            "📭 אין לך כרגע משלוחים פעילים.",
            [
                (
                    "customer_new_shipment",
                    "📦 משלוח חדש"
                ),
                (
                    "customer_menu",
                    "↩️ חזרה"
                ),
            ],
            header="🚚 משלוחים פעילים"
        )
        return

    rows = []

    for shipment in shipments:
        status_labels = {
            SHIP_NEW:
                "חדש",

            SHIP_OPEN:
                "ממתין לשליח",

            SHIP_ASSIGNED:
                "שובץ שליח",

            SHIP_NEEDS_PRICE:
                "ממתין למחיר",
        }

        status_text = status_labels.get(
            shipment["status"],
            shipment["status"]
        )

        rows.append(
            (
                (
                    f"customer_shipment_"
                    f"{shipment['id']}"
                ),
                (
                    shipment["business_name"]
                    or "משלוח"
                )[:24],
                (
                    f"{shipment['origin_city']} → "
                    f"{shipment['destination_city']} • "
                    f"{status_text}"
                )[:72],
            )
        )

    send_list(
        phone,
        "🚚 משלוחים פעילים",
        "בחר משלוח:",
        rows,
        button_text="פתח",
        footer="שליחובוט"
    )


# ============================================================
# הצגת משלוח פעיל למפרסם
# ============================================================

def show_customer_shipment(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    if (
        shipment["publisher_id"]
        != user["id"]
        and not is_admin(phone)
        and not is_dispatcher(phone)
    ):
        send_message(
            phone,
            "❌ אין הרשאה לצפות במשלוח."
        )
        return

    text = build_shipment_details_text(
        shipment,
        include_publisher_phone=False,
        include_driver=True
    )

    buttons = []

    if shipment["status"] in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        buttons.append(
            (
                (
                    f"publisher_view_interests_"
                    f"{shipment_id}"
                ),
                "👥 שליחים"
            )
        )

        buttons.append(
            (
                (
                    f"customer_cancel_shipment_"
                    f"{shipment_id}"
                ),
                "❌ ביטול"
            )
        )

    elif shipment["status"] == SHIP_ASSIGNED:
        buttons.append(
            (
                (
                    f"customer_complete_"
                    f"{shipment_id}"
                ),
                "✅ הסתיים"
            )
        )

    buttons.append(
        (
            "customer_active_shipments",
            "↩️ חזרה"
        )
    )

    # WhatsApp מאפשר עד 3 כפתורים.
    send_buttons(
        phone,
        text,
        buttons[:3],
        header=shipment_title(
            shipment
        )
    )


# ============================================================
# סיום משלוח מצד השליח
# ============================================================

def driver_finish_shipment(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    if (
        shipment["assigned_driver_id"]
        != user["id"]
    ):
        send_message(
            phone,
            (
                "❌ המשלוח אינו משויך "
                "אליך."
            )
        )
        return True

    if not complete_shipment(
        shipment_id,
        phone
    ):
        send_message(
            phone,
            (
                "❌ לא ניתן לסיים את "
                "המשלוח כרגע."
            )
        )
        return True

    send_message(
        phone,
        (
            "✅ המשלוח סומן כהושלם.\n\n"
            "המשלוח נוסף להיסטוריה שלך."
        )
    )

    notify_publisher_shipment_completed(
        shipment_id
    )

    return True


# ============================================================
# סיום משלוח מצד המפרסם
# ============================================================

def customer_finish_shipment(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    if (
        shipment["publisher_id"]
        != user["id"]
        and not is_admin(phone)
        and not is_dispatcher(phone)
    ):
        send_message(
            phone,
            "❌ אין הרשאה לסיים משלוח זה."
        )
        return True

    if not complete_shipment(
        shipment_id,
        phone
    ):
        send_message(
            phone,
            (
                "❌ לא ניתן לסיים את "
                "המשלוח כרגע."
            )
        )
        return True

    send_message(
        phone,
        "✅ המשלוח סומן כהושלם."
    )

    send_rating_prompt(
        phone,
        shipment_id
    )

    return True


# ============================================================
# הודעה למפרסם מיד כשהמשלוח הושלם
# כולל כפתור דירוג - בלי צורך לחפש בהיסטוריה
# ============================================================

def notify_publisher_shipment_completed(
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    publisher = get_shipment_publisher(
        shipment_id
    )

    if (
        not shipment
        or not publisher
    ):
        return False

    send_message(
        publisher["phone"],
        (
            "✅ המשלוח סומן כהושלם.\n\n"
            f"{shipment_title(shipment)}\n"
            f"📍 {shipment['origin_city']} → "
            f"{shipment['destination_city']}\n\n"
            "נשמח אם תדרג את השליח."
        )
    )

    send_rating_prompt(
        publisher["phone"],
        shipment_id
    )

    return True


# ============================================================
# כפתור דירוג מיידי
# ============================================================

def send_rating_prompt(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        return

    if not shipment[
        "assigned_driver_id"
    ]:
        return

    driver = get_user_by_id(
        shipment["assigned_driver_id"]
    )

    if not driver:
        return

    send_buttons(
        phone,
        (
            "✅ המשלוח סומן כהושלם.\n\n"
            f"📦 {shipment_title(shipment)}\n"
            f"📍 {shipment['origin_city']} → "
            f"{shipment['destination_city']}\n\n"
            "⭐ איך היית מדרג את השליח?\n"
            f"👤 שליח: {driver['full_name'] or '-'}\n"
            f"📱 טלפון: {driver['phone']}"
        ),
        [
            (
                f"rate_open_{shipment_id}",
                "⭐ דרג שליח"
            ),
            (
                "customer_menu",
                "לא עכשיו"
            ),
        ],
        header="⭐ דירוג שליח"
    )

# ============================================================
# מסך בחירת דירוג
# בגלל מגבלת 3 כפתורים ב-WhatsApp,
# משתמשים ברשימה של 1 עד 5.
# ============================================================

def show_rating_choices(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    send_list(
        phone,
        "⭐ דירוג שליח",
        "בחר דירוג:",
        [
            (
                f"rate_{shipment_id}_5",
                "⭐⭐⭐⭐⭐ 5",
                "מצוין",
            ),
            (
                f"rate_{shipment_id}_4",
                "⭐⭐⭐⭐ 4",
                "טוב מאוד",
            ),
            (
                f"rate_{shipment_id}_3",
                "⭐⭐⭐ 3",
                "בסדר",
            ),
            (
                f"rate_{shipment_id}_2",
                "⭐⭐ 2",
                "לא כל כך טוב",
            ),
            (
                f"rate_{shipment_id}_1",
                "⭐ 1",
                "לא טוב",
            ),
        ],
        button_text="בחר דירוג",
        footer="הדירוג ניתן פעם אחת בלבד"
    )


# ============================================================
# שמירת דירוג
# ============================================================

def submit_driver_rating(
    phone,
    shipment_id,
    rating
):
    try:
        rate_shipment_driver(
            shipment_id,
            phone,
            rating
        )

    except Exception as exc:
        send_message(
            phone,
            (
                "❌ לא ניתן לשמור את הדירוג.\n"
                f"{str(exc)}"
            )
        )

        return True

    send_message(
        phone,
        (
            f"⭐ תודה! דירגת את השליח "
            f"ב-{rating} מתוך 5."
        )
    )

    driver = get_shipment_driver(
        shipment_id
    )

    if driver:
        send_message(
            driver["phone"],
            (
                "⭐ התקבל דירוג חדש "
                "על משלוח שהשלמת.\n\n"
                f"דירוג: {rating}/5"
            )
        )

    return True


# ============================================================
# היסטוריית משלוחים של מפרסם
# ============================================================

def show_customer_history(
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
                publisher_id = ?
                AND status IN (?, ?)
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            (
                user["id"],
                SHIP_COMPLETED,
                SHIP_CANCELLED,
            )
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "📭 עדיין אין היסטוריית משלוחים.",
            [
                (
                    "customer_menu",
                    "↩️ חזרה"
                ),
            ],
            header="📋 היסטוריה"
        )
        return

    menu_rows = []

    for shipment in rows:
        status_text = (
            "✅ הושלם"
            if shipment["status"] == SHIP_COMPLETED
            else "❌ בוטל"
        )

        menu_rows.append(
            (
                (
                    f"customer_history_shipment_"
                    f"{shipment['id']}"
                ),
                (
                    shipment["business_name"]
                    or "משלוח"
                )[:24],
                (
                    f"{shipment['origin_city']} → "
                    f"{shipment['destination_city']} • "
                    f"{status_text}"
                )[:72],
            )
        )

    send_list(
        phone,
        "📋 היסטוריית משלוחים",
        "בחר משלוח:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט"
    )


# ============================================================
# צפייה במשלוח מההיסטוריה
# ============================================================

def show_customer_history_shipment(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    if (
        shipment["publisher_id"]
        != user["id"]
    ):
        send_message(
            phone,
            "❌ אין הרשאה לצפות במשלוח."
        )
        return

    text = build_shipment_details_text(
        shipment,
        include_publisher_phone=False,
        include_driver=True
    )

    buttons = []

    if (
        shipment["status"] == SHIP_COMPLETED
        and not int(
            shipment["rating"]
            or 0
        )
    ):
        buttons.append(
            (
                f"rate_open_{shipment_id}",
                "⭐ דרג שליח"
            )
        )

    buttons.append(
        (
            "customer_history",
            "↩️ חזרה"
        )
    )

    send_buttons(
        phone,
        text,
        buttons[:3],
        header="📋 פרטי משלוח"
    )


# ============================================================
# ביטול משלוח ע"י מפרסם
# ============================================================

def customer_cancel_shipment(
    phone,
    shipment_id
):
    user = get_user(
        phone
    )

    shipment = get_shipment(
        shipment_id
    )

    if (
        not user
        or not shipment
    ):
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    if (
        shipment["publisher_id"]
        != user["id"]
    ):
        send_message(
            phone,
            "❌ אין הרשאה לבטל משלוח זה."
        )
        return True

    if shipment["status"] == SHIP_ASSIGNED:
        send_buttons(
            phone,
            (
                "⚠️ כבר נבחר שליח למשלוח.\n\n"
                "האם אתה בטוח שברצונך לבטל?"
            ),
            [
                (
                    f"customer_cancel_confirm_{shipment_id}",
                    "כן, בטל"
                ),
                (
                    f"customer_shipment_{shipment_id}",
                    "לא"
                ),
            ],
            header="אישור ביטול"
        )

        return True

    if cancel_shipment(
        shipment_id,
        phone,
        "בוטל על ידי המפרסם"
    ):
        send_message(
            phone,
            "❌ המשלוח בוטל."
        )

    return True


# ============================================================
# אישור ביטול לאחר שכבר שובץ שליח
# ============================================================

def customer_confirm_cancel_shipment(
    phone,
    shipment_id
):
    shipment = get_shipment(
        shipment_id
    )

    user = get_user(
        phone
    )

    if (
        not shipment
        or not user
    ):
        return True

    if (
        shipment["publisher_id"]
        != user["id"]
    ):
        return True

    driver = None

    if shipment[
        "assigned_driver_id"
    ]:
        driver = get_user_by_id(
            shipment[
                "assigned_driver_id"
            ]
        )

    success = cancel_shipment(
        shipment_id,
        phone,
        (
            "בוטל על ידי המפרסם "
            "לאחר שיבוץ שליח"
        )
    )

    if not success:
        send_message(
            phone,
            "❌ לא ניתן לבטל את המשלוח."
        )
        return True

    send_message(
        phone,
        "❌ המשלוח בוטל."
    )

    if driver:
        send_message(
            driver["phone"],
            (
                "⚠️ המשלוח שאליו שובצת בוטל "
                "על ידי המפרסם."
            )
        )

    return True


# ============================================================
# טיפול בכפתורי חלק 6
# ============================================================

def handle_customer_shipment_actions(
    phone,
    action_id
):
    if action_id.startswith(
        "customer_shipment_"
    ):
        raw_id = action_id.replace(
            "customer_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_customer_shipment(
                phone,
                int(raw_id)
            )
            return True

    if action_id.startswith(
        "customer_complete_"
    ):
        raw_id = action_id.replace(
            "customer_complete_",
            "",
            1
        )

        if raw_id.isdigit():
            return customer_finish_shipment(
                phone,
                int(raw_id)
            )

    if action_id.startswith(
        "driver_complete_"
    ):
        raw_id = action_id.replace(
            "driver_complete_",
            "",
            1
        )

        if raw_id.isdigit():
            return driver_finish_shipment(
                phone,
                int(raw_id)
            )

    if action_id.startswith(
        "rate_open_"
    ):
        raw_id = action_id.replace(
            "rate_open_",
            "",
            1
        )

        if raw_id.isdigit():
            show_rating_choices(
                phone,
                int(raw_id)
            )
            return True

    if action_id.startswith(
        "rate_"
    ):
        raw = action_id.replace(
            "rate_",
            "",
            1
        )

        parts = raw.split(
            "_"
        )

        if (
            len(parts) == 2
            and parts[0].isdigit()
            and parts[1].isdigit()
        ):
            shipment_id = int(
                parts[0]
            )

            rating = int(
                parts[1]
            )

            if 1 <= rating <= 5:
                return submit_driver_rating(
                    phone,
                    shipment_id,
                    rating
                )

    if action_id.startswith(
        "customer_history_shipment_"
    ):
        raw_id = action_id.replace(
            "customer_history_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_customer_history_shipment(
                phone,                int(raw_id)
            )
            return True

    if action_id.startswith(
        "customer_cancel_shipment_"
    ):
        raw_id = action_id.replace(
            "customer_cancel_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            return customer_cancel_shipment(
                phone,
                int(raw_id)
            )

    if action_id.startswith(
        "customer_cancel_confirm_"
    ):
        raw_id = action_id.replace(
            "customer_cancel_confirm_",
            "",
            1
        )

        if raw_id.isdigit():
            return customer_confirm_cancel_shipment(
                phone,
                int(raw_id)
            )

    return False


# ============================================================
# חלק 6B
# ניהול משלוחים למנהל ולסדרן
# ============================================================


# ============================================================
# שליפת משלוחים לפי סטטוס למנהל
# ============================================================

def get_shipments_by_status(
    statuses,
    limit=10
):
    if not statuses:
        return []

    placeholders = ",".join(
        "?"
        for _ in statuses
    )

    sql = (
        "SELECT * "
        "FROM shipments "
        f"WHERE status IN ({placeholders}) "
        "ORDER BY updated_at DESC "
        "LIMIT ?"
    )

    params = list(
        statuses
    )

    params.append(
        int(limit)
    )

    with db() as conn:
        return conn.execute(
            sql,
            params
        ).fetchall()


# ============================================================
# הצגת רשימת משלוחים למנהל / סדרן
# ============================================================

def show_management_shipments(
    phone,
    statuses,
    title
):
    if not (
        is_admin(phone)
        or is_dispatcher(phone)
    ):
        return

    shipments = get_shipments_by_status(
        statuses,
        10
    )

    if not shipments:
        send_buttons(
            phone,
            "📭 אין כרגע משלוחים בקטגוריה הזאת.",
            [
                (
                    "admin_shipments",
                    "↩️ חזרה"
                ),
            ],
            header=title
        )
        return

    rows = []

    for shipment in shipments:
        business_name = (
            shipment["business_name"]
            or "משלוח"
        )

        rows.append(
            (
                f"manage_shipment_{shipment['id']}",
                business_name[:24],
                (
                    f"{shipment['origin_city']} → "
                    f"{shipment['destination_city']} • "
                    f"{shipment['final_price'] or 0} ₪"
                )[:72],
            )
        )

    send_list(
        phone,
        title,
        "בחר משלוח:",
        rows,
        button_text="פתח",
        footer="שליחובוט • ניהול"
    )


# ============================================================
# צפייה במשלוח מצד מנהל / סדרן
# ============================================================

def show_management_shipment(
    phone,
    shipment_id
):
    if not (
        is_admin(phone)
        or is_dispatcher(phone)
    ):
        return

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return

    text = build_shipment_details_text(
        shipment,
        include_publisher_phone=True,
        include_driver=True
    )

    buttons = []

    if shipment["status"] in (
        SHIP_NEW,
        SHIP_OPEN,
    ):
        buttons.append(
            (
                f"publisher_view_interests_{shipment_id}",
                "👥 מתעניינים"
            )
        )

    if shipment["status"] == SHIP_NEEDS_PRICE:
        buttons.append(
            (
                f"admin_price_shipment_{shipment_id}",
                "💰 הוסף מחיר"
            )
        )

    if shipment["status"] == SHIP_ASSIGNED:
        buttons.append(
            (
                f"admin_complete_shipment_{shipment_id}",
                "✅ סיום"
            )
        )

    buttons.append(
        (
            "admin_shipments",
            "↩️ חזרה"
        )
    )

    send_buttons(
        phone,
        text,
        buttons[:3],
        header="📦 ניהול משלוח"
    )


# ============================================================
# סיום משלוח ע"י מנהל / סדרן
# ============================================================

def management_complete_shipment(
    phone,
    shipment_id
):
    if not (
        is_admin(phone)
        or is_dispatcher(phone)
    ):
        return False

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    if not complete_shipment(
        shipment_id,
        phone
    ):
        send_message(
            phone,
            "❌ לא ניתן לסיים את המשלוח."
        )
        return True

    send_message(
        phone,
        "✅ המשלוח סומן כהושלם."
    )

    notify_publisher_shipment_completed(
        shipment_id
    )

    return True


# ============================================================
# טיפול בכפתורי ניהול משלוחים
# ============================================================

def handle_management_shipment_actions(
    phone,
    action_id
):
    if action_id == "admin_shipments_new":
        show_management_shipments(
            phone,
            [
                SHIP_NEW,
                SHIP_OPEN,
            ],
            "🆕 משלוחים חדשים"
        )
        return True

    if action_id == "admin_shipments_assigned":
        show_management_shipments(
            phone,
            [
                SHIP_ASSIGNED,
            ],
            "🚚 משלוחים ששובצו"
        )
        return True

    if action_id == "admin_shipments_completed":
        show_management_shipments(
            phone,
            [
                SHIP_COMPLETED,
            ],
            "✅ משלוחים שהושלמו"
        )
        return True

    if action_id == "admin_shipments_cancelled":
        show_management_shipments(
            phone,
            [
                SHIP_CANCELLED,
            ],
            "❌ משלוחים שבוטלו"
        )
        return True

    if action_id == "admin_shipments_no_price":
        show_management_shipments(
            phone,
            [
                SHIP_NEEDS_PRICE,
            ],
            "💰 ממתינים לתמחור"
        )
        return True

    if action_id.startswith(
        "manage_shipment_"
    ):
        raw_id = action_id.replace(
            "manage_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_management_shipment(
                phone,
                int(raw_id)
            )
            return True

    if action_id.startswith(
        "admin_view_shipment_"
    ):
        raw_id = action_id.replace(
            "admin_view_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_management_shipment(
                phone,
                int(raw_id)
            )
            return True

    if action_id.startswith(
        "admin_complete_shipment_"
    ):
        raw_id = action_id.replace(
            "admin_complete_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            return management_complete_shipment(
                phone,
                int(raw_id)
            )

    return False


# ============================================================
# סוף חלק 6
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 7A
# מחירון + תמחור משלוחים + ערים וכינויים
# ============================================================


# ============================================================
# שמירת מחיר בין שתי ערים
# ============================================================

def save_route_price(
    phone,
    city_from,
    city_to,
    price
):
    if not can_manage_prices(
        phone
    ):
        return False

    city_from = resolve_city(
        city_from
    )

    city_to = resolve_city(
        city_to
    )

    if not city_from:
        raise ValueError(
            "עיר מוצא אינה תקינה"
        )

    if not city_to:
        raise ValueError(
            "עיר יעד אינה תקינה"
        )

    if city_from == city_to:
        raise ValueError(
            "עיר המוצא והיעד זהות"
        )

    try:
        price = int(
            price
        )
    except Exception:
        raise ValueError(
            "מחיר לא תקין"
        )

    if price <= 0:
        raise ValueError(
            "המחיר חייב להיות גדול מאפס"
        )

    phone = normalize_phone(
        phone
    )

    with db() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM route_prices
            WHERE
                (
                    city_from = ?
                    AND city_to = ?
                )
                OR
                (
                    city_from = ?
                    AND city_to = ?
                )
            LIMIT 1
            """,
            (
                city_from,
                city_to,
                city_to,
                city_from,
            )
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE route_prices
                SET
                    city_from = ?,
                    city_to = ?,
                    price = ?,
                    updated_by = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    city_from,
                    city_to,
                    price,
                    phone,
                    now_ts(),
                    existing["id"],
                )
            )

            route_id = int(
                existing["id"]
            )

            action_name = (
                "UPDATE_ROUTE_PRICE"
            )

        else:
            cursor = conn.execute(
                """
                INSERT INTO route_prices (
                    city_from,
                    city_to,
                    price,
                    created_by,
                    updated_by,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    city_from,
                    city_to,
                    price,
                    phone,
                    phone,
                    now_ts(),
                    now_ts(),
                )
            )

            route_id = int(
                cursor.lastrowid
            )

            action_name = (
                "CREATE_ROUTE_PRICE"
            )

        conn.commit()

    log_action(
        phone,
        action_name,
        "route_price",
        route_id,
        (
            f"{city_from} -> "
            f"{city_to} = {price}"
        )
    )

    return route_id


# ============================================================
# קבלת מחיר מסלול
# ============================================================

def get_route_price(
    city_from,
    city_to
):
    city_from = resolve_city(
        city_from
    )

    city_to = resolve_city(
        city_to
    )

    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM route_prices
            WHERE
                (
                    city_from = ?
                    AND city_to = ?
                )
                OR
                (
                    city_from = ?
                    AND city_to = ?
                )
            LIMIT 1
            """,
            (
                city_from,
                city_to,
                city_to,
                city_from,
            )
        ).fetchone()

    return row


# ============================================================
# מחיקת מחיר מסלול
# ============================================================

def delete_route_price(
    phone,
    city_from,
    city_to
):
    if not can_manage_prices(
        phone
    ):
        return False

    row = get_route_price(
        city_from,
        city_to
    )

    if not row:
        return False

    with db() as conn:
        conn.execute(
            """
            DELETE FROM route_prices
            WHERE id = ?
            """,
            (
                row["id"],
            )
        )

        conn.commit()

    log_action(
        phone,
        "DELETE_ROUTE_PRICE",
        "route_price",
        row["id"],
        (
            f"{row['city_from']} -> "
            f"{row['city_to']}"
        )
    )

    return True


# ============================================================
# התחלת הוספה / עדכון מחיר
# ============================================================

def start_price_add(phone):
    if not can_manage_prices(
        phone
    ):
        return

    save_session(
        phone,
        "price_add_from",
        {}
    )

    send_message(
        phone,
        (
            "💰 הוספה / עדכון מחיר\n\n"
            "שלח את עיר המוצא."
        )
    )


# ============================================================
# התחלת בדיקת מחיר
# ============================================================

def start_price_check(phone):
    if not can_manage_prices(
        phone
    ):
        return

    save_session(
        phone,
        "price_check_from",
        {}
    )

    send_message(
        phone,
        (
            "🔎 בדיקת מחיר\n\n"
            "שלח את עיר המוצא."
        )
    )


# ============================================================
# התחלת מחיקת מחיר
# ============================================================

def start_price_delete(phone):
    if not can_manage_prices(
        phone
    ):
        return

    save_session(
        phone,
        "price_delete_from",
        {}
    )

    send_message(
        phone,
        (
            "🗑️ מחיקת מחיר\n\n"
            "שלח את עיר המוצא."
        )
    )


# ============================================================
# טיפול בטקסט של המחירון
# ============================================================

def handle_price_management_state(
    phone,
    state,
    text
):
    if not can_manage_prices(
        phone
    ):
        return False

    text = clean_text(
        text
    )

    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # --------------------------------------------------------
    # הוספה - עיר מוצא
    # --------------------------------------------------------

    if state == "price_add_from":
        city_from = resolve_city(
            text
        )

        update_session_data(
            phone,
            "price_add_to",
            city_from=city_from
        )

        send_message(
            phone,
            (
                f"📍 מוצא: {city_from}\n\n"
                "שלח את עיר היעד."
            )
        )

        return True

    # --------------------------------------------------------
    # הוספה - עיר יעד
    # --------------------------------------------------------

    if state == "price_add_to":
        city_to = resolve_city(
            text
        )

        update_session_data(
            phone,
            "price_add_amount",
            city_to=city_to
        )

        send_message(
            phone,
            (
                f"📍 יעד: {city_to}\n\n"
                "💰 שלח את המחיר בשקלים.\n"
                "לדוגמה: 85"
            )
        )

        return True

    # --------------------------------------------------------
    # הוספה - מחיר
    # --------------------------------------------------------

    if state == "price_add_amount":
        clean_amount = re.sub(
            r"[^\d]",
            "",
            text
        )

        if not clean_amount:
            send_message(
                phone,
                "❌ שלח מחיר במספרים."
            )
            return True

        try:
            route_id = save_route_price(
                phone,
                data.get(
                    "city_from",
                    ""
                ),
                data.get(
                    "city_to",
                    ""
                ),
                int(clean_amount)
            )

        except Exception as exc:
            send_message(
                phone,
                (
                    "❌ לא ניתן לשמור מחיר.\n"
                    f"{str(exc)}"
                )
            )
            return True

        city_from = resolve_city(
            data.get(
                "city_from",
                ""
            )
        )

        city_to = resolve_city(
            data.get(
                "city_to",
                ""
            )
        )

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ המחיר נשמר.\n\n"
                f"📍 {city_from} ↔ {city_to}\n"
                f"💰 {int(clean_amount)} ₪"
            )
        )

        # אחרי הוספת מחיר, ננסה להפעיל אוטומטית
        # משלוחים שממתינים בדיוק למסלול הזה.
        activate_waiting_shipments_for_route(
            city_from,
            city_to,
            phone
        )

        return True

    # --------------------------------------------------------
    # בדיקת מחיר - מוצא
    # --------------------------------------------------------

    if state == "price_check_from":
        city_from = resolve_city(
            text
        )

        update_session_data(
            phone,
            "price_check_to",
            city_from=city_from
        )

        send_message(
            phone,
            "📍 שלח את עיר היעד."
        )

        return True

    # --------------------------------------------------------
    # בדיקת מחיר - יעד
    # --------------------------------------------------------

    if state == "price_check_to":
        city_from = data.get(
            "city_from",
            ""
        )

        city_to = resolve_city(
            text
        )

        row = get_route_price(
            city_from,
            city_to
        )

        clear_session(
            phone
        )

        if not row:
            send_message(
                phone,
                (
                    "❌ המסלול עדיין אינו "
                    "קיים במחירון."
                )
            )
            return True

        send_message(
            phone,
            (
                "💰 מחיר מסלול\n\n"
                f"📍 {row['city_from']} ↔ "
                f"{row['city_to']}\n"
                f"💵 {row['price']} ₪"
            )
        )

        return True

    # --------------------------------------------------------
    # מחיקה - מוצא
    # --------------------------------------------------------

    if state == "price_delete_from":
        city_from = resolve_city(
            text
        )

        update_session_data(
            phone,
            "price_delete_to",
            city_from=city_from
        )

        send_message(
            phone,
            "📍 שלח את עיר היעד."
        )

        return True

    # --------------------------------------------------------
    # מחיקה - יעד
    # --------------------------------------------------------

    if state == "price_delete_to":
        city_from = data.get(
            "city_from",
            ""
        )

        city_to = resolve_city(
            text
        )

        success = delete_route_price(
            phone,
            city_from,
            city_to
        )

        clear_session(
            phone
        )

        if success:
            send_message(
                phone,
                "🗑️ המחיר נמחק מהמחירון."
            )
        else:
            send_message(
                phone,
                "❌ המסלול לא נמצא במחירון."
            )

        return True

    return False


# ============================================================
# הפעלת משלוחים שממתינים למסלול שקיבל מחיר
# ============================================================

def activate_waiting_shipments_for_route(
    city_from,
    city_to,
    actor_phone
):
    city_from = resolve_city(
        city_from
    )

    city_to = resolve_city(
        city_to
    )

    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM shipments
            WHERE status = ?
            ORDER BY created_at ASC
            """,
            (
                SHIP_NEEDS_PRICE,
            )
        ).fetchall()

    activated = 0

    for shipment in rows:
        a = resolve_city(
            shipment["origin_city"]
        )

        b = resolve_city(
            shipment["destination_city"]
        )

        same_route = (
            (
                a == city_from
                and b == city_to
            )
            or
            (
                a == city_to
                and b == city_from
            )
        )

        if not same_route:
            continue

        price_data = calculate_shipment_price(
            a,
            b,
            shipment["vehicle_type"],
            bool(
                shipment["driver_help"]
            )
        )

        if not price_data:
            continue

        with db() as conn:
            conn.execute(
                """
                UPDATE shipments
                SET
                    base_price = ?,
                    help_extra = ?,
                    final_price = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    price_data[
                        "base_price"
                    ],
                    price_data[
                        "help_extra"
                    ],
                    price_data[
                        "final_price"
                    ],
                    SHIP_NEW,
                    now_ts(),
                    shipment["id"],
                )
            )

            conn.commit()

        publisher = get_shipment_publisher(
            shipment["id"]
        )

        if publisher:
            send_message(
                publisher["phone"],
                (
                    "💰 המשלוח שלך תומחר "
                    "ומוכן לפרסום.\n\n"
                    f"{shipment_title(shipment)}\n"
                    f"📍 {a} → {b}\n"
                    f"💵 מחיר: "
                    f"{price_data['final_price']} ₪"
                )
            )

        distribute_shipment_to_drivers(
            shipment["id"]
        )

        activated += 1

    log_action(
        actor_phone,
        "ACTIVATE_WAITING_SHIPMENTS",
        "route",
        0,
        (
            f"{city_from}->{city_to}; "
            f"activated={activated}"
        )
    )

    return activated


# ============================================================
# תמחור ידני של משלוח בודד
# ============================================================

def start_manual_shipment_price(
    phone,
    shipment_id
):
    if not can_manage_prices(
        phone
    ):
        return False

    shipment = get_shipment(
        shipment_id
    )

    if not shipment:
        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )
        return True

    save_session(
        phone,
        "manual_shipment_price",
        {
            "shipment_id":
                shipment_id,
        }
    )

    send_message(
        phone,
        (
            "💰 תמחור משלוח\n\n"
            f"📍 {shipment['origin_city']} → "
            f"{shipment['destination_city']}\n\n"
            "שלח את מחיר המסלול בשקלים.\n"
            "המחיר יישמר גם במחירון."
        )
    )

    return True


# ============================================================
# תמחור ידני - קבלת המחיר
# ============================================================

def handle_manual_shipment_price_state(
    phone,
    state,
    text
):
    if state != "manual_shipment_price":
        return False

    if not can_manage_prices(
        phone
    ):
        return False

    amount_text = re.sub(
        r"[^\d]",
        "",
        str(
            text
            or ""
        )
    )

    if not amount_text:
        send_message(
            phone,
            "❌ שלח מחיר במספרים."
        )
        return True

    session = get_session(
        phone
    )

    shipment_id = (
        session
        .get(
            "data",
            {}
        )
        .get(
            "shipment_id"
        )
    )

    if not shipment_id:
        clear_session(
            phone
        )
        return True

    shipment = get_shipment(
        int(shipment_id)
    )

    if not shipment:
        clear_session(
            phone
        )

        send_message(
            phone,
            "❌ המשלוח לא נמצא."
        )

        return True

    try:
        save_route_price(
            phone,
            shipment["origin_city"],
            shipment["destination_city"],
            int(amount_text)
        )

    except Exception as exc:
        send_message(
            phone,
            (
                "❌ לא ניתן לשמור מחיר.\n"
                f"{str(exc)}"
            )
        )

        return True

    clear_session(
        phone
    )

    activate_waiting_shipments_for_route(
        shipment["origin_city"],
        shipment["destination_city"],
        phone
    )

    send_message(
        phone,
        (
            "✅ המחיר נשמר והמשלוח "
            "הועבר להפצה."
        )
    )

    return True


# ============================================================
# הוספת עיר
# ============================================================

def start_add_city(phone):
    if not is_admin(
        phone
    ):
        return

    save_session(
        phone,
        "admin_add_city",
        {}
    )

    send_message(
        phone,
        "🏙️ שלח את שם העיר להוספה."
    )


def add_city(
    phone,
    city_name
):
    if not is_admin(
        phone
    ):
        return False

    city_name = clean_text(
        city_name
    )

    if len(city_name) < 2:
        raise ValueError(
            "שם העיר קצר מדי"
        )

    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cities (
                city_name,
                is_active,
                created_by,
                created_at,
                updated_at
            )
            VALUES (?, 1, ?, ?, ?)
            """,
            (
                city_name,
                phone,
                now_ts(),
                now_ts(),
            )
        )

        conn.commit()

    return True


# ============================================================
# הוספת כינוי לעיר
# ============================================================

def start_add_city_alias(phone):
    if not is_admin(
        phone
    ):
        return

    save_session(
        phone,
        "admin_alias_city",
        {}
    )

    send_message(
        phone,
        (
            "🏙️ לאיזו עיר תרצה "
            "להוסיף כינוי?\n\n"
            "לדוגמה: ראשון לציון"
        )
    )


def save_city_alias(
    phone,
    city_name,
    alias
):
    if not is_admin(
        phone
    ):
        return False

    city_name = resolve_city(
        city_name
    )

    alias = clean_text(
        alias
    ).lower()

    if len(alias) < 1:
        raise ValueError(
            "כינוי אינו תקין"
        )

    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cities (
                name,
                is_active,
                created_by,
                created_at,
                updated_at
            )
            VALUES (?, 1, ?, ?, ?)
            """,
            (
                city_name,
                phone,
                now_ts(),
                now_ts(),
            )
        )

        conn.execute(
            """
            INSERT INTO city_aliases (
                city_name,
                alias,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(alias)
            DO UPDATE SET
                city_name = excluded.city_name,
                created_by = excluded.created_by,
                created_at = excluded.created_at
            """,
            (
                city_name,
                alias,
                phone,
                now_ts(),
            )
        )

        conn.commit()

    log_action(
        phone,
        "SAVE_CITY_ALIAS",
        "city_alias",
        0,
        f"{alias}={city_name}"
    )

    return True


# ============================================================
# מחיקת כינוי
# ============================================================

def start_delete_city_alias(phone):
    if not is_admin(
        phone
    ):
        return

    save_session(
        phone,
        "admin_alias_delete",
        {}
    )

    send_message(
        phone,
        (
            "🗑️ שלח את הכינוי שברצונך למחוק.\n\n"
            "לדוגמה: ים"
        )
    )


def delete_city_alias(
    phone,
    alias
):
    if not is_admin(
        phone
    ):
        return False

    alias = clean_text(
        alias
    ).lower()

    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM city_aliases
            WHERE alias = ?
            LIMIT 1
            """,
            (
                alias,
            )
        ).fetchone()

        if not row:
            return False

        conn.execute(
            """
            DELETE FROM city_aliases
            WHERE alias = ?
            """,
            (
                alias,
            )
        )

        conn.commit()

    log_action(
        phone,
        "DELETE_CITY_ALIAS",
        "city_alias",
        0,
        alias
    )

    return True


# ============================================================
# רשימת כינויים
# ============================================================

def show_city_aliases(phone):
    if not is_admin(
        phone
    ):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM city_aliases
            ORDER BY city_name ASC, alias ASC
            LIMIT 100
            """
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "📭 עדיין לא הוגדרו כינויים.",
            [
                (
                    "admin_cities",
                    "↩️ חזרה"
                ),
            ],
            header="🏙️ ערים וכינויים"
        )
        return

    lines = [
        "🏙️ ערים וכינויים",
        "",
    ]

    for row in rows:
        lines.append(
            f"• {row['alias']} → {row['city_name']}"
        )

    text = "\n".join(
        lines
    )

    send_message(
        phone,
        text[:4000]
    )


# ============================================================
# טיפול בזרימת ערים וכינויים
# ============================================================

def handle_city_management_state(
    phone,
    state,
    text
):
    if not is_admin(
        phone
    ):
        return False

    text = clean_text(
        text
    )

    session = get_session(
        phone
    )

    data = (
        session.get(
            "data",
            {}
        )
        or {}
    )

    # הוספת עיר
    if state == "admin_add_city":
        try:
            add_city(
                phone,
                text
            )

        except Exception as exc:
            send_message(
                phone,
                (
                    "❌ לא ניתן להוסיף עיר.\n"
                    f"{str(exc)}"
                )
            )
            return True

        clear_session(
            phone
        )

        send_message(
            phone,
            f"✅ העיר {text} נוספה למערכת."
        )

        return True

    # בחירת עיר לכינוי
    if state == "admin_alias_city":
        city_name = resolve_city(
            text
        )

        update_session_data(
            phone,
            "admin_alias_value",
            city_name=city_name
        )

        send_message(
            phone,
            (
                f"🏙️ עיר: {city_name}\n\n"
                "עכשיו שלח את הכינוי.\n"
                "לדוגמה: ראשון"
            )
        )

        return True

    # שמירת הכינוי
    if state == "admin_alias_value":
        city_name = data.get(
            "city_name",
            ""
        )

        try:
            save_city_alias(
                phone,
                city_name,
                text
            )

        except Exception as exc:
            send_message(
                phone,
                (
                    "❌ לא ניתן לשמור כינוי.\n"
                    f"{str(exc)}"
                )
            )
            return True

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ הכינוי נשמר.\n\n"
                f"🔤 {text} → {city_name}"
            )
        )

        return True

    # מחיקת כינוי
    if state == "admin_alias_delete":
        success = delete_city_alias(
            phone,
            text
        )

        clear_session(
            phone
        )

        if success:
            send_message(
                phone,
                "✅ הכינוי נמחק."
            )
        else:
            send_message(
                phone,
                "❌ הכינוי לא נמצא."
            )

        return True

    return False


# ============================================================
# טיפול בכפתורי מחירון / ערים
# ============================================================

def handle_price_city_actions(
    phone,
    action_id
):
    if action_id == "price_add":
        start_price_add(
            phone
        )
        return True

    if action_id == "price_check":
        start_price_check(
            phone
        )
        return True

    if action_id == "price_delete":
        start_price_delete(
            phone
        )
        return True

    if action_id.startswith(
        "admin_price_shipment_"
    ):
        raw_id = action_id.replace(
            "admin_price_shipment_",
            "",
            1
        )

        if raw_id.isdigit():
            return start_manual_shipment_price(
                phone,
                int(raw_id)
            )

    if action_id == "admin_city_add":
        start_add_city(
            phone
        )
        return True

    if action_id == "admin_alias_add":
        start_add_city_alias(
            phone
        )
        return True

    if action_id == "admin_alias_delete":
        start_delete_city_alias(
            phone
        )
        return True

    if action_id == "admin_alias_list":
        show_city_aliases(
            phone
        )
        return True

    return False


# ============================================================
# סוף חלק 7A
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 7B
# סדרנים + חסימות + מתגי מערכת + תוספת עזרה
# ============================================================


# ============================================================
# ניהול סדרנים
# ============================================================

def start_add_dispatcher(phone):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_dispatcher_add_phone",
        {}
    )

    send_message(
        phone,
        (
            "👨‍💼 הוספת סדרן\n\n"
            "שלח את מספר הטלפון של הסדרן.\n"
            "לדוגמה: 0501234567"
        )
    )


def start_remove_dispatcher(phone):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_dispatcher_remove_phone",
        {}
    )

    send_message(
        phone,
        (
            "➖ הסרת סדרן\n\n"
            "שלח את מספר הטלפון "
            "של הסדרן שברצונך להסיר."
        )
    )


def add_dispatcher(
    admin_phone,
    dispatcher_phone
):
    if not is_admin(admin_phone):
        return False

    dispatcher_phone = normalize_phone(
        dispatcher_phone
    )

    if not dispatcher_phone:
        raise ValueError(
            "מספר טלפון אינו תקין"
        )

    user = get_user(
        dispatcher_phone
    )

    if user:
        with db() as conn:
            conn.execute(
                """
                UPDATE users
                SET
                    role = ?,
                    status = ?,
                    approved_at = ?,
                    approved_by = ?
                WHERE phone = ?
                """,
                (
                    ROLE_DISPATCHER,
                    USER_APPROVED,
                    now_ts(),
                    normalize_phone(
                        admin_phone
                    ),
                    dispatcher_phone,
                )
            )        
            conn.commit()

    else:
        create_or_update_user(
            phone=dispatcher_phone,
            role=ROLE_DISPATCHER,
            status=USER_APPROVED,
            full_name="סדרן",
            business_name="",
            city=""
        )

    log_action(
        admin_phone,
        "ADD_DISPATCHER",
        "user",
        0,
        dispatcher_phone
    )

    send_message(
        dispatcher_phone,
        (
            "👨‍💼 הוגדרת כסדרן בשליחובוט.\n\n"
            "כעת יש לך גישה לתפריט הסדרן, "
            "לניהול משלוחים ולמחירון."
        )
    )

    return True


def remove_dispatcher(
    admin_phone,
    dispatcher_phone
):
    if not is_admin(admin_phone):
        return False

    dispatcher_phone = normalize_phone(
        dispatcher_phone
    )

    user = get_user(
        dispatcher_phone
    )

    if not user:
        return False

    if user["role"] != ROLE_DISPATCHER:
        return False

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET
                role = ?,
                updated_at = ?
            WHERE phone = ?
            """,
            (
                ROLE_CUSTOMER,
                now_ts(),
                dispatcher_phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "REMOVE_DISPATCHER",
        "user",
        user["id"],
        dispatcher_phone
    )

    send_message(
        dispatcher_phone,
        (
            "ℹ️ הרשאת הסדרן שלך "
            "בשליחובוט הוסרה."
        )
    )

    return True


def show_dispatcher_list(phone):
    if not is_admin(phone):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM users
            WHERE
                role = ?
                AND status = ?
            ORDER BY full_name ASC
            """,
            (
                ROLE_DISPATCHER,
                USER_APPROVED,
            )
        ).fetchall()

    if not rows:
        send_message(
            phone,
            "📭 אין כרגע סדרנים במערכת."
        )
        return

    lines = [
        "👨‍💼 רשימת סדרנים",
        "",
    ]

    for user in rows:
        lines.append(
            (
                f"• {user['full_name'] or 'סדרן'}"
                f" — {user['phone']}"
            )
        )

    send_message(
        phone,
        "\n".join(lines)[:4000]
    )


# ============================================================
# חסימת משתמשים
# ============================================================

def start_block_user(phone):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_block_phone",
        {}
    )

    send_message(
        phone,
        (
            "🚫 חסימת משתמש\n\n"
            "שלח את מספר הטלפון לחסימה."
        )
    )


def start_unblock_user(phone):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_unblock_phone",
        {}
    )

    send_message(
        phone,
        (
            "🔓 הסרת חסימה\n\n"
            "שלח את מספר הטלפון."
        )
    )


def block_user(
    admin_phone,
    target_phone
):
    if not is_admin(admin_phone):
        return False

    target_phone = normalize_phone(
        target_phone
    )

    if not target_phone:
        raise ValueError(
            "מספר טלפון אינו תקין"
        )

    if target_phone == normalize_phone(
        ADMIN_PHONE
    ):
        raise ValueError(
            "לא ניתן לחסום את המנהל"
        )

    user = get_user(
        target_phone
    )

    if not user:
        raise ValueError(
            "המשתמש אינו רשום במערכת"
        )

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET
                status = ?,
                blocked_at = ?,
                blocked_by = ?,
                updated_at = ?
            WHERE phone = ?
            """,
            (
                USER_BLOCKED,
                now_ts(),
                normalize_phone(
                    admin_phone
                ),
                now_ts(),
                target_phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "BLOCK_USER",
        "user",
        user["id"],
        target_phone
    )

    send_message(
        target_phone,
        (
            "🚫 החשבון שלך בשליחובוט "
            "נחסם על ידי מנהל המערכת."
        )
    )

    return True


def unblock_user(
    admin_phone,
    target_phone
):
    if not is_admin(admin_phone):
        return False

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
                status = ?,
                blocked_at = 0,
                blocked_by = '',
                updated_at = ?
            WHERE phone = ?
            """,
            (
                USER_APPROVED,
                now_ts(),
                target_phone,
            )
        )

        conn.commit()

    log_action(
        admin_phone,
        "UNBLOCK_USER",
        "user",
        user["id"],
        target_phone
    )

    send_message(
        target_phone,
        (
            "🔓 החסימה בחשבון שלך "
            "הוסרה."
        )
    )

    return True


def show_blocked_users(phone):
    if not is_admin(phone):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM users
            WHERE status = ?
            ORDER BY blocked_at DESC
            LIMIT 100
            """,
            (
                USER_BLOCKED,
            )
        ).fetchall()

    if not rows:
        send_message(
            phone,
            "✅ אין משתמשים חסומים."
        )
        return

    lines = [
        "🚫 משתמשים חסומים",
        "",
    ]

    for user in rows:
        lines.append(
            (
                f"• {user['full_name'] or '-'}"
                f" — {user['phone']}"
            )
        )

    send_message(
        phone,
        "\n".join(lines)[:4000]
    )


# ============================================================
# שינוי הגדרה בוליאנית
# ============================================================

def toggle_setting(
    phone,
    key
):
    if not is_admin(phone):
        return None

    current = setting_enabled(
        key,
        "0"
    )

    new_value = (
        "0"
        if current
        else "1"
    )

    set_setting(
        key,
        new_value
    )    

    return (
        new_value == "1"
    )


# ============================================================
# הפעלה / כיבוי של כל הבוט
# ============================================================

def toggle_system(phone):
    enabled = toggle_setting(
        phone,
        "system_enabled"
    )

    if enabled is None:
        return False

    status = (
        "🟢 פעיל"
        if enabled
        else "🔴 מצב תחזוקה"
    )

    send_message(
        phone,
        (
            "🤖 מצב שליחובוט עודכן.\n\n"
            f"מצב נוכחי: {status}"
        )
    )

    return True


# ============================================================
# הפעלה / כיבוי צד השליחים
# ============================================================

def toggle_driver_side(phone):
    enabled = toggle_setting(
        phone,
        "driver_side_enabled"
    )

    if enabled is None:
        return False

    status = (
        "🟢 פעיל"
        if enabled
        else "🔴 כבוי"
    )

    send_message(
        phone,
        (
            "🚚 צד השליחים עודכן.\n\n"
            f"מצב נוכחי: {status}"
        )
    )

    return True


# ============================================================
# תוספת עזרה לפי סוג רכב
# ============================================================

def show_help_price_settings(phone):
    if not is_admin(phone):
        return

    send_list(
        phone,
        "🧤 תוספת עזרת שליח",
        (
            "בחר סוג רכב כדי לשנות "
            "את תוספת המחיר."
        ),
        [
            (
                "help_price_private",
                "🚗 רכב פרטי",
                (
                    f"{get_driver_help_extra(VEHICLE_PRIVATE)} ₪"
                ),
            ),
            (
                "help_price_7",
                "🚙 7 מקומות",
                (
                    f"{get_driver_help_extra(VEHICLE_7_SEATS)} ₪"
                ),
            ),
            (
                "help_price_small",
                "🚐 מסחרי קטן",
                (
                    f"{get_driver_help_extra(VEHICLE_SMALL_COMMERCIAL)} ₪"
                ),
            ),
            (
                "help_price_large",
                "🚚 מסחרי גדול",
                (
                    f"{get_driver_help_extra(VEHICLE_LARGE_COMMERCIAL)} ₪"
                ),
            ),
        ],
        button_text="בחר",
        footer="שליחובוט • הגדרות"
    )


def start_help_price_update(
    phone,
    vehicle_type
):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_help_price_amount",
        {
            "vehicle_type":
                vehicle_type,
        }
    )

    vehicle_label = VEHICLE_LABELS.get(
        vehicle_type,
        vehicle_type
    )

    send_message(
        phone,
        (
            f"🧤 {vehicle_label}\n\n"
            "שלח את תוספת המחיר "
            "בשקלים.\n"
            "לדוגמה: 20"
        )
    )


# ============================================================
# הודעת תחזוקה
# ============================================================

def start_maintenance_text_update(phone, target):
    if not is_admin(phone):
        return

    if target not in ("drivers", "publishers"):
        return

    save_session(
        phone,
        "admin_maintenance_text",
        {
            "target": target
        }
    )

    target_text = (
        "לשליחים"
        if target == "drivers"
        else "למפרסמים ולסדרנים"
    )

    send_message(
        phone,
        (
            f"🛠️ שלח את הודעת התחזוקה {target_text}.\n\n"
            "ההודעה תישלח למשתמשים המתאימים."
        )
    )


# ============================================================
# טיפול בטקסט - חלק 7B
# ============================================================

def handle_admin_management_state(
    phone,
    state,
    text
):
    if not is_admin(phone):
        return False

    text = clean_text(
        text
    )

    if state == "admin_delete_user_phone":
        target_phone = normalize_phone(text)

        with db() as conn:
            user = conn.execute(
                """
                SELECT id, phone, role, status, full_name, business_name
                FROM users
                WHERE phone = ?
                """,
                (target_phone,)
            ).fetchone()

        if not user:
            send_message(
                phone,
                (
                    "❌ לא נמצא משתמש עם המספר הזה.\n"
                    "שלח מספר אחר או חזור לתפריט."
                )
            )
            return True

        if is_admin(target_phone):
            clear_session(phone)

            send_message(
                phone,
                "❌ לא ניתן למחוק משתמש מנהל."
            )
            return True

        save_session(
            phone,
            "admin_delete_user_confirm",
            {
                "user_id": user["id"],
                "phone": user["phone"],
            }
        )

        send_buttons(
            phone,
            (
                "⚠️ *אישור מחיקת משתמש*\n\n"
                f"👤 שם: {user['full_name'] or '-'}\n"
                f"🏢 עסק: {user['business_name'] or '-'}\n"
                f"📱 טלפון: {user['phone']}\n"
                f"👥 תפקיד: {user['role']}\n"
                f"📌 סטטוס: {user['status']}\n\n"
                "המחיקה תאפס את המשתמש ותאפשר לו להתחיל הרשמה מחדש.\n\n"
                "האם למחוק?"
            ),
            [
                (
                    "admin_delete_user_confirm",
                    "🗑️ כן, מחק משתמש"
                ),
                (
                    "admin_delete_user_cancel",
                    "❌ ביטול"
                ),
            ]
        )

        return True    
    if state == "admin_dispatcher_add_phone":
        try:
            add_dispatcher(
                phone,
                text
            )

            clear_session(
                phone
            )

            send_message(
                phone,
                "✅ הסדרן נוסף בהצלחה."
            )

        except Exception as exc:
            send_message(
                phone,
                (
                    "❌ לא ניתן להוסיף סדרן.\n"
                    f"{str(exc)}"
                )
            )

        return True

    if state == "admin_dispatcher_remove_phone":
        success = remove_dispatcher(
            phone,
            text
        )

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ הרשאת הסדרן הוסרה."
                if success
                else "❌ הסדרן לא נמצא."
            )
        )

        return True

    if state == "admin_block_phone":
        try:
            block_user(
                phone,
                text
            )

            clear_session(
                phone
            )

            send_message(
                phone,
                "✅ המשתמש נחסם."
            )

        except Exception as exc:
            send_message(
                phone,
                (
                    "❌ לא ניתן לחסום משתמש.\n"
                    f"{str(exc)}"
                )
            )

        return True

    if state == "admin_unblock_phone":
        success = unblock_user(
            phone,
            text
        )

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ החסימה הוסרה."
                if success
                else "❌ המשתמש לא נמצא."
            )
        )

        return True

    if state == "admin_help_price_amount":
        amount = re.sub(
            r"[^\d]",
            "",
            text
        )

        if not amount:
            send_message(
                phone,
                "❌ שלח סכום במספרים."
            )
            return True

        session = get_session(
            phone
        )

        vehicle_type = (
            session
            .get(
                "data",
                {}
            )
            .get(
                "vehicle_type"
            )
        )

        if not vehicle_type:
            clear_session(
                phone
            )
            return True

        key_map = {
            VEHICLE_PRIVATE:
                "help_extra_private",

            VEHICLE_7_SEATS:
                "help_extra_7_seats",

            VEHICLE_SMALL_COMMERCIAL:
                "help_extra_small_commercial",

            VEHICLE_LARGE_COMMERCIAL:
                "help_extra_large_commercial",
        }

        setting_key = key_map.get(
            vehicle_type
        )

        if not setting_key:
            clear_session(
                phone
            )
            return True

        set_setting(
            setting_key,
            str(
                int(amount)
            )
        )        

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ תוספת העזרה עודכנה ל-"
                f"{int(amount)} ₪."
            )
        )

        return True

    if state == "admin_maintenance_text":
        if len(text) < 2:
            send_message(
                phone,
                "❌ ההודעה קצרה מדי."
            )
            return True

        session = get_session(phone)
        target = ((session or {}).get("data") or {}).get("target")

        if target == "drivers":
            roles = (ROLE_DRIVER,)
            target_name = "השליחים"

        elif target == "publishers":
            roles = (ROLE_CUSTOMER, ROLE_DISPATCHER)
            target_name = "המפרסמים והסדרנים"

        else:
            clear_session(phone)
            send_message(
                phone,
                "❌ לא נמצאה קבוצת יעד."
            )
            return True        

        with db() as conn:
            placeholders = ",".join(
                "?" for _ in roles
            )

            users = conn.execute(
                f"""
                SELECT phone
                FROM users
                WHERE role IN ({placeholders})
                  AND status = ?
                """,
                (*roles, USER_APPROVED)
            ).fetchall()

        sent_count = 0
        failed_count = 0

        for row in users:
            target_phone = row["phone"]

            try:
                send_message(
                    target_phone,
                    text
                )
                sent_count += 1
            except Exception as e:
                print(
                    "MAINTENANCE SEND ERROR:",
                    target_phone,
                    repr(e)
                )
                failed_count += 1

        clear_session(phone)

        send_message(
            phone,
            (
                f"✅ הודעת התחזוקה נשלחה אל {target_name}.\n\n"
                f"📤 נשלחו: {sent_count}\n"
                f"❌ נכשלו: {failed_count}"
            )
        )

        return True    
    return False


# ============================================================
# טיפול בכפתורים - חלק 7B
# ============================================================

def handle_admin_management_actions(
    phone,
    action_id
):
    if not is_admin(phone):
        return False

    if action_id == "admin_dispatcher_add":
        start_add_dispatcher(
            phone
        )
        return True

    if action_id == "admin_dispatcher_remove":
        start_remove_dispatcher(
            phone
        )
        return True

    if action_id == "admin_dispatcher_list":
        show_dispatcher_list(
            phone
        )
        return True

    if action_id == "admin_block_add":
        start_block_user(
            phone
        )
        return True

    if action_id == "admin_block_remove":
        start_unblock_user(
            phone
        )
        return True

    if action_id == "admin_block_list":
        show_blocked_users(
            phone
        )
        return True

    if action_id == "admin_system_toggle":
        return toggle_system(
            phone
        )

    if action_id == "admin_driver_side_toggle":
        return toggle_driver_side(
            phone
        )

    if action_id == "admin_help_prices":
        show_help_price_settings(
            phone
        )
        return True

    if action_id == "help_price_private":
        start_help_price_update(
            phone,
            VEHICLE_PRIVATE
        )
        return True

    if action_id == "help_price_7":
        start_help_price_update(
            phone,
            VEHICLE_7_SEATS
        )
        return True

    if action_id == "help_price_small":
        start_help_price_update(
            phone,
            VEHICLE_SMALL_COMMERCIAL
        )
        return True

    if action_id == "help_price_large":
        start_help_price_update(
            phone,
            VEHICLE_LARGE_COMMERCIAL
        )
        return True

    if action_id == "admin_maintenance_drivers":
        start_maintenance_text_update(
            phone,
            "drivers"
        )
        return True

    if action_id == "admin_maintenance_publishers":
        start_maintenance_text_update(
            phone,
            "publishers"
        )
        return True    

    if action_id == "admin_delete_user":
        save_session(
            phone,
            "admin_delete_user_phone",
            {}
        )

        send_message(
            phone,
            (
                "🗑️ *מחיקת משתמש*\n\n"
                "שלח את מספר הטלפון של המשתמש שברצונך למחוק.\n\n"
                "⚠️ לפני המחיקה יוצגו לך פרטי המשתמש לאישור."
            )
        )

        return True    
    if action_id == "admin_delete_user_cancel":
        clear_session(phone)

        send_message(
            phone,
            "❌ מחיקת המשתמש בוטלה."
        )

        show_admin_more_menu(phone)
        return True

    if action_id == "admin_delete_user_confirm":
        session = get_session(phone)

        if session.get("state") != "admin_delete_user_confirm":
            send_message(
                phone,
                "❌ לא נמצאה בקשת מחיקה שממתינה לאישור."
            )
            return True

        data = session.get("data") or {}
        user_id = data.get("user_id")
        target_phone = normalize_phone(
            data.get("phone", "")
        )

        if not user_id or not target_phone:
            clear_session(phone)

            send_message(
                phone,
                "❌ פרטי המשתמש למחיקה חסרים."
            )
            return True

        if is_admin(target_phone):
            clear_session(phone)

            send_message(
                phone,
                "❌ לא ניתן לאפס משתמש מנהל."
            )
            return True

        with db() as conn:
            conn.execute(
                """
                UPDATE users
                SET role = ?,
                    status = ?,
                    full_name = '',
                    business_name = '',
                    city = '',
                    approved_at = 0
                WHERE id = ?
                """,
                (
                    ROLE_CUSTOMER,
                    USER_RESET,
                    user_id,
                )
            )

            conn.execute(
                "DELETE FROM sessions WHERE phone = ?",
                (target_phone,)
            )

            conn.commit()

        clear_session(phone)

        send_message(
            phone,
            (
                "✅ המשתמש אופס בהצלחה.\n\n"
                f"📱 {target_phone}\n"
                "המשתמש יכול כעת להתחיל את תהליך ההרשמה מחדש."
            )
        )

        show_admin_more_menu(phone)
        return True    
    return False


# ============================================================
# סוף חלק 7
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 8A
# מנויים + אמצעי תשלום + בקשות תשלום
# ============================================================

# ============================================================
# Paperless - הפקת קבלות למנויים
# ============================================================

def paperless_payment_data(method):
    method = clean_text(method).lower()

    payment_map = {
        "bank": {
            "iType": 2,
        },
        "bit": {
            "iType": 5,
            "iApp": 1,
        },
        "paybox": {
            "iType": 5,
            "iApp": 2,
        },
        "cash": {
            "iType": 4,
        },
        "credit": {
            "iType": 3,
        },
    }

    return payment_map.get(
        method,
        {
            "iType": 5,
        }
    )


def create_paperless_receipt(
    customer_name,
    customer_phone,
    amount,
    payment_method,
    description="מנוי חודשי - שליחובוט"
):
    if not PAPERLESS_API_KEY:
        raise RuntimeError(
            "PAPERLESS_API_KEY is missing"
        )

    try:
        amount = float(amount)
    except Exception:
        raise ValueError(
            "סכום הקבלה אינו תקין"
        )

    if amount <= 0:
        raise ValueError(
            "סכום הקבלה חייב להיות גדול מאפס"
        )

    payment_info = paperless_payment_data(
        payment_method
    )

    payload = {
        "type": {
            "iType": 3
        },
        "client": {
            "sPaperlessID": None,
            "sNumber": None,
            "sName": clean_text(customer_name) or "לקוח שליחובוט",
            "sEmail": None,
            "sMobile": normalize_phone(customer_phone),
            "sAddress": None,
            "sExternalID": None,
            "bIsFixed": True,
            "bIsEng": False
        },        
        "items": [
            {
                "sProductID": None,
                "sProductName": description,
                "dCount": 1,
                "dPrice": float(amount),
                "bVAT0": False
            }
        ],        
        "payments": [
            {
                **payment_info,
                "dAmount": amount
            }
        ]
    }    
    headers = {
        "X-API-KEY": PAPERLESS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.put(
        PAPERLESS_API_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    if not response.ok:
        raise RuntimeError(
            (
                "Paperless HTTP "
                f"{response.status_code}: "
                f"{response.text[:500]}"
            )
        )

    try:
        result = response.json()
    except Exception:
        raise RuntimeError(
            "Paperless returned invalid JSON"
        )

    invoices = result.get("invoices", [])

    if invoices:
        invoice = invoices[0]
        receipt_url = (
            invoice.get("sURL")
            or invoice.get("sDownloadPageURL")
            or ""
        )
    else:
        receipt_url = ""    

    return {
        "ok": True,
        "url": receipt_url,
        "response": result,
    }


# ============================================================
# הפקת קבלה עבור תשלום מנוי
# ============================================================

def create_subscription_receipt(
    payment_id
):
    payment = get_payment_by_id(
        payment_id
    )

    if not payment:
        raise ValueError(
            "התשלום לא נמצא"
        )

    user = get_user_by_id(
        payment["user_id"]
    )

    if not user:
        raise ValueError(
            "המשתמש לא נמצא"
        )

    result = create_paperless_receipt(
        customer_name=(
            user["full_name"]
            or "שליח"
        ),
        customer_phone=user["phone"],
        amount=payment["amount"],
        payment_method=payment["payment_method"],
        description="מנוי חודשי - שליחובוט"
    )

    receipt_url = result.get(
        "url",
        ""
    )

    with db() as conn:
        conn.execute(
            """
            UPDATE payments
            SET receipt_url = ?
            WHERE id = ?
            """,
            (
                receipt_url,
                payment_id,
            )
        )

        conn.commit()

    return receipt_url

# ============================================================
# שליחת קבלה לשליח
# ============================================================

def send_subscription_receipt(
    phone,
    payment_id
):
    try:
        receipt_url = (
            create_subscription_receipt(
                payment_id
            )
        )

    except Exception as exc:
        print(
            "PAPERLESS RECEIPT ERROR:",
            repr(exc)
        )

        return False

    if receipt_url:
        send_message(
            phone,
            (
                "🧾 הקבלה שלך מוכנה.\n\n"
                f"{receipt_url}"
            )
        )

    else:
        send_message(
            phone,
            (
                "🧾 התשלום נקלט והקבלה הופקה.\n"
                "לא התקבל קישור לצפייה בקבלה."
            )
        )

    return True


# ============================================================
# סוף Paperless
# ============================================================
# ============================================================
# מחיר המנוי
# ============================================================

def get_subscription_price():
    try:
        return int(
            get_setting(
                "subscription_price",
                "50"
            )
        )
    except Exception:
        return 50


# ============================================================
# האם המשתמש פטור ממנוי
# מנהל וסדרן תמיד פטורים
# ============================================================

def subscription_exempt(phone):
    phone = normalize_phone(
        phone
    )

    if is_admin(phone):
        return True

    if is_dispatcher(phone):
        return True

    return False


# ============================================================
# שליפת מנוי אחרון של משתמש
# ============================================================

def get_latest_subscription(
    user_id
):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                user_id,
            )
        ).fetchone()


# ============================================================
# האם מנוי פעיל
# ============================================================

def user_has_active_subscription(
    phone
):
    phone = normalize_phone(
        phone
    )

    if subscription_exempt(
        phone
    ):
        return True

    if not subscriptions_are_enabled():
        return True

    user = get_user(
        phone
    )

    if not user:
        return False

    if user["role"] != ROLE_DRIVER:
        return True

    subscription = get_latest_subscription(
        user["id"]
    )

    if not subscription:
        return False

    if subscription["status"] != SUB_ACTIVE:
        return False

    expires_at = int(
        subscription["expires_at"]
        or 0
    )

    if expires_at <= now_ts():
        return False

    return True


# ============================================================
# טקסט מצב מנוי
# ============================================================

def get_subscription_status_text(
    phone
):
    if subscription_exempt(
        phone
    ):
        return "מנוי פטור"

    if not subscriptions_are_enabled():
        return "מערכת המנויים כבויה"

    user = get_user(
        phone
    )

    if not user:
        return "לא נמצא משתמש"

    subscription = get_latest_subscription(
        user["id"]
    )

    if not subscription:
        return "אין מנוי פעיל"

    expires_at = int(
        subscription["expires_at"]
        or 0
    )

    if (
        subscription["status"] != SUB_ACTIVE
        or expires_at <= now_ts()
    ):
        return "המנוי אינו פעיל"

    expiry_text = datetime.fromtimestamp(
        expires_at
    ).strftime(
        "%d/%m/%Y"
    )

    return (
        f"מנוי פעיל עד {expiry_text}"
    )


# ============================================================
# יצירת / חידוש מנוי לחודש
# החודש נספר אישית מתאריך האישור
# ============================================================

def activate_driver_subscription(
    user_id,
    payment_id=None,
    months=1,
    actor_phone=""
):
    user = get_user_by_id(
        user_id
    )

    if not user:
        raise ValueError(
            "המשתמש לא נמצא"
        )

    if user["role"] != ROLE_DRIVER:
        raise ValueError(
            "המשתמש אינו שליח"
        )

    months = max(
        1,
        int(months)
    )

    latest = get_latest_subscription(
        user_id
    )

    current_time = now_ts()

    if (
        latest
        and latest["status"] == SUB_ACTIVE
        and int(
            latest["expires_at"]
            or 0
        ) > current_time
    ):
        starts_at = int(
            latest["expires_at"]
        )
    else:
        starts_at = current_time

    # חודש מנוי = 30 ימים
    expires_at = (
        starts_at
        + (
            30
            * 24
            * 60
            * 60
            * months
        )
    )

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                status,
                start_at,
                expires_at,
                payment_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                SUB_ACTIVE,
                starts_at,
                expires_at,
                payment_id,
                current_time,
                current_time,
            )
        )

        subscription_id = int(
            cursor.lastrowid
        )

        conn.commit()

    log_action(
        actor_phone or "system",
        "ACTIVATE_SUBSCRIPTION",
        "subscription",
        subscription_id,
        (
            f"user_id={user_id}; "
            f"expires_at={expires_at}"
        )
    )

    return subscription_id


# ============================================================
# סימון מנויים שפגו
# ============================================================

def expire_old_subscriptions():
    current_time = now_ts()

    with db() as conn:
        conn.execute(
            """
            UPDATE subscriptions
            SET
                status = ?,
                updated_at = ?
            WHERE
                status = ?
                AND expires_at <= ?
            """,
            (
                SUB_EXPIRED,
                current_time,
                SUB_ACTIVE,
                current_time,
            )
        )

        conn.commit()


# ============================================================
# תזכורת יום לפני פקיעת מנוי
# ============================================================

def send_subscription_expiry_reminders():
    if not subscriptions_are_enabled():
        return 0

    now_value = now_ts()

    from_ts = (
        now_value
        + 23 * 60 * 60
    )

    to_ts = (
        now_value
        + 25 * 60 * 60
    )

    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                s.*,
                u.phone,
                u.full_name

            FROM subscriptions s

            JOIN users u
                ON u.id = s.user_id

            WHERE
                s.status = ?
                AND s.expires_at BETWEEN ? AND ?
                AND COALESCE(
                    s.reminder_sent,
                    0
                ) = 0
            """,
            (
                SUB_ACTIVE,
                from_ts,
                to_ts,
            )
        ).fetchall()

    sent = 0

    for row in rows:
        expiry_text = datetime.fromtimestamp(
            int(
                row["expires_at"]
            )
        ).strftime(
            "%d/%m/%Y"
        )

        send_buttons(
            row["phone"],
            (
                "⏰ תזכורת מנוי\n\n"
                "המנוי שלך בשליחובוט "
                "יפוג מחר.\n\n"
                f"📅 תוקף עד: {expiry_text}\n\n"
                "ניתן לחדש כבר עכשיו "
                "והחודש החדש יתווסף "
                "לתאריך הקיים."
            ),
            [
                (
                    "driver_subscription",
                    "💎 חידוש מנוי"
                ),
            ],
            header="שליחובוט"
        )

        with db() as conn:
            conn.execute(
                """
                UPDATE subscriptions
                SET
                    reminder_sent = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now_ts(),
                    row["id"],
                )
            )

            conn.commit()

        sent += 1

    return sent


# ============================================================
# אמצעי תשלום
# ============================================================

def payment_method_enabled(
    method
):
    key_map = {
        "bit":
            "payment_bit_enabled",

        "paybox":
            "payment_paybox_enabled",

        "bank":
            "payment_bank_enabled",

        
    }

    key = key_map.get(
        method
    )

    if not key:
        return False

    return setting_enabled(
        key,
        "0"
    )


# ============================================================
# פרטי אמצעי תשלום
# ============================================================

def get_payment_method_details(
    method
):
    if method == "bit":
        return get_setting(
            "payment_bit_details",
            ""
        )

    if method == "paybox":
        return get_setting(
            "payment_paybox_details",
            ""
        )

    if method == "bank":
        return get_setting(
            "payment_bank_details",
            ""
        )

    return ""


# ============================================================
# תפריט המנוי של השליח
# ============================================================

def show_driver_subscription(
    phone
):
    if subscription_exempt(
        phone
    ):
        send_buttons(
            phone,
            (
                "💎 המנוי שלך\n\n"
                "החשבון שלך פטור מתשלום מנוי."
            ),
            [
                (
                    "driver_menu",
                    "↩️ חזרה"
                ),
            ],
            header="שליחובוט"
        )

        return

    if not subscriptions_are_enabled():
        send_buttons(
            phone,
            (
                "💎 מערכת המנויים "
                "אינה פעילה כרגע.\n\n"
                "השימוש בשליחובוט חינם."
            ),
            [
                (
                    "driver_menu",
                    "↩️ חזרה"
                ),
            ],
            header="שליחובוט"
        )

        return

    status_text = (
        get_subscription_status_text(
            phone
        )
    )

    price = get_subscription_price()

    send_buttons(
        phone,
        (
            "💎 המנוי שלי\n\n"
            f"מצב: {status_text}\n"
            f"מחיר חודשי: {price} ₪\n\n"
            "לחידוש המנוי לחץ למטה."
        ),
        [
            (
                "subscription_payment_methods",
                "💳 חידוש מנוי"
            ),
            (
                "driver_menu",
                "↩️ חזרה"
            ),
        ],
        header="שליחובוט"
    )


# ============================================================
# הצגת אמצעי תשלום פעילים
# ============================================================

def show_subscription_payment_methods(
    phone
):
    rows = []

    

    if payment_method_enabled(
        "bit"
    ):
        rows.append(
            (
                "subscription_pay_bit",
                "📱 Bit",
                "תשלום באמצעות Bit",
            )
        )

    if payment_method_enabled(
        "paybox"
    ):
        rows.append(
            (
                "subscription_pay_paybox",
                "📲 PayBox",
                "תשלום באמצעות PayBox",
            )
        )

    if payment_method_enabled(
        "bank"
    ):
        rows.append(
            (
                "subscription_pay_bank",
                "🏦 העברה בנקאית",
                "תשלום בהעברה",
            )
        )

    if not rows:
        send_message(
            phone,
            (
                "⚠️ אין כרגע אמצעי תשלום "
                "פעילים.\n"
                "יש לפנות למנהל."
            )
        )

        return

    send_list(
        phone,
        "💳 חידוש מנוי",
        (
            f"מחיר המנוי: "
            f"{get_subscription_price()} ₪\n\n"
            "בחר אמצעי תשלום:"
        ),
        rows,
        button_text="בחר",
        footer="שליחובוט • מנוי"
    )


# ============================================================
# יצירת בקשת תשלום ידנית
# Bit / PayBox / בנק
# ============================================================

def create_manual_payment_request(
    phone,
    method
):
    user = get_user(
        phone
    )

    if not user:
        return None

    if user["role"] != ROLE_DRIVER:
        return None

    if not payment_method_enabled(
        method
    ):
        send_message(
            phone,
            "❌ אמצעי התשלום אינו פעיל."
        )
        return None

    amount = get_subscription_price()

    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO payments (
                user_id,
                payment_type,
                payment_method,
                amount,
                status,
                proof_media_id,
                receipt_url,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, '', '', ?)
            """,
            (
                user["id"],
                "subscription",
                method,
                amount,
                PAYMENT_PENDING,
                now_ts(),
            )
        )

        payment_id = int(
            cursor.lastrowid
        )

        conn.commit()

    return payment_id

# ============================================================
# שליחת הוראות תשלום ידני
# ============================================================

def send_manual_payment_instructions(
    phone,
    method
):
    payment_id = (
        create_manual_payment_request(
            phone,
            method
        )
    )

    if not payment_id:
        return

    details = get_payment_method_details(
        method
    )

    labels = {
        "bit":
            "📱 Bit",

        "paybox":
            "📲 PayBox",

        "bank":
            "🏦 העברה בנקאית",
    }

    method_label = labels.get(
        method,
        method
    )

    send_message(
        phone,
        (
            f"{method_label}\n\n"
            f"💰 לתשלום: "
            f"{get_subscription_price()} ₪\n\n"
            f"{details or 'פרטי התשלום עדיין לא הוגדרו.'}\n\n"
            f"🔢 מספר בקשת תשלום: "
            f"{payment_id}\n\n"
            "לאחר ביצוע התשלום לחץ "
            "על הכפתור למטה."
        )
    )

    send_buttons(
        phone,
        "ביצעת את התשלום?",
        [
            (
                f"payment_done_{payment_id}",
                "✅ שילמתי"
            ),
            (
                "driver_subscription",
                "↩️ חזרה"
            ),
        ],
        header="אישור תשלום"
    )


# ============================================================
# השליח מודיע ששילם
# ============================================================

def driver_mark_payment_done(
    phone,
    payment_id
):
    user = get_user(
        phone
    )

    if not user:
        return False

    with db() as conn:
        payment = conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            LIMIT 1
            """,
            (
                payment_id,
            )
        ).fetchone()

    if not payment:
        send_message(
            phone,
            "❌ בקשת התשלום לא נמצאה."
        )
        return True

    if payment["user_id"] != user["id"]:
        return True

    save_session(
        phone,
        "subscription_payment_proof",
        {
            "payment_id": payment_id
        }
    )

    send_message(
        phone,
        (
            "📸 שלח עכשיו צילום של אישור התשלום.\n\n"
            "אפשר לשלוח צילום מסך של "
            "Bit / PayBox / העברה בנקאית.\n\n"
            "לאחר שליחת הצילום הבקשה "
            "תועבר לאישור המנהל."
        )
    )

    return True

# ============================================================
# סוף חלק 8A
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 8B
# אישור תשלומים + הגדרות מנוי + אמצעי תשלום
# ============================================================


# ============================================================
# תשלום לפי מזהה
# ============================================================

def get_payment_by_id(payment_id):
    with db() as conn:
        return conn.execute(
            """
            SELECT *
            FROM payments
            WHERE id = ?
            LIMIT 1
            """,
            (
                int(payment_id),
            )
        ).fetchone()


# ============================================================
# אישור תשלום ידני
# ============================================================

def approve_manual_payment(
    admin_phone,
    payment_id
):
    if not is_admin(admin_phone):
        return False

    payment = get_payment_by_id(
        payment_id
    )

    if not payment:
        send_message(
            admin_phone,
            "❌ התשלום לא נמצא."
        )
        return True

    if payment["status"] == PAYMENT_APPROVED:
        send_message(
            admin_phone,
            "ℹ️ התשלום כבר אושר."
        )
        return True

    user = get_user_by_id(
        payment["user_id"]
    )

    if not user:
        send_message(
            admin_phone,
            "❌ המשתמש לא נמצא."
        )
        return True

    with db() as conn:
        conn.execute(
            """
            UPDATE payments
            SET
                status = ?,
                approved_at = ?,
                approved_by = ?
            WHERE id = ?
            """,
            (
                PAYMENT_APPROVED,
                now_ts(),
                normalize_phone(
                    admin_phone
                ),
                payment_id,
            )
        )    

        conn.commit()

    subscription_id = (
        activate_driver_subscription(
            user["id"],
            payment_id=payment_id,
            months=1,
            actor_phone=admin_phone
        )
    )
    send_subscription_receipt(
        user["phone"],
        payment_id
    )
    send_message(
        user["phone"],
        (
            "✅ התשלום אושר.\n\n"
            "💎 המנוי שלך בשליחובוט הופעל.\n"
            f"{get_subscription_status_text(user['phone'])}"
        )
    )

    send_message(
        admin_phone,
        (
            "✅ התשלום אושר והמנוי הופעל.\n\n"
            f"👤 {user['full_name'] or '-'}\n"
            f"📱 {user['phone']}\n"
            f"💰 {payment['amount']} ₪\n"
            f"🔢 מנוי: {subscription_id}"
        )
    )

    log_action(
        admin_phone,
        "APPROVE_PAYMENT",
        "payment",
        payment_id,
        f"user_id={user['id']}"
    )

    return True


# ============================================================
# דחיית תשלום
# ============================================================

def reject_manual_payment(
    admin_phone,
    payment_id
):
    if not is_admin(admin_phone):
        return False

    payment = get_payment_by_id(
        payment_id
    )

    if not payment:
        send_message(
            admin_phone,
            "❌ התשלום לא נמצא."
        )
        return True

    user = get_user_by_id(
        payment["user_id"]
    )

    with db() as conn:
        conn.execute(
            """
            UPDATE payments
            SET
                status = ?,
                approved_by = ?
            WHERE id = ?
            """,
            (
                PAYMENT_REJECTED,
                normalize_phone(
                    admin_phone
                ),
                payment_id,
            )
        )    

        conn.commit()

    if user:
        send_message(
            user["phone"],
            (
                "❌ התשלום לא אושר.\n\n"
                "אם ביצעת את התשלום, "
                "פנה לנציג לבדיקה."
            )
        )

    send_message(
        admin_phone,
        "❌ התשלום סומן כנדחה."
    )

    return True


# ============================================================
# תשלומים שממתינים לאישור
# ============================================================

def show_pending_payments(phone):
    if not is_admin(phone):
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                p.*,
                u.full_name,
                u.phone

            FROM payments p

            JOIN users u
                ON u.id = p.user_id

            WHERE p.status IN (?, ?)

            ORDER BY p.created_at ASC
            LIMIT 10
            """,
            (
                PAYMENT_PENDING,
                PAYMENT_REVIEW,
            )
        ).fetchall()

    if not rows:
        send_buttons(
            phone,
            "✅ אין תשלומים שממתינים לאישור.",
            [
                (
                    "admin_payments",
                    "↩️ חזרה"
                ),
            ],
            header="💳 תשלומים"
        )
        return

    menu_rows = []

    for payment in rows:
        menu_rows.append(
            (
                f"admin_payment_{payment['id']}",
                (
                    payment["full_name"]
                    or "שליח"
                )[:24],
                (
                    f"{payment['amount']} ₪ • "
                    f"{payment['method']} • "
                    f"{payment['phone']}"
                )[:72],
            )
        )

    send_list(
        phone,
        "💳 תשלומים ממתינים",
        "בחר תשלום:",
        menu_rows,
        button_text="פתח",
        footer="שליחובוט • מנהל"
    )


# ============================================================
# הצגת תשלום למנהל
# ============================================================

def show_admin_payment(
    phone,
    payment_id
):
    if not is_admin(phone):
        return

    payment = get_payment_by_id(
        payment_id
    )

    if not payment:
        send_message(
            phone,
            "❌ התשלום לא נמצא."
        )
        return

    user = get_user_by_id(
        payment["user_id"]
    )

    send_buttons(
        phone,
        (
            "💳 בקשת תשלום\n\n"
            f"👤 "
            f"{user['full_name'] if user else '-'}\n"
            f"📱 "
            f"{user['phone'] if user else '-'}\n"
            f"💰 {payment['amount']} ₪\n"
            f"💳 {payment['method']}\n"
            f"🔢 #{payment['id']}"
        ),
        [
            (
                f"payment_approve_{payment_id}",
                "✅ אישור"
            ),
            (
                f"payment_reject_{payment_id}",
                "❌ דחייה"
            ),
            (
                "admin_payments",
                "↩️ חזרה"
            ),
        ],
        header="אישור תשלום"
    )


# ============================================================
# הפעלה / כיבוי מערכת המנויים
# ============================================================

def toggle_subscriptions(phone):
    if not is_admin(phone):
        return False

    current = subscriptions_are_enabled()

    set_setting(
        "subscriptions_enabled",
        (
            "0"
            if current
            else "1"
        )
    )    

    new_status = not current

    send_message(
        phone,
        (
            "💎 מערכת המנויים עודכנה.\n\n"
            f"מצב: "
            f"{'🟢 פעילה' if new_status else '🔴 כבויה'}"
        )
    )

    return True


# ============================================================
# שינוי מחיר מנוי
# ============================================================

def start_subscription_price_update(phone):
    if not is_admin(phone):
        return

    save_session(
        phone,
        "admin_subscription_price_amount",
        {}
    )

    send_message(
        phone,
        (
            "💰 שלח את מחיר המנוי "
            "החודשי החדש.\n\n"
            "לדוגמה: 50"
        )
    )


# ============================================================
# עריכת Bit / PayBox / בנק
# ============================================================

def show_payment_method_admin(
    phone,
    method
):
    if not is_admin(phone):
        return

    labels = {
        "bit": "📱 Bit",
        "paybox": "📲 PayBox",
        "bank": "🏦 העברה בנקאית",
    }

    label = labels.get(
        method,
        method
    )

    enabled = payment_method_enabled(
        method
    )

    details = get_payment_method_details(
        method
    )

    send_buttons(
        phone,
        (
            f"{label}\n\n"
            f"מצב: "
            f"{'🟢 פעיל' if enabled else '🔴 כבוי'}\n\n"
            f"פרטים:\n"
            f"{details or 'לא הוגדרו'}"
        ),
        [
            (
                f"payment_method_toggle_{method}",
                "🔘 הפעלה / כיבוי"
            ),
            (
                f"payment_method_edit_{method}",
                "✏️ עדכון פרטים"
            ),
            (
                "admin_payments",
                "↩️ חזרה"
            ),
        ],
        header="הגדרות תשלום"
    )


def toggle_payment_method(
    phone,
    method
):
    if not is_admin(phone):
        return False

    key_map = {
        "bit":
            "payment_bit_enabled",

        "paybox":
            "payment_paybox_enabled",

        "bank":
            "payment_bank_enabled",

        
    }

    key = key_map.get(
        method
    )

    if not key:
        return False

    current = payment_method_enabled(
        method
    )

    set_setting(
        key,
        (
            "0"
            if current
            else "1"
        )
    )    
    return True


def start_payment_method_details_update(
    phone,
    method
):
    if not is_admin(phone):
        return

    if method not in (
        "bit",
        "paybox",
        "bank",
    ):
        return

    save_session(
        phone,
        "admin_payment_method_details",
        {
            "method":
                method,
        }
    )

    send_message(
        phone,
        (
            "✏️ שלח את פרטי התשלום "
            "החדשים כפי שתרצה שיופיעו "
            "לשליח."
        )
    )





# ============================================================
# טיפול בטקסט של הגדרות התשלום
# ============================================================

def handle_subscription_admin_state(
    phone,
    state,
    text
):
    if not is_admin(phone):
        return False

    text = clean_text(
        text
    )

    if state == "admin_subscription_price_amount":
        amount = re.sub(
            r"[^\d]",
            "",
            text
        )

        if not amount:
            send_message(
                phone,
                "❌ שלח מחיר במספרים."
            )
            return True

        price = int(
            amount
        )

        if price <= 0:
            send_message(
                phone,
                "❌ המחיר חייב להיות גדול מאפס."
            )
            return True

        set_setting(
            "subscription_price",
            str(price)
        )        

        clear_session(
            phone
        )

        send_message(
            phone,
            (
                "✅ מחיר המנוי עודכן.\n\n"
                f"💰 {price} ₪ לחודש"
            )
        )

        return True

    if state == "admin_payment_method_details":
        session = get_session(
            phone
        )

        method = (
            session
            .get(
                "data",
                {}
            )
            .get(
                "method"
            )
        )

        key_map = {
            "bit":
                "payment_bit_details",

            "paybox":
                "payment_paybox_details",

            "bank":
                "payment_bank_details",
        }

        key = key_map.get(
            method
        )

        if not key:
            clear_session(
                phone
            )
            return True

        set_setting(
            key,
            text
        )        

        clear_session(
            phone
        )

        send_message(
            phone,
            "✅ פרטי התשלום עודכנו."
        )

        return True

    return False


# ============================================================
# טיפול בכפתורי חלק 8
# ============================================================

def handle_subscription_actions(
    phone,
    action_id
):
    if action_id == "driver_subscription":
        show_driver_subscription(
            phone
        )
        return True

    if action_id == "subscription_payment_methods":
        show_subscription_payment_methods(
            phone
        )
        return True

    if action_id == "subscription_pay_bit":
        send_manual_payment_instructions(
            phone,
            "bit"
        )
        return True

    if action_id == "subscription_pay_paybox":
        send_manual_payment_instructions(
            phone,
            "paybox"
        )
        return True

    if action_id == "subscription_pay_bank":
        send_manual_payment_instructions(
            phone,
            "bank"
        )
        return True

    
    if action_id.startswith(
        "payment_done_"
    ):
        raw_id = action_id.replace(
            "payment_done_",
            "",
            1
        )

        if raw_id.isdigit():
            return driver_mark_payment_done(
                phone,
                int(raw_id)
            )

    if not is_admin(phone):
        return False

    if action_id == "admin_subscription_toggle":
        return toggle_subscriptions(
            phone
        )

    if action_id == "admin_subscription_price":
        start_subscription_price_update(
            phone
        )
        return True

    if action_id == "admin_pending_payments":
        show_pending_payments(
            phone
        )
        return True

    if action_id == "admin_bit_settings":
        show_payment_method_admin(
            phone,
            "bit"
        )
        return True

    if action_id == "admin_paybox_settings":
        show_payment_method_admin(
            phone,
            "paybox"
        )
        return True

    if action_id == "admin_bank_settings":
        show_payment_method_admin(
            phone,
            "bank"
        )
        return True

    

    if action_id.startswith(
        "payment_method_toggle_"
    ):
        method = action_id.replace(
            "payment_method_toggle_",
            "",
            1
        )

        if toggle_payment_method(
            phone,
            method
        ):
            send_message(
                phone,
                "✅ מצב אמצעי התשלום עודכן."
            )

            show_payment_method_admin(
                phone,
                method
            )        

        return True

    if action_id.startswith(
        "payment_method_edit_"
    ):
        method = action_id.replace(
            "payment_method_edit_",
            "",
            1
        )

        start_payment_method_details_update(
            phone,
            method
        )

        return True

    if action_id.startswith(
        "admin_payment_"
    ):
        raw_id = action_id.replace(
            "admin_payment_",
            "",
            1
        )

        if raw_id.isdigit():
            show_admin_payment(
                phone,
                int(raw_id)
            )
            return True

    if action_id.startswith(
        "payment_approve_"
    ):
        raw_id = action_id.replace(
            "payment_approve_",
            "",
            1
        )

        if raw_id.isdigit():
            return approve_manual_payment(
                phone,                int(raw_id)
            )

    if action_id.startswith(
        "payment_reject_"
    ):
        raw_id = action_id.replace(
            "payment_reject_",
            "",
            1
        )

        if raw_id.isdigit():
            return reject_manual_payment(
                phone,
                int(raw_id)
            )

    return False


# ============================================================
# סוף חלק 8
# ============================================================
# ============================================================
# שליחובוט - Shaliachobot
# חלק 9
# ניתוב ראשי + Webhook + חיבור כל חלקי המערכת
# ============================================================


# ============================================================
# בדיקה האם המשתמש יכול להשתמש במערכת
# ============================================================

def check_system_access(phone):
    phone = normalize_phone(
        phone
    )

    if is_admin(phone):
        return True

    if system_is_enabled():
        return True

    maintenance_message = get_setting(
        "maintenance_message",
        (
            "🛠️ שליחובוט נמצא כרגע "
            "בתחזוקה.\n"
            "נחזור לפעילות בהקדם."
        )
    )

    send_message(
        phone,
        maintenance_message
    )

    return False


# ============================================================
# הצגת תפריט לפי תפקיד
# ============================================================

def route_user_to_menu(phone):
    phone = normalize_phone(
        phone
    )

    if is_admin(phone):
        show_admin_menu(
            phone
        )
        return True

    user = get_user(
        phone
    )

    if not user or user["status"] == USER_RESET:
        show_role_choice(
            phone
        )
        return True

    if user["status"] == USER_BLOCKED:
        send_blocked_message(
            phone
        )
        return True

    if user["status"] == USER_PENDING:
        send_pending_approval_message(
            phone,
            user["role"]
        )
        return True

    if user["status"] != USER_APPROVED:
        send_message(
            phone,
            "החשבון אינו פעיל כרגע."
        )
        return True

    if user["role"] == ROLE_DISPATCHER:
        show_dispatcher_menu(
            phone
        )
        return True

    if user["role"] == ROLE_DRIVER:
        show_driver_menu(
            phone
        )
        return True

    show_customer_menu(
        phone
    )

    return True


# ============================================================
# ניתוב פעולות תפריט בסיסיות
# ============================================================

def handle_basic_menu_action(
    phone,
    action_id
):
    if action_id in (
        "menu",
        "main_menu",
    ):
        route_user_to_menu(
            phone
        )
        return True

    if action_id == "admin_menu":
        if is_admin(phone):
            show_admin_menu(
                phone
            )
            return True
    if action_id == "register_customer":
        start_customer_registration(
            phone
        )
        return True

    if action_id == "register_driver":
        start_driver_registration(
            phone
        )
        return True
    if action_id == "customer_menu":
        show_customer_menu(
            phone
        )
        return True

    if action_id == "driver_menu":
        show_driver_menu(
            phone
        )
        return True

    if action_id == "dispatcher_menu":
        if is_dispatcher(phone):
            show_dispatcher_menu(
                phone
            )
            return True

    # --------------------------------------------------------
    # מפרסם
    # --------------------------------------------------------

    if action_id == "customer_new_shipment":
        start_new_shipment(
            phone
        )
        return True

    if action_id == "customer_active_shipments":
        show_customer_active_shipments(
            phone
        )
        return True

    if action_id == "customer_history":
        show_customer_history(
            phone
        )
        return True

    # --------------------------------------------------------
    # שליח
    # --------------------------------------------------------

    if action_id == "driver_available_shipments":
        show_available_shipments_for_driver(
            phone
        )
        return True

    if action_id == "driver_my_shipments":
        show_my_assigned_shipments(
            phone
        )
        return True

    if action_id == "driver_subscription":
        show_driver_subscription(
            phone
        )
        return True

    if action_id == "driver_guide":
        show_driver_guide(
            phone
        )
        return True

    if action_id == "driver_support":
        save_session(
            phone,
            "driver_support_message",
            {}
        )

        send_message(
            phone,
            "💬 כתוב עכשיו את הפנייה שלך לנציג."
        )

        return True

    if action_id in (
        "customer_support",
        "dispatcher_support",
    ):
        category = (
            "פניית מפרסם"
            if action_id == "customer_support"
            else "פניית סדרן"
        )

        save_session(
            phone,
            "general_support_message",
            {"category": category}
        )

        send_message(
            phone,
            "💬 כתוב עכשיו את הפנייה שלך לנציג."
        )

        return True    

    # --------------------------------------------------------
    # סדרן
    # --------------------------------------------------------

    if action_id == "dispatcher_new_shipment":
        start_new_shipment(
            phone
        )
        return True

    if action_id == "dispatcher_shipments":
        show_management_shipments(
            phone,
            [
                SHIP_NEW,
                SHIP_OPEN,
                SHIP_ASSIGNED,
                SHIP_NEEDS_PRICE,
            ],
            "🚚 ניהול משלוחים"
        )
        return True

    if action_id == "dispatcher_price_list":
        show_price_management_menu(
            phone,
            "dispatcher_menu"
        )
        return True

    if action_id == "dispatcher_driver_mode":
        show_available_shipments_for_driver(
            phone
        )
        return True

    # --------------------------------------------------------
    # מנהל
    # --------------------------------------------------------

    if action_id == "admin_support":
        show_admin_support_requests(
            phone
        )
        return True  
    if action_id == "admin_shipments":
        show_admin_shipments_menu(
            phone
        )
        return True
    if action_id == "admin_vehicle_types":
        show_admin_vehicle_types(phone)
        return True
    if action_id == "admin_vehicle_add":
        save_session(
            phone,
            "admin_vehicle_add_name",
            {}
        )
        send_message(
            phone,
            "🚗 *הוספת סוג רכב חדש*\n\n"
            "שלח עכשיו את שם סוג הרכב.\n"
            "לדוגמה: אופנוע / רכב פרטי / מסחרי גדול"
        )
        return True        
    if action_id == "admin_pending_users":
        show_admin_pending_users_menu(
            phone
        )
        return True

    if action_id == "admin_pending_customers":
        show_pending_customers(
            phone
        )
        return True

    if action_id == "admin_pending_drivers":
        show_pending_drivers(
            phone
        )
        return True

    if action_id == "admin_dispatchers":
        show_admin_dispatchers_menu(
            phone
        )
        return True

    if action_id == "admin_blocks":
        show_admin_blocks_menu(
            phone
        )
        return True

    if action_id == "admin_prices":
        show_price_management_menu(
            phone,
            "admin_menu"
        )
        return True

    if action_id == "admin_cities":
        show_admin_cities_menu(
            phone
        )
        return True

    if action_id == "admin_payments":
        show_admin_payments_menu(
            phone
        )
        return True

    if action_id == "admin_statistics":
        send_admin_statistics(
            phone
        )
        return True
    if action_id.startswith("admin_vehicle_type_"):
        try:
            vehicle_id = int(
                action_id.replace("admin_vehicle_type_", "")
            )
        except ValueError:
            return True

        with db() as conn:
            vehicle = conn.execute(
                """
                SELECT id, name, price_extra
                FROM vehicle_types
                WHERE id = ?
                """,
                (vehicle_id,)
            ).fetchone()

        if not vehicle:
            send_message(phone, "❌ סוג הרכב לא נמצא.")
            return True

        send_buttons(
            phone,
            (
                f"🚗 *{vehicle['name']}*\n\n"
                f"💰 תוספת מחיר נוכחית: ₪{vehicle['price_extra']}"
            ),
            [
                (
                    f"admin_vehicle_price_{vehicle_id}",
                    "✏️ שינוי מחיר"
                ),
                (
                    f"admin_vehicle_delete_{vehicle_id}",
                    "🗑️ מחיקת סוג רכב"
                ),
            ]
        )
        return True
    if action_id.startswith("admin_vehicle_price_"):
        try:
            vehicle_id = int(
                action_id.replace("admin_vehicle_price_", "")
            )
        except ValueError:
            return True

        save_session(
            phone,
            "admin_vehicle_edit_price",
            {"vehicle_id": vehicle_id}
        )

        send_message(
            phone,
            "💰 שלח עכשיו את תוספת המחיר החדשה בשקלים.\n"
            "לדוגמה: 70\n\n"
            "אם אין תוספת, שלח 0."
        )
        return True

    if action_id.startswith("admin_vehicle_delete_"):
        try:
            vehicle_id = int(
                action_id.replace("admin_vehicle_delete_", "")
            )
        except ValueError:
            return True

        with db() as conn:
            conn.execute(
                "DELETE FROM vehicle_types WHERE id = ?",
                (vehicle_id,)
            )
            conn.commit()

        send_message(phone, "🗑️ סוג הרכב נמחק בהצלחה.")
        show_admin_vehicle_types(phone)
        return True        

    if action_id == "admin_more":
        show_admin_more_menu(
            phone
        )
        return True    
    if action_id == "admin_system_settings":
        show_admin_system_settings(
            phone
        )
        return True

    if action_id == "admin_attention":
        show_admin_attention(
            phone
        )
        return True

    return False


# ============================================================
# ניתוב כל הכפתורים
# ============================================================

def handle_all_actions(
    phone,
    action_id
):
    phone = normalize_phone(
        phone
    )

    action_id = clean_text(
        action_id
    )

    if not action_id:
        return False

    # הסכם שימוש למפרסם
    if action_id in (
        "customer_agreement_accept",
        "customer_agreement_reject",
    ):
        session = get_session(phone)

        if session.get("state") != "register_customer_agreement":
            send_message(
                phone,
                "❌ לא נמצאה הרשמה שממתינה לאישור."
            )
            return True

        if action_id == "customer_agreement_reject":
            clear_session(phone)

            send_message(
                phone,
                (
                    "❌ ההסכם לא אושר.\n"
                    "ההרשמה כמפרסם בוטלה."
                )
            )

            show_role_choice(phone)
            return True

        data = session.get("data") or {}

        full_name = clean_text(
            data.get("full_name", "")
        )

        business_name = clean_text(
            data.get("business_name", "")
        )

        city = resolve_city(
            data.get("city", "")
        )

        if not full_name:
            clear_session(phone)

            send_message(
                phone,
                "❌ פרטי ההרשמה חסרים. יש להתחיל את ההרשמה מחדש."
            )

            show_role_choice(phone)
            return True

        user_id = create_or_update_user(
            phone=phone,
            role=ROLE_CUSTOMER,
            status=USER_PENDING,
            full_name=full_name,
            business_name=business_name,
            city=city
        )

        notify_admin_about_registration(
            user_id
        )

        create_admin_notification(
            "customer_registration",
            "🆕 בקשת הרשמת מפרסם חדשה",
            (
                f"👤 שם: {full_name}\n"
                f"🏢 עסק: {business_name}\n"
                f"📱 טלפון: {normalize_phone(phone)}\n"
                f"📍 עיר: {city}"
            ),
            "user",
            user_id
        )

        clear_session(phone)

        send_message(
            phone,
            (
                "✅ ההסכם אושר.\n\n"
                "📋 בקשת ההרשמה התקבלה.\n"
                f"🏢 עסק: {business_name}\n"
                f"📍 עיר: {city}\n\n"
                "הבקשה הועברה לאישור מנהל.\n"
                "לאחר האישור נעדכן אותך כאן ותוכל להתחיל לפרסם משלוחים."
            )
        )

        return True
    if action_id.startswith("admin_support_view_"):
        request_id = int(
            action_id.replace(
                "admin_support_view_",
                ""
            )
        )

        show_admin_support_request(
            phone,
            request_id
        )
        return True

    if action_id.startswith("admin_support_delete_"):
        request_id = int(
            action_id.replace(
                "admin_support_delete_",
                ""
            )
        )

        delete_admin_support_request(
            phone,
            request_id
        )
        return True        
    # הרשמת שליח - בחירת רכב
    if handle_driver_registration_action(
        phone,
        action_id
    ):
        return True

    # אישור / דחיית הרשמות
    if handle_admin_registration_action(
        phone,
        action_id
    ):
        return True

    # יצירת משלוח
    if handle_new_shipment_action(
        phone,
        action_id
    ):
        return True

    # שליח / בחירת שליח
    if handle_driver_interest_action(
        phone,
        action_id
    ):
        return True

    if handle_shipment_driver_actions(
        phone,
        action_id
    ):
        return True
    if action_id == "customer_guide":
        show_customer_guide(
            phone
        )
        return True
    # משלוחים של מפרסם
    if handle_customer_shipment_actions(
        phone,
        action_id
    ):
        return True

    # ניהול משלוחים
    if handle_management_shipment_actions(
        phone,
        action_id
    ):
        return True

    # מחירון וערים
    if handle_price_city_actions(
        phone,
        action_id
    ):
        return True

    # מנהל
    if handle_admin_management_actions(
        phone,
        action_id
    ):
        return True

    # מנויים ותשלומים
    if handle_subscription_actions(
        phone,
        action_id
    ):
        return True

    # תפריטים
    if handle_basic_menu_action(
        phone,
        action_id
    ):
        return True

    return False


# ============================================================
# ניתוב טקסט לפי state
# ============================================================

def handle_all_text_states(
    phone,
    state,
    text
):
    if state == "admin_vehicle_add_name":
        vehicle_name = text.strip()

        if not vehicle_name:
            send_message(
                phone,
                "❌ שם סוג הרכב לא יכול להיות ריק.\n"
                "שלח שוב את שם סוג הרכב."
            )
            return True

        save_session(
            phone,
            "admin_vehicle_add_price",
            {
                "vehicle_name": vehicle_name
            }
        )

        send_message(
            phone,
            f"🚗 סוג הרכב: *{vehicle_name}*\n\n"
            "💰 עכשיו שלח את תוספת המחיר בשקלים.\n"
            "לדוגמה: 50\n\n"
            "אם אין תוספת מחיר, שלח 0."
        )
        return True
    if state == "admin_vehicle_add_price":
        session = get_session(phone)
        vehicle_name = session.get("data", {}).get("vehicle_name")

        try:
            price_extra = int(text.strip())
            if price_extra < 0:
                raise ValueError
        except (ValueError, TypeError):
            send_message(
                phone,
                "❌ יש לשלוח סכום תקין בשקלים.\n"
                "לדוגמה: 50\n"
                "או 0 אם אין תוספת."
            )
            return True

        code = f"vehicle_{now_ts()}"

        with db() as conn:
            sort_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM vehicle_types"
            ).fetchone()["next_order"]            
            conn.execute(
                """
                INSERT INTO vehicle_types (
                    code,
                    name,
                    price_extra,
                    sort_order,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    code,
                    vehicle_name,
                    price_extra,
                    sort_order,
                    now_ts(),
                    now_ts(),
                )
            )
            conn.commit()

        clear_session(phone)

        send_message(
            phone,
            f"✅ סוג הרכב *{vehicle_name}* נוסף בהצלחה.\n"
            f"💰 תוספת מחיר: ₪{price_extra}"
        )

        show_admin_vehicle_types(phone)
        return True
    if state == "admin_vehicle_edit_price":
        session = get_session(phone)
        vehicle_id = session.get("data", {}).get("vehicle_id")

        try:
            price_extra = int(text.strip())
            if price_extra < 0:
                raise ValueError
        except (ValueError, TypeError):
            send_message(
                phone,
                "❌ יש לשלוח סכום תקין בשקלים.\n"
                "לדוגמה: 70\n"
                "או 0 אם אין תוספת."
            )
            return True

        with db() as conn:
            conn.execute(
                """
                UPDATE vehicle_types
                SET price_extra = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    price_extra,
                    now_ts(),
                    vehicle_id,
                )
            )
            conn.commit()

        clear_session(phone)

        send_message(
            phone,
            f"✅ תעריף סוג הרכב עודכן ל־₪{price_extra}."
        )

        show_admin_vehicle_types(phone)
        return True        
    if state == "driver_support_message":
        clear_session(phone)

        create_support_request(
            phone,
            "פניית שליח",
            message=text
        )

        send_message(
            phone,
            "✅ הפנייה נשלחה לנציג."
        )

        return True
    if state == "general_support_message":
        session = get_session(phone)
        category = session.get("data", {}).get(
            "category",
            "פנייה לנציג"
        )

        clear_session(phone)

        create_support_request(
            phone,
            category,
            message=text
        )

        send_message(
            phone,
            "✅ הפנייה נשלחה לנציג."
        )

        return True        
    # הרשמת מפרסם
    if handle_customer_registration_state(
        phone,
        state,
        text
    ):
        return True

    # הרשמת שליח
    if handle_driver_registration_state(
        phone,
        state,
        text=text,
        media_id="",
        message_type="text"
    ):
        return True

    # יצירת משלוח
    if handle_new_shipment_state(
        phone,
        state,
        text
    ):
        return True

    # זמן הגעה שליח
    if handle_driver_interest_text(
        phone,
        state,
        text
    ):
        return True

    # מחירון
    if handle_price_management_state(
        phone,
        state,
        text
    ):
        return True

    # מחיר ידני למשלוח
    if handle_manual_shipment_price_state(
        phone,
        state,
        text
    ):
        return True

    # ערים וכינויים
    if handle_city_management_state(
        phone,
        state,
        text
    ):
        return True

    # מנהל
    if handle_admin_management_state(
        phone,
        state,
        text
    ):
        return True

    # מנויים
    if handle_subscription_admin_state(
        phone,
        state,
        text
    ):
        return True

    return False


# ============================================================
# טיפול במדיה
# בעיקר צילום תעודה וסלפי בהרשמת שליח
# ============================================================

def handle_all_media_states(
    phone,
    state,
    media_id,
    message_type
):
    if state == "subscription_payment_proof":
        session = get_session(
            phone
        )

        payment_id = (
            session
            .get("data", {})
            .get("payment_id")
        )

        if not payment_id:
            clear_session(phone)
            return True

        user = get_user(phone)

        if not user:
            clear_session(phone)
            return True

        with db() as conn:
            payment = conn.execute(
                """
                SELECT *
                FROM payments
                WHERE id = ?
                LIMIT 1
                """,
                (
                    payment_id,
                )
            ).fetchone()

            if not payment:
                clear_session(phone)
                send_message(
                    phone,
                    "❌ בקשת התשלום לא נמצאה."
                )
                return True

            if payment["user_id"] != user["id"]:
                clear_session(phone)
                return True

            conn.execute(
                """
                UPDATE payments
                SET
                    proof_media_id = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    media_id,
                    PAYMENT_REVIEW,
                    payment_id,
                )
            )            

            conn.commit()

        clear_session(phone)

        send_message(
            phone,
            (
                "✅ צילום התשלום התקבל.\n\n"
                "הבקשה הועברה לאישור המנהל.\n"
                "לאחר האישור המנוי יופעל "
                "ותקבל הודעה."
            )
        )

        if ADMIN_PHONE:
            send_image_by_media_id(
                ADMIN_PHONE,
                media_id,
                "📸 אסמכתא לתשלום מנוי"
            )

            send_buttons(
                ADMIN_PHONE,
                (
                    "💳 תשלום מנוי ממתין לאישור\n\n"
                    f"👤 {user['full_name'] or '-'}\n"
                    f"📱 {user['phone']}\n"
                    f"💰 {payment['amount']} ₪\n"
                    f"💳 אמצעי: {payment['payment_method']}\n"
                    f"🔢 תשלום: {payment_id}"
                ),
                [
                    (
                        f"payment_approve_{payment_id}",
                        "✅ אישור"
                    ),
                    (
                        f"payment_reject_{payment_id}",
                        "❌ דחייה"
                    ),
                ],
                header="אישור תשלום"
            )

        return True

    if handle_driver_registration_state(
        phone,
        state,
        text="",
        media_id=media_id,
        message_type=message_type
    ):
        return True

    return False

# ============================================================
# פקודות טקסט כלליות
# ============================================================

def handle_general_text(
    phone,
    text
):
    normalized = clean_text(
        text
    ).lower()

    # --------------------------------------------------------
    # שליח - סימון פנוי לפי עיר
    # דוגמאות:
    # פ ירושלים
    # פנוי ירושלים
    # --------------------------------------------------------

    if (
        normalized.startswith("פ ")
        or normalized.startswith("פנוי ")
    ):
        user = get_user(
            phone
        )

        if (
            user
            and user["role"] == ROLE_DRIVER
            and user["status"] == USER_APPROVED
        ):
            if normalized.startswith("פנוי "):
                city_text = normalized[len("פנוי "):].strip()
            else:
                city_text = normalized[len("פ "):].strip()

            if not city_text:
                send_message(
                    phone,
                    "❌ יש לרשום עיר.\nלדוגמה: פ ירושלים"
                )
                return True

            city = resolve_city(
                city_text
            )

            set_driver_available(
                user["id"],
                True,
                city
            )

            send_message(
                phone,
                (
                    "🟢 סומנת כפנוי.\n"
                    f"📍 אזור זמינות: {city}"
                )
            )

            return True

    if normalized in (
        "תפוס",
        "לא פנוי",
        "לא זמין",
    ):
        user = get_user(
            phone
        )

        if (
            user
            and user["role"] == ROLE_DRIVER
            and user["status"] == USER_APPROVED
        ):
            set_driver_available(
                user["id"],
                False,
                ""
            )

            send_message(
                phone,
                "🔴 סומנת כתפוס.\nלא יישלחו אליך משלוחים חדשים."
            )

            return True    
    if normalized in (
        "תפריט",
        "התחלה",
        "היי",
        "הי",
        "שלום",
        "menu",
        "start",
    ):
        clear_session(
            phone
        )

        route_user_to_menu(
            phone
        )

        return True

    return False


# ============================================================
# ניתוב הודעה נכנסת אחת
# ============================================================

def process_incoming_message(
    phone,
    text="",
    action_id="",
    media_id="",
    message_type="text"
):
    phone = normalize_phone(
        phone
    )

    if not phone:
        return False

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET last_inbound_at = ?
            WHERE phone = ?
            """,
            (
                now_ts(),
                phone,
            )
        )
        conn.commit()    

    # המנהל תמיד יכול להיכנס.
    if not is_admin(phone):
        if not check_system_access(
            phone
        ):
            return True

    user = get_user(
        phone
    )

    if (
        user
        and user["status"] == USER_BLOCKED
    ):
        send_blocked_message(
            phone
        )
        return True

    # --------------------------------------------------------
    # לחיצה על כפתור / רשימה
    # --------------------------------------------------------

    if action_id:
        if handle_all_actions(
            phone,
            action_id
        ):
            return True

    # --------------------------------------------------------
    # state נוכחי
    # --------------------------------------------------------

    session = get_session(
        phone
    )

    state = session.get(
        "state",
        ""
    )

    # --------------------------------------------------------
    # תמונה / מדיה
    # --------------------------------------------------------

    if media_id:
        if handle_all_media_states(
            phone,
            state,
            media_id,
            message_type
        ):
            return True

    # --------------------------------------------------------
    # טקסט
    # --------------------------------------------------------

    if text:
        if handle_all_text_states(
            phone,
            state,
            text
        ):
            return True

        if handle_general_text(
            phone,
            text
        ):
            return True

    # --------------------------------------------------------
    # אין משתמש - הצגת בחירת תפקיד
    # --------------------------------------------------------

    if not user:
        show_role_choice(
            phone
        )
        return True

    route_user_to_menu(
        phone
    )

    return True


# ============================================================
# חילוץ הודעת WhatsApp מתוך payload
# ============================================================

def extract_whatsapp_event(payload):
    result = {
        "phone": "",
        "text": "",
        "action_id": "",
        "media_id": "",
        "message_type": "",
    }

    try:
        entry = payload.get(
            "entry",
            []
        )

        if not entry:
            return result

        changes = (
            entry[0]
            .get(
                "changes",
                []
            )
        )

        if not changes:
            return result

        value = (
            changes[0]
            .get(
                "value",
                {}
            )
        )

        messages = value.get(
            "messages",
            []
        )

        if not messages:
            return result

        message = messages[0]

        result["phone"] = normalize_phone(
            message.get(
                "from",
                ""
            )
        )

        message_type = message.get(
            "type",
            ""
        )

        result["message_type"] = (
            message_type
        )

        # ----------------------------------------------------
        # טקסט
        # ----------------------------------------------------

        if message_type == "text":
            result["text"] = (
                message
                .get(
                    "text",
                    {}
                )
                .get(
                    "body",
                    ""
                )
            )

        # ----------------------------------------------------
        # תמונה
        # ----------------------------------------------------

        elif message_type == "image":
            result["media_id"] = (
                message
                .get(
                    "image",
                    {}
                )
                .get(
                    "id",
                    ""
                )
            )

            result["text"] = (
                message
                .get(
                    "image",
                    {}
                )
                .get(
                    "caption",
                    ""
                )
            )

        # ----------------------------------------------------
        # interactive
        # ----------------------------------------------------

        elif message_type == "interactive":
            interactive = message.get(
                "interactive",
                {}
            )

            interactive_type = (
                interactive.get(
                    "type",
                    ""
                )
            )

            if interactive_type == "button_reply":
                result["action_id"] = (
                    interactive
                    .get(
                        "button_reply",
                        {}
                    )
                    .get(
                        "id",
                        ""
                    )
                )

            elif interactive_type == "list_reply":
                result["action_id"] = (
                    interactive
                    .get(
                        "list_reply",
                        {}
                    )
                    .get(
                        "id",
                        ""
                    )
                )

    except Exception as exc:
        print(
            "EXTRACT WHATSAPP EVENT ERROR:",
            repr(exc)
        )

    return result


# ============================================================
# Webhook verification
# ============================================================

@app.route(
    "/webhook",
    methods=["GET"]
)
def verify_webhook():
    mode = request.args.get(
        "hub.mode",
        ""
    )

    token = request.args.get(
        "hub.verify_token",
        ""
    )

    challenge = request.args.get(
        "hub.challenge",
        ""
    )

    if (
        mode == "subscribe"
        and token == VERIFY_TOKEN
    ):
        return challenge, 200

    return "Forbidden", 403


# ============================================================
# WhatsApp Webhook
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def whatsapp_webhook():
    try:
        payload = request.get_json(
            silent=True
        ) or {}

        event = extract_whatsapp_event(
            payload
        )

        # עדכוני status אינם הודעה מהמשתמש.
        if not event["phone"]:
            return jsonify(
                {
                    "ok": True
                }
            ), 200

        process_incoming_message(
            phone=event["phone"],
            text=event["text"],
            action_id=event["action_id"],
            media_id=event["media_id"],
            message_type=event["message_type"]
        )

        return jsonify(
            {
                "ok": True
            }
        ), 200

    except Exception as exc:
        print(
            "WEBHOOK ERROR:",
            repr(exc)
        )

        # מחזירים 200 כדי למנוע מ-WhatsApp
        # לשלוח שוב ושוב אותה הודעה.
        return jsonify(
            {
                "ok": False,
                "error": str(exc),
            }
        ), 200


# ============================================================
# Health check
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def health_check():
    return jsonify(
        {
            "ok": True,
            "name": "שליחובוט",
            "service": "whatsapp-bot",
        }
    ), 200


# ============================================================
# תחזוקת מערכת
# ============================================================

def run_system_maintenance():
    try:
        expire_old_subscriptions()
    except Exception as exc:
        print(
            "EXPIRE SUBSCRIPTIONS ERROR:",
            repr(exc)
        )

    try:
        send_subscription_expiry_reminders()
    except Exception as exc:
        print(
            "SUBSCRIPTION REMINDER ERROR:",
            repr(exc)
        )

    try:
        maintain_driver_availability()
    except Exception as exc:
        print(
            "DRIVER AVAILABILITY ERROR:",
            repr(exc)
        )
def maintenance_loop():
    while True:
        time.sleep(5 * 60)

        try:
            run_system_maintenance()
        except Exception as exc:
            print(
                "MAINTENANCE LOOP ERROR:",
                repr(exc)
            )

# ============================================================
# אתחול
# ============================================================

def initialize_shaliachobot():
    init_db()

    try:
        run_system_maintenance()
    except Exception as exc:
        print(
            "SYSTEM MAINTENANCE ERROR:",
            repr(exc)
        )

    threading.Thread(
        target=maintenance_loop,
        daemon=True
    ).start()    

    print(
        "Shaliachobot initialized successfully"
    )


initialize_shaliachobot()


# ============================================================
# סוף חלק 9
# ============================================================
