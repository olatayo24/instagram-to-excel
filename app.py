import os, json, shutil, requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response
from excel_writer import register_csv_route  # keeps /export.csv route if you want; we’ll swap to DB below
from price_store import load_prices, find_price_reply
from db import upsert_product, fetch_products, insert_message, stream_messages_csv

def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

app = Flask(__name__)

IG_VERIFY_TOKEN = os.getenv("IG_VERIFY_TOKEN", "dev_token")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")  # set in Step 4
GRAPH_URL = "https://graph.facebook.com/v21.0/me/messages"

# ---- Seed products into DB from Excel once (optional) ----
def seed_products_from_excel_once():
    # Only if DB is empty
    products = fetch_products()
    if products:
        return
    # Load from repo Excel (data/prices.xlsx) or /tmp/prices.xlsx if you kept that
    prices_map = load_prices()  # This still reads PRICES_XLSX or /tmp variant in your price_store.py
    for name, price in prices_map.items():
        upsert_product(name, price)

seed_products_from_excel_once()

@app.get("/health")
def health():
    return jsonify({"ok": True, "time": now_iso()})

# Webhook verify
@app.get("/webhook/instagram")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == IG_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# Generate CSV from DB (replaces file-based export)
@app.get("/export.csv")
def export_csv_db():
    data = stream_messages_csv()
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=instagram_messages.csv"})

def lookup_price_reply(message_text: str) -> str:
    # Fetch products from DB and do simple contains match
    prods = fetch_products()  # list of (name, price)
    msg = (message_text or "").lower()
    # try longest product names first
    for name, price in sorted(prods, key=lambda x: len(x[0]), reverse=True):
        if name in msg:
            return f"The price for {name.title()} is {price}." if price else f"I have {name.title()} but the price is not set yet."
    return "Please specify the exact product name (e.g., 'AirPods', 'iPhone 14', 'PS5')."

def send_ig_reply(recipient_id: str, text: str):
    if not PAGE_ACCESS_TOKEN or not recipient_id:
        return {"skipped": True, "reason": "missing token or recipient id"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    r = requests.post(
        GRAPH_URL,
        params={"access_token": PAGE_ACCESS_TOKEN},
        json=payload,
        timeout=15
    )
    try:
        return r.json()
    except Exception:
        return {"status_code": r.status_code, "text": r.text}

@app.post("/webhook/instagram")
def receive_ig():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    # Extract IG message
    message_text = ""
    username = "unknown"
    sender_id = ""  # IMPORTANT for replying
    ts = now_iso()

    try:
        entry = (data.get("entry") or [])[0]
        changes = (entry.get("changes") or [])[0]
        value = changes.get("value", {}) if isinstance(changes, dict) else {}
        msgs = value.get("messages") or []
        if msgs:
            m0 = msgs[0]
            message_text = (m0.get("text") or "").strip()
            ts = (m0.get("timestamp") or ts)
        from_obj = value.get("from") or {}
        username = from_obj.get("username", username)
        sender_id = from_obj.get("id", "")  # Instagram Scoped ID – Meta provides this in real payloads
    except Exception:
        pass

    # Price lookup via DB
    reply_text = lookup_price_reply(message_text)

    # Log to DB
    try:
        insert_message(ts, username, sender_id, message_text, reply_text, "instagram")
    except Exception as e:
        # don't block replies if DB insert fails
        pass

    # Send actual IG reply (if PAGE_ACCESS_TOKEN + sender_id are present)
    api_result = send_ig_reply(sender_id, reply_text)

    return jsonify({"status": "ok", "reply": reply_text, "ig_send": api_result}), 200

@app.get("/")
def root():
    return "OK", 200
