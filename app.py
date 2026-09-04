Build the first stage of a complete WhatsApp delivery marketplace system.

IMPORTANT:
Do not build a demo or mockup only.
Create the real backend structure, database models, user states, admin approval flow, and WhatsApp-ready logic so later stages can be added without rebuilding the system.

SYSTEM LANGUAGE:
All messages shown to users must be in Hebrew.
Code, variable names, database fields and internal technical logic can be in English.

USER TYPES:
There are exactly 3 roles:
1. CUSTOMER
2. DRIVER
3. ADMIN

A phone number can be registered as EITHER CUSTOMER OR DRIVER.
Never allow the same phone number to have both roles.

The role becomes permanent after registration is submitted.
Only an ADMIN may manually change it later.

========================
DATABASE / USER MODEL
========================

Create a users table/model with at least:

id
phone_number - unique
role - CUSTOMER / DRIVER / ADMIN
full_name
business_name - optional
email - optional
city
registration_status
agreement_accepted
agreement_version
agreement_accepted_at
admin_approved_at
admin_rejected_at
rejection_reason
created_at
updated_at
is_blocked
subscription_status
subscription_plan
subscription_expiry

registration_status values:

NEW
REGISTRATION_IN_PROGRESS
WAITING_ADMIN_APPROVAL
APPROVED
REJECTED
BLOCKED

========================
FIRST MESSAGE / NEW USER
========================

When an unknown WhatsApp number sends a message, show:

"ברוכים הבאים למערכת המשלוחים 🚚

לפני שמתחילים, יש לבחור כיצד ברצונך להירשם.

שים לב:
כל מספר טלפון יכול להיות משויך לסוג חשבון אחד בלבד."

Buttons:

"אני לקוח / שולח"
"אני שליח"

After the user selects a role, store the selected role for the registration process.

Do not allow switching between CUSTOMER and DRIVER after the final registration submission.

========================
CUSTOMER REGISTRATION
========================

For CUSTOMER ask step-by-step:

1. Full name
2. Business name - optional
3. City
4. Email - optional

Then show a summary:

"נא לבדוק שהפרטים נכונים:

שם:
שם העסק:
עיר:
אימייל:
מספר WhatsApp:

סוג החשבון: לקוח / שולח"

Buttons:

"מאשר את הפרטים"
"עריכת פרטים"

After confirmation, show CUSTOMER AGREEMENT.

========================
CUSTOMER AGREEMENT
========================

Create a clear Hebrew agreement screen.

The agreement should include, in simple but professional language:

- The customer confirms that all shipment information supplied is accurate.
- The customer must not request transportation of illegal, prohibited or dangerous items.
- The customer is responsible for properly describing the shipment.
- The customer must provide correct pickup and delivery information.
- The platform connects customers and independent drivers.
- Delivery times may be affected by traffic, weather, availability and other circumstances.
- Cancellation requests may require administrator approval.
- If a driver has already accepted a shipment, cancellation is not automatic.
- Payments, subscriptions and delivery charges are subject to the applicable plan and agreed terms.
- The platform may suspend or block accounts that abuse the service.
- The customer agrees that relevant shipment details may be shared with the driver assigned to the shipment.
- The customer agrees to the system storing registration, shipment, status and payment records as required to operate the service.

At the bottom show:

"אני מאשר שקראתי והבנתי את התנאים."

Buttons:

"אני מסכים"
"איני מסכים"

If "איני מסכים":
Stop registration and do not activate the account.

If "אני מסכים":
Store:
agreement_accepted = true
agreement_version = "1.0"
agreement_accepted_at = current timestamp

Then set:

registration_status = WAITING_ADMIN_APPROVAL

Show:

"ההרשמה התקבלה ✅

החשבון שלך ממתין כעת לאישור מנהל.

לאחר אישור המנהל תקבל הודעה אוטומטית ולאחר מכן תוכל להשתמש במערכת."

========================
DRIVER REGISTRATION
========================

For DRIVER ask step-by-step:

1. Full name
2. City
3. Phone number is taken automatically from WhatsApp
4. Vehicle type:
   - רכב פרטי
   - אופנוע / קטנוע
   - מסחרי
   - אחר

5. Vehicle number - optional for now
6. Areas of operation

For areas of operation, support:

- Multiple cities
- Search by city name
- Ability to add/remove cities later
- Special option:
  "כל הארץ"

Store driver areas separately in a driver_service_areas table/model.

Example:

driver_id
city
is_active
created_at

Also create:

driver_availability_status

Possible values:

OFFLINE
AVAILABLE
BUSY

Default:
OFFLINE

========================
DRIVER AGREEMENT
========================

Before completing registration, show a DRIVER AGREEMENT in Hebrew.

Include:

- The driver agrees to perform accepted deliveries responsibly and faithfully.
- The driver must only accept deliveries they intend and are able to complete.
- The driver must keep customer and recipient information confidential.
- The driver must comply with traffic laws and applicable laws.
- The driver is responsible for having all required licenses, insurance and legal authorization to operate their vehicle.
- The driver must properly protect shipments while in their possession.
- The driver may not intentionally delay, misuse, open, steal or damage a shipment.
- The driver must update shipment status accurately.
- The driver must immediately report problems relating to a shipment.
- The driver understands that the platform connects drivers and customers and that the exact legal relationship may depend on the final terms of service.
- The platform may suspend or block a driver for misconduct, abuse or repeated service problems.
- Cancellation or release from an accepted shipment may require administrator approval.
- The driver agrees to applicable subscription/payment terms.

