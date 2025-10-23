import os
from datetime import datetime
from flask import Flask, request, jsonify
from excel_writer import append_row, register_csv_route
from price_store import load_prices, find_price_reply

def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

app = Flask(__name__)
register_csv_route(app)  # exposes /export.csv

IG_VERIFY_TOKEN = os.getenv("IG_VERIFY_TOKEN", "dev_token")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "time": now_iso()})

# Meta webhook verification (GET)
@app.route("/webhook/instagram", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == IG_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# Webhook receiver (POST)
@app.route("/webhook/instagram", methods=["POST"])
def receive_ig():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    # Extract basic fields from IG payload
    message_text = ""
    username = "unknown"
    ts = now_iso()

    try:
        entry = (data.get("entry") or [])[0]
        changes = (entry.get("changes") or [])[0]
        value = changes.get("value", {}) if isinstance(changes, dict) else {}
        msgs = value.get("messages") or []
        if msgs:
            message_text = (msgs[0].get("text") or "").strip()
            ts = (msgs[0].get("timestamp") or ts)
        from_obj = value.get("from") or {}
        username = from_obj.get("username", username)
    except Exception:
        pass

    # Load prices from Excel and compute auto-reply text
    prices_map = load_prices()
    reply_text = find_price_reply(message_text, prices_map)

    # Log to CSV (including reply text)
    try:
        append_row({
            "timestamp": ts,
            "username": username,
            "message": message_text,
            "channel": "instagram",
            "reply": reply_text
        })
        # NOTE: This does NOT send a DM back yet. It only logs what we WOULD reply.
        return jsonify({"status": "ok", "reply": reply_text}), 200
    except Exception as e:
        return jsonify({"status": "csv_write_error", "error": str(e)}), 200

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
