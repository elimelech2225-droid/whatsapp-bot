Build a production-ready WhatsApp delivery marketplace backend from scratch.

IMPORTANT:
This is Stage 1 of a larger system.
Do not build a mockup only.
Create a clean, working backend with persistent storage, proper data models, user states, admin approval flow, role separation, agreements, subscriptions placeholders, payment-proof placeholders, and driver availability/service areas.

VERY IMPORTANT TECHNICAL REQUIREMENTS:
- The code must be syntactically valid and runnable.
- Before finishing, run a full Python syntax validation.
- If this is a Python project, make sure:
  python -m py_compile app.py
  succeeds with no syntax errors.
- Do not leave broken multiline strings.
- Use triple-quoted strings for multiline Hebrew text where needed.
- Do not hardcode Meta access tokens, secrets, phone number IDs, or verify tokens.
- Use environment variables for all Meta WhatsApp credentials.
- Preserve any already configured Meta WhatsApp environment variables if they exist.
- Use persistent database storage so users are not erased after restart.
- Add proper error handling and logging.
- Keep the project modular so future stages can be added without rebuilding everything.

SYSTEM LANGUAGE:
All messages shown to customers, drivers and admins must be in Hebrew.
Code, database fields, filenames and internal variable names can be in English.

==================================================
ROLES
==================================================

There are exactly 3 roles:

1. CUSTOMER
2. DRIVER
3. ADMIN

A WhatsApp phone number can be registered as either CUSTOMER or DRIVER.

Never allow one phone number to be both CUSTOMER and DRIVER at the same time.

The selected role becomes permanent after registration is submitted.

Only ADMIN may change a user's role manually later.

==================================================
USER DATABASE MODEL
==================================================

Create a users table/model with at least:

id
phone_number
role
full_name
business_name
email
city
registration_status
agreement_accepted
agreement_version
agreement_accepted_at
admin_approved_at
admin_rejected_at
rejection_reason
is_blocked
subscription_status
subscription_plan
subscription_expiry
created_at
updated_at

phone_number must be unique.

registration_status values:

NEW
REGISTRATION_IN_PROGRESS
WAITING_ADMIN_APPROVAL
APPROVED
REJECTED
BLOCKED

subscription_status values:

NONE
WAITING_PAYMENT
WAITING_ADMIN_PAYMENT_APPROVAL
ACTIVE
EXPIRED
REJECTED

==================================================
FIRST CONTACT
==================================================

When an unknown WhatsApp number sends a message, show:

"""ברוכים הבאים למערכת המשלוחים 🚚

לפני שמתחילים, יש לבחור כיצד ברצונך להירשם.

שים לב:
כל מספר טלפון יכול להיות משויך לסוג חשבון אחד בלבד."""

Show two choices:

"אני לקוח / שולח"
"אני שליח"

Store the selected role temporarily during registration.

Do not allow the user to enter the main system before registration is completed and approved by ADMIN.

==================================================
CUSTOMER REGISTRATION
==================================================

For CUSTOMER, ask step-by-step:

1. Full name
2. Business name - optional
3. City
4. Email - optional

Phone number must be taken automatically from WhatsApp.

After collecting the details, show a summary:

"""נא לבדוק שהפרטים נכונים:

שם: {full_name}
שם העסק: {business_name}
עיר: {city}
אימייל: {email}
מספר WhatsApp: {phone_number}

סוג החשבון: לקוח / שולח"""

Show buttons:

"מאשר את הפרטים"
"עריכת פרטים"

If the customer chooses edit, allow editing before continuing.

==================================================
CUSTOMER AGREEMENT
==================================================

After customer details are confirmed, show a Hebrew agreement.

The agreement must explain clearly and professionally:

- The customer confirms that shipment information supplied is accurate.
- The customer may not request delivery of illegal, prohibited, dangerous or restricted items.
- The customer is responsible for properly describing the shipment.
- The customer must provide correct pickup and delivery information.
- The platform connects customers with independent drivers.
- Delivery times may be affected by traffic, weather, driver availability and other circumstances.
- Cancellation requests may require administrator approval.
- If a driver already accepted a shipment, cancellation is not automatic.
- Payments, subscriptions and delivery charges are subject to the selected plan and applicable terms.
- The platform may suspend or block accounts that misuse the service.
- Relevant shipment information may be shared with the driver assigned to the shipment.
- The customer agrees that registration, shipment, status and payment records may be stored for operating the service.

