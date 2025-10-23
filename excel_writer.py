import os, csv
from flask import send_file, Blueprint, current_app

HEADERS = ["timestamp","username","message","channel"]
CSV_PATH = os.getenv("CSV_PATH", "/data/instagram_messages.csv")

bp_export = Blueprint("export_bp", __name__)

def _ensure_file():
    d = os.path.dirname(CSV_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()

def append_row(row_dict: dict):
    _ensure_file()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writerow({h: row_dict.get(h, "") for h in HEADERS})

@bp_export.route("/export.csv", methods=["GET"])
def export_csv():
    _ensure_file()
    return send_file(CSV_PATH, as_attachment=True)

def register_csv_route(app):
    app.register_blueprint(bp_export)
