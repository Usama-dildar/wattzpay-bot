import os
account_sid = os.getenv("account_sid")
auth_token = os.getenv("auth_token")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")

from flask import Flask, request
from twilio.rest import Client
import sqlite3
import json
import uuid
from datetime import datetime
import re
import requests



DB_NAME = "wattzpay.db"
FEE_AMOUNT = 3.99

# ********************************************************************
def readable_time():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")

# ********************************************************************
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        name TEXT,
        state TEXT,
        menu_selection TEXT,
        transfer_country TEXT,
        transfer_language TEXT,
        recipient_name TEXT,
        send_amount REAL,
        payout_method TEXT,
        Summary text
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS flow_sessions (
        flow_id TEXT PRIMARY KEY,
        phone TEXT,
        status TEXT,
        menu_selection TEXT,
        transfer_country TEXT,
        transfer_language TEXT,
        recipient_name TEXT,
        send_amount REAL,
        payout_method TEXT,
        summary TEXT,
        started_at TEXT,
        completed_at TEXT
    )
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ********************************************************************
def user_exists(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone FROM users WHERE phone=?", (phone,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# ********************************************************************
def create_user(phone, name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (phone, name, state) VALUES (?, ?, ?)", (phone, name, "welcome_menu"))
    conn.commit()
    conn.close()
    print(f"✅ New user created → {phone} | Name: {name}")

# ********************************************************************
def send_template(user_number, content_sid, variables=None):
    try:
        print(f"📤 Sending template | SID: {content_sid} | Variables: {variables}")
        message = client.messages.create(
            from_=TWILIO_NUMBER,
            to=user_number,
            content_sid=content_sid,
            content_variables=json.dumps(variables or {})
        )
        print(f"✅ Template sent | SID: {message.sid}")
        return True
    except Exception as e:
        print(f"❌ Error sending template | SID: {content_sid} | Error: {e}")
        return False

# ********************************************************************
def get_state(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM users WHERE phone=?", (phone,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ********************************************************************
def update_state(phone, new_state):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state=? WHERE phone=?", (new_state, phone))
    conn.commit()
    conn.close()
    print(f"✅ State updated → {new_state}")

# ********************************************************************
def send_text(user_number, message):
    try:
        print(f"📤 Sending text to {user_number}")
        msg = client.messages.create(from_=TWILIO_NUMBER, to=user_number, body=message)
        print(f"✅ Text sent | SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ Error sending text message: {e}")
        return False

# ********************************************************************
def save_user_reply(phone, column_name, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {column_name}=? WHERE phone=?", (value, phone))
    conn.commit()
    conn.close()
    print(f"✅ Saved {column_name} = {value}")
    flow_id = get_active_flow_id(phone)
    if flow_id:
        conn2 = sqlite3.connect(DB_NAME)
        cursor2 = conn2.cursor()
        try:
            cursor2.execute(f"UPDATE flow_sessions SET {column_name}=? WHERE flow_id=?", (value, flow_id))
            conn2.commit()
        except:
            pass
        conn2.close()

# ********************************************************************
def get_transfer_country(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT transfer_country FROM users WHERE phone=?", (phone,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ********************************************************************
def get_recipient_name(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT recipient_name FROM users WHERE phone = ?", (phone,))
    result = cursor.fetchone()
    conn.close()
    if result is None or result[0] is None:
        return None
    return result[0]

# ********************************************************************
def get_send_amount(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT send_amount FROM users WHERE phone = ?", (phone,))
    result = cursor.fetchone()
    conn.close()
    if result is None or result[0] is None:
        return None
    return result[0]

# ********************************************************************
# flow session functions
# ********************************************************************
def create_flow_session(phone):
    flow_id = "FL-" + str(uuid.uuid4())[:8].upper()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO flow_sessions (flow_id, phone, status, started_at) VALUES (?, ?, 'in_progress', ?)",
        (flow_id, phone, readable_time())
    )
    conn.commit()
    conn.close()
    print(f"✅ Flow session created → Flow ID: {flow_id} | Started: {readable_time()}")
    return flow_id

def get_active_flow_id(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT flow_id FROM flow_sessions WHERE phone=? AND status='in_progress' ORDER BY rowid DESC LIMIT 1",
        (phone,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def complete_flow_session(phone):
    flow_id = get_active_flow_id(phone)
    if flow_id:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE flow_sessions SET status='completed', completed_at=? WHERE flow_id=?",
            (readable_time(), flow_id)
        )
        conn.commit()
        conn.close()
        print(f"✅ Flow session completed → Flow ID: {flow_id} | Time: {readable_time()}")

def reset_flow_session(phone):
    flow_id = get_active_flow_id(phone)
    if flow_id:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE flow_sessions SET status='reset', completed_at=? WHERE flow_id=?",
            (readable_time(), flow_id)
        )
        conn.commit()
        conn.close()
        print(f"✅ Flow session reset → Flow ID: {flow_id} | Time: {readable_time()}")

def reset_user_state(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET
            state='welcome_menu',
            menu_selection=NULL,
            transfer_country=NULL,
            transfer_language=NULL,
            recipient_name=NULL,
            send_amount=NULL,
            payout_method=NULL,
            Summary=NULL
        WHERE phone=?
    """, (phone,))
    conn.commit()
    conn.close()
    print(f"✅ User state reset → {phone}")

# ********************************************************************
# resend correct message based on current state after wrong input
# ********************************************************************
def resend_current_step(phone, state):
    print(f"🔁 Resending current step for state: {state}")
    if state == "welcome_menu":
        send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")
    elif state == "country_selection":
        send_template(phone, "HXae7ede52e7eb7ca4afaa7b4aebc3ce1c")
    elif state == "language_selection":
        country = get_transfer_country(phone)
        send_template(phone, "HX80e728b32952c4b939075817c4098b73", {"country": country})
    elif state == "recipient_name":
        # ✅ Resend phone number prompt
        send_text(phone, "📱 Please enter your recipient's phone number with country code.\n\nExample: *+923001234567*")
    elif state == "transfer_amount":
        country = get_transfer_country(phone)
        send_template(phone, "HXb14726ce37c1b2f86334e71829477288", {"Country": country})
    elif state == "payout_method_selection":
        country = get_transfer_country(phone)
        recipient = get_recipient_name(phone)
        if country == "Nigeria":
            send_template(phone, "HX383f85f373927afa5e524fc0c81a0a4b", {"info": recipient})
        elif country == "Ghana":
            send_template(phone, "HX58a96898988dab39ea3b87ee591b68c6", {"info": recipient})
        elif country == "Jamaica":
            send_template(phone, "HX32ff7a50f85d97fd0d2404b0663bf050", {"info": recipient})
        elif country == "DRC":
            send_template(phone, "HX391f3f3a6c53ed6a33f64c069fdeacbd", {"info": recipient})
        elif country == "Senegal":
            send_template(phone, "HX6c6638a9ddff58645f5bd170eaefd74b", {"info": recipient})
        elif country == "Ivory Coast":
            send_template(phone, "HXd803927289b75c644e021b9699d4e8f5", {"info": recipient})
    elif state == "summary":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT Summary FROM users WHERE phone=?", (phone,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": result[0]})

# ********************************************************************
# warn user + resend exact same step
# ********************************************************************
def warn_and_resend(phone, state, custom_warning=None):
    warning = custom_warning or (
        "⚠️ That reply was not recognised. Please use the options provided below. 👇\n\n"
        "💡 Type *reset* anytime to restart from the beginning."
    )
    send_text(phone, warning)
    resend_current_step(phone, state)

# ********************************************************************
def log_help_activity(phone, name, state, transaction_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO help_logs (phone, name, state, transaction_id) VALUES (?, ?, ?, ?)",
        (phone, name, state, transaction_id)
    )
    conn.commit()
    conn.close()

def init_help_logs_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS help_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            name TEXT,
            state TEXT,
            transaction_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    print("✅ help_logs table ready")

def update_logs_state(phone, new_state):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE help_logs SET state = ? WHERE phone = ?", (new_state, phone))
    conn.commit()
    conn.close()
    print(f"✅ Logs state updated → {new_state}")

def extract_phone_number(text):
    """Extract international phone number like +923001234567"""
    pattern = r"\+\d{10,15}"
    match = re.search(pattern, text)
    return match.group() if match else None

def Logs_state_(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT state FROM help_logs WHERE phone = ? ORDER BY created_at DESC LIMIT 1",
        (phone,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

COUNTRY_INFO = {
    "Nigeria":     {"display": "Nigeria",      "currency_name": "Nigerian Naira",         "currency_code": "NGN"},
    "Ghana":       {"display": "Ghana",        "currency_name": "Ghanaian Cedi",           "currency_code": "GHS"},
    "Jamaica":     {"display": "Jamaica",      "currency_name": "Jamaican Dollar",         "currency_code": "JMD"},
    "DRC":         {"display": "Congo (DRC)",  "currency_name": "Congolese Franc",         "currency_code": "CDF"},
    "Senegal":     {"display": "Senegal",      "currency_name": "West African CFA Franc",  "currency_code": "XOF"},
    "Ivory Coast": {"display": "Ivory Coast",  "currency_name": "West African CFA Franc",  "currency_code": "XOF"},
}

def get_live_exchange_rate(country):
    currency_code = COUNTRY_INFO.get(country, {}).get("currency_code")
    if not currency_code:
        return None
    try:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/USD"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("result") != "success":
            return None
        return float(data["conversion_rates"].get(currency_code))
    except Exception as e:
        print("Exchange API Error:", e)
        return None

# ********************************************************************
def build_transfer_summary(phone, bank):
    country = get_transfer_country(phone)
    recipient = get_recipient_name(phone)
    amount = float(get_send_amount(phone) or 0)
    info = COUNTRY_INFO.get(country)
    if not info:
        return "❌ Invalid country selected."
    rate = get_live_exchange_rate(country)
    if not rate:
        return "❌ Unable to fetch exchange rate."
    amount_after_fee = max(amount - FEE_AMOUNT, 0)
    recipient_amount = amount_after_fee * rate
    summary_text = (
        "■ *Transfer Summary:*\n\n"
        f"You are sending ${amount:.2f} to {recipient}\n"
        f"in {info['display']} — {info['currency_name']} ({info['currency_code']})\n"
        f"via {bank}\n\n"
        f"Fee: ${FEE_AMOUNT:.2f}\n"
        f"Amount After Fee: ${amount_after_fee:.2f}\n"
        f"Exchange Rate: 1 USD = {float(rate):,.2f} {info['currency_code']}\n"
        f"Recipient Receives: {float(recipient_amount):,.2f} {info['currency_code']} ({info['currency_name']})"
    )
    return summary_text

# ============================================================
# Non-text message types (image, audio, video, etc.)
# ============================================================
NON_TEXT_TYPES = ["image", "audio", "video", "document", "sticker", "location", "contacts", "unknown"]

def handle_non_text_message(phone):
    """Reject any non-text/non-interactive message at ANY stage."""
    print(f"🚫 Non-text message from {phone}")
    send_text(
        phone,
        "❌ I can only process *text messages*.\n\n"
        "I cannot process images, voice notes, videos, documents, or stickers.\n\n"
        "Please reply using *text or the buttons* provided. 👇"
    )
    send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")

# ********************************************************************

app = Flask(__name__)
init_db()
init_help_logs_table()

client = Client(account_sid, auth_token)
TWILIO_NUMBER = "whatsapp:+15558804942"

@app.route("/", methods=["POST"])
def whatsapp_bot():

    print("\n========== WEBHOOK RECEIVED ==========")
    for key, value in request.form.items():
        print(f"  {key}: {value}")
    print("=======================================\n")

    try:
        user_number = request.form.get("From")
        phone = user_number

        if not phone:
            print("⚠️ Twilio system webhook — ignoring.")
            return ("", 200)

        profile_name  = request.form.get("ProfileName")
        message_type  = request.form.get("MessageType")
        payload       = request.form.get("ButtonPayload")
        list_id       = request.form.get("ListId")
        msg_body      = request.form.get("Body", "").strip()
        state         = get_state(phone)
        exists        = user_exists(phone)
        logs_state    = Logs_state_(phone)

        print(f"👤 User: {phone} | Name: {profile_name} | Type: {message_type} | State: {state} | Logs State: {logs_state}")

        # ============================================================
        # 🚫 STEP 0 — Block non-text messages at ANY stage (runs first)
        # ============================================================
        if message_type in NON_TEXT_TYPES:
            print(f"🚫 Unsupported message type: {message_type} from {phone}")
            handle_non_text_message(phone)
            return ("", 200)

        # ------------------------------------------------
        # RESET — works at any stage
        # ------------------------------------------------
        if msg_body.lower() == "reset":
            print(f"🔄 RESET requested by {phone}")
            reset_flow_session(phone)
            reset_user_state(phone)
            update_logs_state(phone, None)
            create_flow_session(phone)
            send_text(phone, "🔄 *Your session has been reset.* Starting fresh...")
            send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")
            return ("", 200)

        # ------------------------------------------------
        # NEW USER
        # ------------------------------------------------
        if not exists:
            print(f"🆕 New user detected → {phone}")
            create_user(phone, profile_name)
            create_flow_session(phone)
            send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")
            return ("", 200)

        # ------------------------------------------------
        # RETURNING USER — no active flow
        # ------------------------------------------------
        active_flow = get_active_flow_id(phone)
        print(f"🔑 Active Flow ID: {active_flow}")
        if not active_flow:
            print(f"🔁 No active flow — returning user: {phone}")
            create_flow_session(phone)
            if message_type == "text":
                send_text(phone, "👋 *Welcome back!* Your previous transfer is complete.\n\n⚠️ Please use the buttons below to start a new transfer.\n\n💡 Type *reset* anytime to restart.")
                send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")
                return ("", 200)

        # ------------------------------------------------
        # EXISTING USER — full flow logic
        # ------------------------------------------------
        if exists:

            # ============================================================
            # Check Status — text input step (logs flow, not main flow)
            # Handle FIRST so it doesn't fall into state checks below
            # ============================================================
            if message_type == "text" and logs_state == "Check Status":
                print(f"📝 Transaction ID received → {msg_body}")
                update_logs_state(phone, msg_body)
                send_text(phone, f"✅ Transaction *{msg_body}* is currently being processed. You will receive another update once it's complete. Thank you for your patience!")
                # ✅ Clear logs state so user returns to normal flow
                update_logs_state(phone, None)
                return ("", 200)

            # ============================================================
            # INTERACTIVE — Button payloads
            # ============================================================
            if message_type == "interactive" and payload:
                print(f"🔘 Button clicked → {payload}")

                if payload == "Send Money":
                    update_state(phone, "country_selection")
                    save_user_reply(phone, "menu_selection", payload)
                    state = get_state(phone)
                    send_template(phone, "HXb5df6e8342dd3186dcf5049bc655cd31")
                    return ("", 200)

                elif payload == "history":
                    send_text(phone, "You don't have any transfer history yet.")
                    return ("", 200)

                elif payload == "Help":
                    log_help_activity(phone, profile_name, payload)
                    send_template(phone, "HX413842a19992a9257623980e866169a5")
                    return ("", 200)

                elif payload == "Check Status":
                    update_logs_state(phone, payload)
                    print("✅ Status updated on log database")
                    send_text(phone, "Please enter your Transaction ID (e.g., WP-12345)")
                    return ("", 200)

                elif payload == "Fees & Limits":
                    send_text(phone, "💳 *Fees & Limits*\n\n_No hidden fees. No surprises._\n\n💸 *Fees*\nA small service fee applies per transfer.\nBefore you confirm, you will always see the full breakdown including:\n\n• Exchange rate\n• Transfer fee\n• Total amount your recipient will receive\n\nNothing is charged without your approval.\n\n📊 *Sending Limits*\n\n• Up to $500 per day\n• Up to 10 transactions per day\n\nFor security and compliance purposes, additional verification may be required for certain transactions in line with AML regulations.")
                    return ("", 200)

                elif payload == "Contact Support":
                    send_text(phone, "🌟 For support, please contact us at: 📧 founder@wattzpay.com — ⏱ We typically respond within 24 hours.")
                    return ("", 200)

                elif payload in ["Bank Transfer", "Paga Wallet", "OPay Wallet"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload in ["MTN MoMo", "Vodafone Cash", "AirtelTigo Money"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload in ["Lynk Wallet", "MyCash Wallet", "Bank Transfer"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload in ["Airtel Money", "Orange Money", "M-Pesa"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload in ["Orange Money", "Wave", "MTN MoMo"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload in ["Orange Money", "MTN MoMo"]:
                    save_user_reply(phone, "payout_method", payload)
                    summary_text = build_transfer_summary(phone, payload)
                    save_user_reply(phone, "summary", summary_text)
                    print(f"📋 Summary generated:\n{summary_text}")
                    update_state(phone, "summary")
                    send_template(phone, "HX79b969c252e4a07c81b0df6af67678f8", {"Summary": summary_text})
                    return ("", 200)

                elif payload == "Confirm & Pay" and state == "summary":
                    print(f"✅ Confirm & Pay clicked by {phone}")
                    complete_flow_session(phone)
                    reset_user_state(phone)
                    create_flow_session(phone)
                    send_text(phone, "Click below to securely enter your payment details.\n This link expires in 30 minutes.\n www.test.com")
                    complete_flow_session(phone)
                    reset_user_state(phone)
                    return ("", 200)

                elif payload == "Edit Amount" and state == "summary":
                    update_state(phone, "payout_method_selection")
                    send_text(phone, "Please type the new amount you want to send")
                    return ("", 200)

            # ============================================================
            # INTERACTIVE — List selections (country or amount)
            # ============================================================
            if message_type == "interactive" and list_id:
                print(f"📋 List selected → {list_id}")
                list_id = list_id.strip()

                # ✅ Country selection — update state to recipient_name ONLY here
                if list_id in ["Nigeria", "Ghana", "Jamaica", "DRC", "Senegal", "Ivory Coast"]:
                    update_state(phone, "recipient_name")
                    save_user_reply(phone, "transfer_country", list_id)
                    state = get_state(phone)
                    if state == "recipient_name":
                        save_user_reply(phone, "transfer_language", "Yes, proceed in local language")
                        send_text(phone, "Please enter your recipient's phone number (include country code, e.g. +243XXXXXXXXX)")
                    return ("", 200)

                elif list_id == "Other Amount":
                    send_text(phone, "*Please type the amount you want to send*")
                    update_state(phone, "payout_method_selection")
                    return ("", 200)

                elif list_id in ["20", "40", "60", "80", "100", "200"]:
                    save_user_reply(phone, "send_amount", list_id)
                    update_state(phone, "payout_method_selection")
                    country = get_transfer_country(phone)
                    if country == "Nigeria":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HX383f85f373927afa5e524fc0c81a0a4b", {"info": recipient})
                    if country == "Ghana":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HX58a96898988dab39ea3b87ee591b68c6", {"info": recipient})
                    if country == "Jamaica":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HX32ff7a50f85d97fd0d2404b0663bf050", {"info": recipient})
                    if country == "DRC":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HX6a4ecd021b47fad7e72017a3d2eca3b6", {"info": recipient})
                    if country == "Senegal":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HX6c6638a9ddff58645f5bd170eaefd74b", {"info": recipient})
                    if country == "Ivory Coast":
                        recipient = get_recipient_name(phone)
                        send_template(phone, "HXd803927289b75c644e021b9699d4e8f5", {"info": recipient})
                    return ("", 200)

            # ============================================================
            # STATE: welcome_menu — only buttons allowed
            # ============================================================
            if message_type == "text" and state == "welcome_menu":
                print(f"⚠️ Text at welcome_menu | Message: {msg_body}")
                warn_and_resend(
                    phone, state,
                    custom_warning=(
                        "⚠️ Please use the *buttons* below to continue.\n"
                        "Typing is not supported at this step.\n\n"
                        "💡 Type *reset* anytime to restart."
                    )
                )
                return ("", 200)

            # ============================================================
            # STATE: country_selection — only list selection allowed
            # ============================================================
            if message_type == "text" and state == "country_selection":
                print(f"⚠️ Text at country_selection | Message: {msg_body}")
                warn_and_resend(
                    phone, state,
                    custom_warning=(
                        "⚠️ Please *select a country* from the list below.\n"
                        "Typing is not supported at this step.\n\n"
                        "💡 Type *reset* anytime to restart."
                    )
                )
                return ("", 200)

            # ============================================================
            # STATE: recipient_name — STRICT: only valid phone number
            # ============================================================
            if message_type == "text" and state == "recipient_name":
                print(f"📝 Recipient input received → {msg_body}")
                recipient_number = extract_phone_number(msg_body)

                if not recipient_number:
                    print(f"❌ Invalid phone number input: {msg_body}")
                    warn_and_resend(
                        phone, state,
                        custom_warning=(
                            "⚠️ Invalid input.\n\n"
                            "Please send *only* the recipient's phone number with country code.\n\n"
                            "📱 Example: *+923001234567*\n\n"
                            "💡 Type *reset* anytime to restart."
                        )
                    )
                    return ("", 200)

                # ✅ Valid phone number
                print(f"✅ Valid recipient number → {recipient_number}")
                save_user_reply(phone, "recipient_name", recipient_number)
                update_state(phone, "transfer_amount")
                country = get_transfer_country(phone)
                send_template(phone, "HXb14726ce37c1b2f86334e71829477288", {"Country": country})
                return ("", 200)

            # ============================================================
            # STATE: transfer_amount — only list selection allowed
            # ============================================================
            if message_type == "text" and state == "transfer_amount":
                print(f"⚠️ Text at transfer_amount | Message: {msg_body}")
                warn_and_resend(
                    phone, state,
                    custom_warning=(
                        "⚠️ Please *select an amount* from the list below.\n"
                        "Typing is not supported at this step.\n\n"
                        "💡 Type *reset* anytime to restart."
                    )
                )
                return ("", 200)

            # ============================================================
            # STATE: payout_method_selection — STRICT: only valid number
            # ============================================================
            if message_type == "text" and state == "payout_method_selection":
                print(f"💰 Amount received → {msg_body}")
                try:
                    amount_value = float(msg_body)
                    if amount_value <= 0:
                        raise ValueError("Amount must be positive")
                except ValueError:
                    print(f"❌ Invalid amount input: {msg_body}")
                    warn_and_resend(
                        phone, state,
                        custom_warning=(
                            "⚠️ Invalid amount.\n\n"
                            "Please enter a *valid positive number*.\n\n"
                            "📝 Example: *50* or *120.50*\n\n"
                            "💡 Type *reset* anytime to restart."
                        )
                    )
                    return ("", 200)

                # ✅ Valid amount
                save_user_reply(phone, "send_amount", msg_body)
                country = get_transfer_country(phone)
                if country == "Nigeria":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HX383f85f373927afa5e524fc0c81a0a4b", {"info": recipient})
                if country == "Ghana":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HX58a96898988dab39ea3b87ee591b68c6", {"info": recipient})
                if country == "Jamaica":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HX32ff7a50f85d97fd0d2404b0663bf050", {"info": recipient})
                if country == "DRC":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HX6a4ecd021b47fad7e72017a3d2eca3b6", {"info": recipient})
                if country == "Senegal":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HX6c6638a9ddff58645f5bd170eaefd74b", {"info": recipient})
                if country == "Ivory Coast":
                    recipient = get_recipient_name(phone)
                    send_template(phone, "HXd803927289b75c644e021b9699d4e8f5", {"info": recipient})
                return ("", 200)

            # ============================================================
            # STATE: summary — only buttons allowed
            # ============================================================
            if message_type == "text" and state == "summary":
                print(f"⚠️ Text at summary | Message: {msg_body}")
                warn_and_resend(
                    phone, state,
                    custom_warning=(
                        "⚠️ Please use the *buttons* below to confirm or edit.\n"
                        "Typing is not supported at this step.\n\n"
                        "💡 Type *reset* anytime to restart."
                    )
                )
                return ("", 200)

            # ============================================================
            # ✅ CATCH-ALL — no condition matched
            # Clear everything and restart as fresh user
            # ============================================================
            print(f"⚠️ No condition matched | state: {state} | type: {message_type} | msg: {msg_body} — resetting user")
            reset_flow_session(phone)
            reset_user_state(phone)
            update_logs_state(phone, None)
            create_flow_session(phone)
            send_template(phone, "HX94b41cf3209a07b99325f0c7a3e28c8d")
            return ("", 200)

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    return ("", 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)