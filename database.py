"""SQLite helpers shared by the kiosk app and the admin panel."""
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_number TEXT PRIMARY KEY,
    name           TEXT NOT NULL DEFAULT '',
    department     TEXT NOT NULL DEFAULT '',
    year_level     TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS compartments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name      TEXT NOT NULL,
    compartment_no INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'available',   -- available | borrowed
    UNIQUE(item_name, compartment_no)
);
CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT NOT NULL,
    compartment_id INTEGER NOT NULL,
    item_name      TEXT NOT NULL,
    compartment_no INTEGER NOT NULL,
    otp            TEXT NOT NULL,
    face_photo     TEXT,
    borrowed_at    TEXT NOT NULL,
    returned_at    TEXT,
    status         TEXT NOT NULL DEFAULT 'borrowed',    -- borrowed | returned
    FOREIGN KEY (compartment_id) REFERENCES compartments(id)
);
CREATE INDEX IF NOT EXISTS idx_txn_otp ON transactions(otp, status);
CREATE INDEX IF NOT EXISTS idx_txn_student ON transactions(student_number);
"""


def get_conn():
    os.makedirs(config.CAPTURE_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with closing(get_conn()) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM compartments").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO compartments(item_name, compartment_no) VALUES (?,?)",
                config.COMPARTMENTS,
            )
        conn.commit()


def fetchall(sql, args=()):
    with closing(get_conn()) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def fetchone(sql, args=()):
    with closing(get_conn()) as conn:
        r = conn.execute(sql, args).fetchone()
        return dict(r) if r else None


def execute(sql, args=()):
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid


# ---------------- Students ----------------
def get_student(student_number):
    return fetchone("SELECT * FROM students WHERE student_number=?", (student_number,))


def student_is_complete(student):
    return bool(student) and all((student.get(k) or "").strip()
                                 for k in ("name", "department", "year_level"))


def save_student(student_number, name, department, year_level):
    """Insert or update (used by the kiosk quick registration)."""
    execute(
        """INSERT INTO students(student_number, name, department, year_level)
           VALUES (?,?,?,?)
           ON CONFLICT(student_number) DO UPDATE SET
               name=excluded.name, department=excluded.department, year_level=excluded.year_level""",
        (student_number, name, department, year_level),
    )


def add_student(student_number, name, department, year_level):
    try:
        execute("INSERT INTO students(student_number, name, department, year_level) VALUES (?,?,?,?)",
                (student_number, name, department, year_level))
        return True
    except sqlite3.IntegrityError:
        return False


def update_student(old_sn, new_sn, name, department, year_level):
    with closing(get_conn()) as conn:
        try:
            conn.execute(
                "UPDATE students SET student_number=?, name=?, department=?, year_level=? WHERE student_number=?",
                (new_sn, name, department, year_level, old_sn))
            if old_sn != new_sn:
                conn.execute("UPDATE transactions SET student_number=? WHERE student_number=?", (new_sn, old_sn))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False


def delete_student(student_number):
    """Refuses if the student still has unreturned items."""
    if fetchone("SELECT 1 AS x FROM transactions WHERE student_number=? AND status='borrowed'", (student_number,)):
        return False
    execute("DELETE FROM students WHERE student_number=?", (student_number,))
    return True


def list_students(q=""):
    if q:
        like = f"%{q}%"
        return fetchall("SELECT * FROM students WHERE student_number LIKE ? OR name LIKE ? ORDER BY name", (like, like))
    return fetchall("SELECT * FROM students ORDER BY name")


# ---------------- Compartments / items ----------------
def availability():
    rows = fetchall(
        """SELECT item_name, COUNT(*) AS total,
                  SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available
           FROM compartments GROUP BY item_name ORDER BY MIN(id)""")
    for r in rows:
        r["available"] = r["available"] or 0
    return rows


def list_compartments():
    return fetchall("SELECT * FROM compartments ORDER BY id")


def set_compartment_status(comp_id, status):
    if status in ("available", "borrowed"):
        execute("UPDATE compartments SET status=? WHERE id=?", (status, comp_id))


# ---------------- Borrow / return ----------------
def _new_otp(taken):
    while True:
        otp = f"{secrets.randbelow(900000) + 100000}"
        if otp not in taken:
            return otp


def create_borrow(student_number, cart, photo):
    """cart = {"Basketball": 1, "Volleyball": 1, ...}
    One transaction (and one unique OTP) is created PER ITEM, each bound to a
    specific compartment. Raises ValueError if stock ran out meanwhile."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        taken = {r[0] for r in conn.execute("SELECT otp FROM transactions WHERE status='borrowed'")}
        ts = now_str()
        created = []
        for item, qty in cart.items():
            if qty <= 0:
                continue
            comps = conn.execute(
                """SELECT id, compartment_no FROM compartments
                   WHERE item_name=? AND status='available' ORDER BY compartment_no LIMIT ?""",
                (item, qty)).fetchall()
            if len(comps) < qty:
                raise ValueError(f"Not enough {item} available anymore.")
            for comp in comps:
                otp = _new_otp(taken)
                taken.add(otp)
                cur = conn.execute(
                    """INSERT INTO transactions(student_number, compartment_id, item_name, compartment_no,
                                                otp, face_photo, borrowed_at, status)
                       VALUES (?,?,?,?,?,?,?, 'borrowed')""",
                    (student_number, comp["id"], item, comp["compartment_no"], otp, photo, ts))
                conn.execute("UPDATE compartments SET status='borrowed' WHERE id=?", (comp["id"],))
                created.append({"id": cur.lastrowid, "item_name": item,
                                "compartment_no": comp["compartment_no"], "otp": otp})
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_active_by_otp(otp):
    return fetchone(
        """SELECT t.*, s.name, s.department, s.year_level
           FROM transactions t LEFT JOIN students s ON s.student_number = t.student_number
           WHERE t.otp=? AND t.status='borrowed'""", (otp,))


def complete_return(txn_id):
    """Marks the item returned (OTP becomes unusable) and frees the compartment."""
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT compartment_id FROM transactions WHERE id=? AND status='borrowed'",
                           (txn_id,)).fetchone()
        if not row:
            return None
        ts = now_str()
        conn.execute("UPDATE transactions SET status='returned', returned_at=? WHERE id=?", (ts, txn_id))
        conn.execute("UPDATE compartments SET status='available' WHERE id=?", (row["compartment_id"],))
        conn.commit()
        return ts


def get_logs(q="", status=""):
    sql = """SELECT t.*, s.name, s.department, s.year_level
             FROM transactions t LEFT JOIN students s ON s.student_number = t.student_number
             WHERE 1=1"""
    args = []
    if q:
        sql += " AND (t.student_number LIKE ? OR s.name LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    if status in ("borrowed", "returned"):
        sql += " AND t.status=?"
        args.append(status)
    sql += " ORDER BY t.id DESC"
    return fetchall(sql, args)