At the end show:

"אני מאשר שקראתי והבנתי את התנאים."

Buttons:

"אני מסכים"
"איני מסכים"

If "איני מסכים":
stop registration.

If "אני מסכים":

set:

agreement_accepted = true
agreement_version = "1.0"
agreement_accepted_at = current timestamp

then set:

registration_status = WAITING_ADMIN_APPROVAL

Send:

"""ההרשמה התקבלה ✅

החשבון שלך ממתין כעת לאישור מנהל.

לאחר אישור המנהל תקבל הודעה אוטומטית ולאחר מכן תוכל להשתמש במערכת."""

==================================================
DRIVER REGISTRATION
==================================================

For DRIVER ask step-by-step:

1. Full name
2. City
3. Vehicle type
4. Vehicle number - optional
5. Service areas

Vehicle type options:

"רכב פרטי"
"אופנוע / קטנוע"
"רכב מסחרי"
"אחר"

Phone number comes automatically from WhatsApp.

==================================================
DRIVER SERVICE AREAS
==================================================

Create a driver_service_areas table/model.

Fields:

id
driver_id
city
is_active
created_at
updated_at

The driver must be able to:

- Search city by name
- Add multiple cities
- Remove cities later
- Choose "כל הארץ"

Do not force the driver to scroll through a huge list of all cities.

Support text-based city search.

Also support the special value:

"כל הארץ"

==================================================
DRIVER AVAILABILITY
==================================================

Create driver availability status.

Values:

OFFLINE
AVAILABLE
BUSY

Default:

OFFLINE

Driver menu must later support:

"אני פנוי"
"אני לא פנוי"

When driver chooses "אני פנוי":

set availability to AVAILABLE

Send:

"סומן שאתה פנוי לקבלת משלוחים ✅"

When driver chooses "אני לא פנוי":

set availability to OFFLINE

Send:

"לא יישלחו אליך משלוחים חדשים עד שתסמן שאתה פנוי."

==================================================
DRIVER AGREEMENT
==================================================

Before submitting driver registration, show a Hebrew driver agreement.

It must include:

- The driver agrees to perform accepted deliveries responsibly and faithfully.
- The driver must only accept deliveries they intend and are able to complete.
- The driver must protect customer and recipient privacy.
- The driver must comply with traffic laws and all applicable laws.
- The driver is responsible for valid license, insurance and legal authorization for the vehicle.
- The driver must protect the shipment while it is in their possession.
- The driver may not intentionally delay, misuse, open, steal or damage a shipment.
- The driver must update shipment status accurately.
- The driver must report problems immediately.
- The platform connects drivers and customers.
- The platform may suspend or block a driver for misconduct, abuse or repeated service problems.
- Releasing a driver from an accepted shipment may require administrator approval.
- The driver agrees to applicable subscription/payment terms.

Buttons:

"אני מסכים"
"איני מסכים"

If not accepted:
stop registration.

If accepted:

agreement_accepted = true
agreement_version = "1.0"
agreement_accepted_at = current timestamp

registration_status = WAITING_ADMIN_APPROVAL

Send:

"""ההרשמה שלך כשליח התקבלה ✅

הפרטים הועברו למנהל לבדיקה.

עד לאישור המנהל לא ניתן לקבל משלוחים."""

==================================================
ADMIN REGISTRATION APPROVAL
==================================================

Create an ADMIN management section for pending registrations.

ADMIN must see:

User ID
Full name
Phone number
Role
City
Business name if customer
Vehicle type if driver
Driver service areas
Agreement accepted date
Registration date

For every pending user show:

"אשר הרשמה"
"דחה הרשמה"
"חסום משתמש"

If ADMIN approves:

registration_status = APPROVED
admin_approved_at = current timestamp

Send customer:

"""ההרשמה שלך אושרה ✅

ברוך הבא למערכת.

כעת ניתן להתחיל להשתמש בשירות ולפתוח משלוחים."""

