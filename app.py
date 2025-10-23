import os, json
from datetime import datetime
from flask import Flask, request, jsonify
from excel_writer import append_row, HEADERS, register_csv_route

def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

app = Flask(__name__)
register_csv_route(app)  # exposes /export.csv for Power BI

IG_VERIFY_TOKEN = os.getenv("IG_VERIFY_TOKEN", "dev_token")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

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

    # Extract common IG structure
    message_text = ""
    username = "unknown"
    ts = now_iso()

    try:
        entry = (data.get("entry") or [])[0]
        changes = (entry.get("changes") or [])[0]
        value = changes.get("value", {}) if isinstance(changes, dict) else {}
        msgs = value.get("messages") or []
        if msgs:
            message_text = msgs[0].get("text", "") or ""
            ts = msgs[0].get("timestamp", ts) or ts
        from_obj = value.get("from") or {}
        username = from_obj.get("username", username)
    except Exception:
        pass

    # Append to CSV (persistent disk on Render: /data/instagram_messages.csv)
    try:
        append_row({
            "timestamp": ts,
            "username": username,
            "message": message_text.strip(),
            "channel": "instagram"
        })
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "csv_write_error", "error": str(e)}), 200

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
