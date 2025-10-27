import os, csv, io
from contextlib import contextmanager
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create tables if not exist
with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS products (
      id SERIAL PRIMARY KEY,
      name TEXT UNIQUE NOT NULL,
      price TEXT
    );
    """))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS messages (
      id SERIAL PRIMARY KEY,
      ts TIMESTAMPTZ NOT NULL,
      username TEXT,
      sender_id TEXT,
      message TEXT,
      reply TEXT,
      channel TEXT
    );
    """))

def upsert_product(name: str, price: str):
    with engine.begin() as conn:
        conn.execute(text("""
          INSERT INTO products(name, price)
          VALUES (:n, :p)
          ON CONFLICT (name) DO UPDATE SET price = EXCLUDED.price
        """), {"n": name.lower(), "p": price})

def fetch_products():
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT name, price FROM products")).fetchall()
        return [(r[0], r[1]) for r in rows]

def insert_message(ts_iso: str, username: str, sender_id: str, message: str, reply: str, channel: str="instagram"):
    # Ensure timestamp
    try:
        ts = datetime.fromisoformat(ts_iso.replace("Z","+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(text("""
          INSERT INTO messages (ts, username, sender_id, message, reply, channel)
          VALUES (:ts, :user, :sid, :msg, :rep, :ch)
        """), {"ts": ts, "user": username, "sid": sender_id, "msg": message, "rep": reply, "ch": channel})

def stream_messages_csv():
    # return bytes for CSV download
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp","username","sender_id","message","channel","reply"])
    with engine.begin() as conn:
        for r in conn.execute(text("""
            SELECT ts, username, sender_id, message, channel, reply
            FROM messages
            ORDER BY ts DESC
        """)):
            writer.writerow([r.ts.isoformat(), r.username or "", r.sender_id or "", r.message or "", r.channel or "", r.reply or ""])
    return output.getvalue().encode("utf-8")