Send driver:

"""ההרשמה שלך כשליח אושרה ✅

ברוך הבא למערכת.

כעת ניתן להיכנס לתפריט השליח ולהגדיר זמינות ואזורי פעילות."""

If ADMIN rejects:

ask ADMIN for optional rejection reason.

Set:

registration_status = REJECTED
admin_rejected_at = current timestamp
rejection_reason = entered reason

Send:

"""ההרשמה לא אושרה.

סיבה:
{rejection_reason}

לפרטים נוספים ניתן לפנות למנהל."""

==================================================
ACCESS CONTROL
==================================================

Very important:

Users with:

WAITING_ADMIN_APPROVAL
REJECTED
BLOCKED

must not access the main system.

If WAITING_ADMIN_APPROVAL sends a message:

"החשבון שלך עדיין ממתין לאישור מנהל."

If REJECTED:

"החשבון שלך אינו מאושר כרגע."

If BLOCKED:

"החשבון שלך חסום. יש לפנות למנהל."

Only APPROVED users may enter the main menus.

==================================================
CUSTOMER MAIN MENU
==================================================

For approved CUSTOMER prepare this menu:

"הזמנת משלוח חדש"
"המשלוחים שלי"
"בקשת ביטול"
"מנוי ותשלומים"
"עדכון פרטים"
"צור קשר / תמיכה"

Do not fully implement shipment creation yet.

Create placeholders/backend routes/functions for Stage 2.

==================================================
DRIVER MAIN MENU
==================================================

For approved DRIVER prepare:

"אני פנוי"
"אני לא פנוי"
"אזורי הפעילות שלי"
"משלוחים פתוחים"
"המשלוחים שלי"
"מדריך לשליח"
"מנוי ותשלומים"
"עדכון פרטים"
"צור קשר / תמיכה"

==================================================
DRIVER GUIDE
==================================================

Create a permanent driver guide.

It must explain in Hebrew:

- איך מסמנים "אני פנוי"
- איך מסמנים "אני לא פנוי"
- איך בוחרים אזורי פעילות
- איך מוסיפים עיר
- איך מסירים עיר
- איך בוחרים "כל הארץ"
- מה הם משלוחים פתוחים
- מה קורה כאשר שליח לוקח משלוח
- מה פירוש "אני בדרך לאיסוף"
- מה פירוש "אספתי"
- מה פירוש "בדרך ליעד"
- מה פירוש "נמסר"
- כיצד מבקשים להשתחרר ממשלוח
- כיצד פונים למנהל
- כיצד עובד המנוי

Prepare the backend so these shipment status actions can be added later.

==================================================
SUBSCRIPTIONS
==================================================

Prepare subscription support for both customers and drivers.

Do not require online credit-card integration at this stage.

Support plans such as:

CUSTOMER:
50 ILS monthly
100 ILS monthly

DRIVER:
50 ILS monthly
100 ILS monthly

The exact plan features can be edited later.

Create subscription fields/models now.

==================================================
MANUAL PAYMENT METHODS
==================================================

Prepare manual payment flow.

Supported payment methods:

BIT
BANK_TRANSFER

The admin must be able to configure:

Bit payment phone number
Bank name
Branch number
Account number
Account holder name

User flow:

1. User chooses a subscription plan.
2. User chooses payment method.
3. System shows payment instructions.
4. User pays outside the system.
5. User clicks:

"ביצעתי תשלום"

6. User uploads proof/screenshot.
7. Payment status becomes:

WAITING_ADMIN_PAYMENT_APPROVAL

8. ADMIN receives the payment request.

ADMIN buttons:

"אשר תשלום"
"דחה תשלום"

If approved:

payment status = APPROVED
subscription_status = ACTIVE
subscription start date = current date
subscription expiry = based on plan duration

Send:

"התשלום אושר והמנוי הופעל בהצלחה ✅"

If rejected:

payment status = REJECTED

ADMIN may enter a rejection reason.

Send:

"""התשלום לא אושר.

סיבה:
{rejection_reason}

ניתן לשלוח אישור תשלום חדש."""