Buttons:

"אני מסכים"
"איני מסכים"

If accepted:
Store agreement acceptance data and set:

registration_status = WAITING_ADMIN_APPROVAL

Show:

"ההרשמה שלך כשליח התקבלה ✅

הפרטים הועברו למנהל לבדיקה.

עד לאישור המנהל לא ניתן לקבל משלוחים."

========================
ADMIN APPROVAL SYSTEM
========================

Create an admin management section for pending registrations.

ADMIN must be able to see:

User ID
Full name
Phone
Role
City
Business name if customer
Vehicle type if driver
Driver service areas
Agreement accepted date
Registration date

For each registration show buttons:

"אשר הרשמה"
"דחה הרשמה"
"חסום משתמש"

If ADMIN approves:

registration_status = APPROVED
admin_approved_at = current timestamp

Send WhatsApp message:

For customer:

"ההרשמה שלך אושרה ✅
ברוך הבא למערכת.

כעת ניתן להתחיל להשתמש בשירות ולפתוח משלוחים."

For driver:

"ההרשמה שלך כשליח אושרה ✅
ברוך הבא למערכת.

כעת ניתן להיכנס לתפריט השליח ולהגדיר זמינות ואזורי פעילות."

If ADMIN rejects:

Ask ADMIN for optional rejection reason.

Set:
registration_status = REJECTED
admin_rejected_at = current timestamp
rejection_reason = entered reason

Send user:

"ההרשמה לא אושרה.

סיבה:
{rejection_reason}

לפרטים נוספים ניתן לפנות למנהל."

========================
ACCESS CONTROL
========================

Very important:

A user with:
WAITING_ADMIN_APPROVAL
REJECTED
BLOCKED

must NOT be allowed to access the main system.

If WAITING_ADMIN_APPROVAL sends another message, reply:

"החשבון שלך עדיין ממתין לאישור מנהל."

If REJECTED:
"החשבון שלך אינו מאושר כרגע."

If BLOCKED:
"החשבון שלך חסום. יש לפנות למנהל."

Only APPROVED users may continue.

========================
CUSTOMER MAIN MENU
========================

For an approved CUSTOMER prepare the menu structure:

"הזמנת משלוח חדש"
"המשלוחים שלי"
"בקשת ביטול"
"מנוי ותשלומים"
"עדכון פרטים"
"צור קשר / תמיכה"

Do not build the full shipment ordering flow yet.
Only prepare the menu and backend placeholders for the next stage.

========================
DRIVER MAIN MENU
========================

For an approved DRIVER prepare:

"אני פנוי"
"אני לא פנוי"
"אזורי הפעילות שלי"
"משלוחים פתוחים"
"המשלוחים שלי"
"מדריך לשליח"
"מנוי ותשלומים"
"עדכון פרטים"
"צור קשר / תמיכה"

When driver selects:

"אני פנוי"
set:
driver_availability_status = AVAILABLE

Reply:
"סומן שאתה פנוי לקבלת משלוחים ✅"

When driver selects:
"אני לא פנוי"

set:
driver_availability_status = OFFLINE

Reply:
"לא יישלחו אליך משלוחים חדשים עד שתסמן שאתה פנוי."

========================
DRIVER GUIDE
========================

Create a permanent DRIVER GUIDE page/menu.

It should clearly explain in Hebrew:

- איך מסמנים "אני פנוי"
- איך מסמנים "אני לא פנוי"
- איך בוחרים אזורי פעילות
- איך מוסיפים עיר
- איך מסירים עיר
- איך לבחור "כל הארץ"
- מה הם משלוחים פתוחים
- מה קורה כאשר שליח מקבל משלוח
- מה פירוש "אני בדרך לאיסוף"
- מה פירוש "אספתי"
- מה פירוש "בדרך ליעד"
- מה פירוש "נמסר"
- כיצד מבקשים להשתחרר ממשלוח
- כיצד פונים למנהל
- כיצד עובד המנוי

Prepare the system so these shipment status actions can be implemented in the next development stage.

========================
FUTURE-READY TABLES
========================

Prepare database tables/models now for future stages:

shipments
shipment_status_history
driver_service_areas
subscriptions
payments
payment_proofs
cancellation_requests
admin_actions
notifications

Do not fully implement those features yet, but create a clean scalable schema so we do not need to redesign the database later.

========================
IMPORTANT TECHNICAL RULES
========================

1. WhatsApp phone number must be the main unique identity of each user.
2. Never create duplicate user records for the same phone number.
3. Never expose admin functions to customers or drivers.
4. Never expose driver functions to customers.
5. Never expose customer functions to drivers.
6. Preserve conversation state so registration can continue after multiple messages.
7. Validate all user input.
8. Save timestamps for important actions.
9. Keep code modular because more stages will be added.
10. Add clear comments in the code.
11. Do not delete or replace working Meta WhatsApp configuration or environment variables.
12. Use existing WhatsApp Cloud API configuration if already present.
13. Never hardcode access tokens or secrets.
14. Use environment variables for Meta credentials.
15. Create proper error handling and logging.
16. Make sure restarting the application does not erase registered users.
17. Use persistent database storage.
18. Make the design suitable for many customers, drivers and shipments.

When finished, explain exactly:
- which files were created
- which database tables/models were created
- how registration works
- how admin approval works
- how to test a customer registration
- how to test a driver registration
- what remains for Stage 2

Do not proceed to Stage 2 automatically.
