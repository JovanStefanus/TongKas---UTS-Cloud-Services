import csv
import io
import os
import re
import time

import psycopg
import redis
from flask import Flask, Response, jsonify, render_template, request
from psycopg.rows import dict_row

app = Flask(__name__)

CATEGORIES = ["penjualan", "bahan baku", "gaji", "operasional", "lainnya"]
CACHE_TTL = 30  # detik

cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def get_conn():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        row_factory=dict_row,
    )


def init_db():
    for _ in range(10):
        try:
            with get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        type VARCHAR(10) NOT NULL CHECK (type IN ('income','expense')),
                        amount INTEGER NOT NULL CHECK (amount > 0),
                        description VARCHAR(200) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )""")
                # aman untuk tabel lama: kolom baru ditambahkan bila belum ada
                conn.execute("""
                    ALTER TABLE transactions
                    ADD COLUMN IF NOT EXISTS category VARCHAR(30) NOT NULL DEFAULT 'lainnya'""")
            return
        except psycopg.OperationalError:
            time.sleep(2)


init_db()


# ---------- helper cache (aplikasi tetap jalan walau Redis mati) ----------
def cache_get(key):
    try:
        return cache.get(key)
    except redis.RedisError:
        return None


def cache_set(key, value):
    try:
        cache.setex(key, CACHE_TTL, value)
    except redis.RedisError:
        pass


def cache_invalidate():
    try:
        for k in cache.scan_iter("tx:*"):
            cache.delete(k)
    except redis.RedisError:
        pass


def month_filter(month):
    """Kembalikan (potongan WHERE, params) berdasarkan parameter bulan."""
    if month:
        return (" WHERE to_char(created_at AT TIME ZONE 'Asia/Jakarta','YYYY-MM') = %s", (month,))
    return ("", ())


# ---------- routes ----------
@app.get("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.get("/health")
def health():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        db = "up"
    except Exception:
        return jsonify(status="error", database="down"), 503
    try:
        cache.ping()
        rds = "up"
    except redis.RedisError:
        rds = "down"  # cache opsional, aplikasi tetap sehat
    return jsonify(status="ok", database=db, cache=rds), 200


@app.get("/transactions")
def list_transactions():
    month = request.args.get("month")
    if month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        return jsonify(error="format month harus YYYY-MM"), 400

    key = f"tx:{month or 'all'}"
    cached = cache_get(key)
    if cached:
        resp = app.response_class(cached, mimetype="application/json")
        resp.headers["X-Cache"] = "HIT"
        return resp

    where, params = month_filter(month)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, type, amount, description, category, created_at "
            f"FROM transactions{where} ORDER BY id DESC LIMIT 100", params).fetchall()
        s = conn.execute(f"""
            SELECT COALESCE(SUM(amount) FILTER (WHERE type='income'),0) AS income,
                   COALESCE(SUM(amount) FILTER (WHERE type='expense'),0) AS expense
            FROM transactions{where}""", params).fetchone()

    payload = app.json.dumps(dict(
        items=rows, income=s["income"], expense=s["expense"],
        profit=s["income"] - s["expense"]))
    cache_set(key, payload)
    resp = app.response_class(payload, mimetype="application/json")
    resp.headers["X-Cache"] = "MISS"
    return resp


@app.post("/transactions")
def create_transaction():
    data = request.get_json(silent=True) or {}
    t = data.get("type")
    amount = data.get("amount")
    desc = (data.get("description") or "").strip()
    category = data.get("category", "lainnya")
    if (t not in ("income", "expense") or not isinstance(amount, int)
            or isinstance(amount, bool) or amount <= 0 or not desc
            or category not in CATEGORIES):
        return jsonify(error="type harus income/expense, amount integer > 0, "
                             "description wajib, category harus valid"), 400
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO transactions (type, amount, description, category) "
            "VALUES (%s,%s,%s,%s) "
            "RETURNING id, type, amount, description, category, created_at",
            (t, amount, desc[:200], category)).fetchone()
    cache_invalidate()
    return jsonify(row), 201


@app.delete("/transactions/<int:tx_id>")
def delete_transaction(tx_id):
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM transactions WHERE id = %s RETURNING id", (tx_id,)).fetchone()
    if not row:
        return jsonify(error="transaksi tidak ditemukan"), 404
    cache_invalidate()
    return "", 204


@app.get("/export.csv")
def export_csv():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at, type, category, amount, description "
            "FROM transactions ORDER BY id").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "tanggal", "tipe", "kategori", "jumlah", "keterangan"])
    for r in rows:
        w.writerow([r["id"], r["created_at"].isoformat(), r["type"],
                    r["category"], r["amount"], r["description"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tongkas.csv"})