==================================================
PAYMENT DATA MODEL
==================================================

Create payments table/model:

id
user_id
subscription_plan
amount
payment_method
payment_status
proof_file_url
submitted_at
approved_at
rejected_at
rejection_reason
approved_by_admin_id

Payment statuses:

WAITING_PROOF
WAITING_ADMIN_PAYMENT_APPROVAL
APPROVED
REJECTED

Create payment_proofs table/model if needed.

==================================================
CANCELLATION REQUEST INFRASTRUCTURE
==================================================

Prepare a cancellation_requests table/model now for future shipment cancellations.

Fields:

id
shipment_id
requested_by_user_id
reason
status
requested_at
approved_at
rejected_at
admin_id

Statuses:

WAITING_ADMIN_APPROVAL
APPROVED
REJECTED

Future rule:

If customer requests cancellation after a driver accepted the shipment, do not cancel automatically.

ADMIN must see:

"אשר ביטול"
"דחה ביטול"

If approved:
shipment becomes cancelled.

If rejected:
shipment continues.

Do not fully implement shipment cancellation yet.
Only create the infrastructure.

==================================================
FUTURE-READY DATA MODELS
==================================================

Create clean scalable models/tables for:

users
driver_profiles
driver_service_areas
shipments
shipment_status_history
subscriptions
payments
payment_proofs
cancellation_requests
admin_actions
notifications

Suggested shipment statuses for future use:

DRAFT
WAITING_ADMIN_APPROVAL
OPEN
ACCEPTED
DRIVER_ON_THE_WAY_TO_PICKUP
PICKED_UP
ON_THE_WAY_TO_DESTINATION
DELIVERED
CANCELLATION_REQUESTED
CANCELLED

Do not fully implement shipment flow yet.

==================================================
ADMIN ACTION LOG
==================================================

Create admin_actions table/model.

Save actions such as:

REGISTER_APPROVED
REGISTER_REJECTED
USER_BLOCKED
PAYMENT_APPROVED
PAYMENT_REJECTED
CANCELLATION_APPROVED
CANCELLATION_REJECTED

Fields:

id
admin_id
target_user_id
action_type
reference_id
notes
created_at

==================================================
WHATSAPP INTEGRATION RULES
==================================================

Use the existing Meta WhatsApp Cloud API configuration if environment variables already exist.

Do not delete existing Meta settings.

Never hardcode:

ACCESS_TOKEN
APP_SECRET
VERIFY_TOKEN
PHONE_NUMBER_ID

Read them from environment variables.

Prepare webhook handling for incoming WhatsApp messages.

Use phone number as the main unique user identity.

Preserve conversation state between messages.

Do not create duplicate users.

==================================================
CODE QUALITY
==================================================

The code must be modular.

Separate concerns where possible, for example:

app.py
models.py
database.py
services/
whatsapp/
admin/
config.py

Use whichever structure best fits the existing project.

Add comments.

Validate user input.

Handle missing data safely.

Handle unexpected WhatsApp messages safely.

Do not crash if a user sends unsupported text.

Do not crash on empty fields.

Do not expose admin functionality to CUSTOMER or DRIVER.

Do not expose CUSTOMER functionality to DRIVER.

Do not expose DRIVER functionality to CUSTOMER.

==================================================
FINAL VALIDATION
==================================================

Before you finish:

1. Check all files for syntax errors.
2. If Python is used, run:
   python -m py_compile app.py
3. Fix every syntax error before finishing.
4. Make sure the app can start.
5. Make sure multiline Hebrew messages are valid strings.
6. Make sure no environment secrets are hardcoded.
7. Make sure the database is persistent.
8. Make sure registration state survives restart.

At the end, explain:

- Which files were created
- Which files were modified
- Which database models/tables were created
- How CUSTOMER registration works
- How DRIVER registration works
- How ADMIN approval works
- How driver availability works
- How service-area selection works
- How subscription/payment proof flow is prepared
- How to test a CUSTOMER registration
- How to test a DRIVER registration
- How to test ADMIN approval
- Whether the application passed syntax validation
- What remains for Stage 2

Do not proceed to Stage 2 automatically.
