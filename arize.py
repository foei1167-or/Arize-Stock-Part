"""Arize (อะริเสะ) - ระบบจัดการสต๊อกอะไหล่ ไฟล์เดียวจบ
รัน: python arize.py          (โหมดแชทในหน้าจอดำ)
เว็บ: streamlit run arize_web.py
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

# เก็บไฟล์ฐานข้อมูลไว้โฟลเดอร์เดียวกับไฟล์นี้เสมอ (ไม่ขึ้นกับว่ารันจากโฟลเดอร์ไหน)
DB_PATH = str(Path(__file__).resolve().parent / "arize.db")

# ---------- ตั้งค่าระบบผู้ใช้ (แก้ได้) ----------
ROLES = ("admin", "staff")
MIN_PASSWORD = 6          # รหัสผ่านสั้นสุดกี่ตัว
MAX_FAILED = 5            # ใส่รหัสผิดกี่ครั้งถึงล็อกบัญชี
LOCK_MINUTES = 5          # ล็อกกี่นาที
PBKDF2_ROUNDS = 200_000   # ความหนักในการเข้ารหัสรหัสผ่าน


class StockError(Exception):
    """ข้อผิดพลาดที่แสดงให้ผู้ใช้เห็นได้ เช่น ของไม่พอ / ไม่พบ part"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    part_no    TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT DEFAULT '',
    unit       TEXT DEFAULT 'ชิ้น',
    location   TEXT DEFAULT '',
    qty        INTEGER NOT NULL DEFAULT 0 CHECK (qty >= 0),
    min_qty    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    part_no       TEXT NOT NULL,
    type          TEXT NOT NULL,      -- REGISTER / IN / OUT / ADJUST / EDIT
    qty           INTEGER NOT NULL,   -- จำนวนที่เปลี่ยน (OUT เป็นลบ)
    balance_after INTEGER NOT NULL,
    person        TEXT DEFAULT '',
    note          TEXT DEFAULT '',
    FOREIGN KEY (part_no) REFERENCES parts(part_no)
);
CREATE INDEX IF NOT EXISTS idx_tx_part ON transactions(part_no, ts);
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('admin','staff')),
    active        INTEGER NOT NULL DEFAULT 1,
    failed_count  INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
"""


# ====================== รหัสผ่าน ======================
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(rounds))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,30}$")


class StockDB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        with self._conn() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ---------- helpers ----------
    @staticmethod
    def _norm(part_no: str) -> str:
        return part_no.strip().upper()

    def _get(self, con, part_no):
        row = con.execute("SELECT * FROM parts WHERE part_no=?", (part_no,)).fetchone()
        if not row:
            raise StockError(f"ไม่พบ part '{part_no}' ในระบบ (ต้องลงทะเบียนก่อน)")
        return row

    def _move(self, con, part_no, delta, ttype, person="", note=""):
        part = self._get(con, part_no)
        new_qty = part["qty"] + delta
        if new_qty < 0:
            raise StockError(
                f"{part_no} ({part['name']}) คงเหลือ {part['qty']} {part['unit']} ไม่พอเบิก {-delta}"
            )
        con.execute("UPDATE parts SET qty=? WHERE part_no=?", (new_qty, part_no))
        con.execute(
            "INSERT INTO transactions(ts,part_no,type,qty,balance_after,person,note) VALUES (?,?,?,?,?,?,?)",
            (now(), part_no, ttype, delta, new_qty, person, note),
        )
        return new_qty

    # ---------- operations ----------
    def register_part(self, part_no, name, qty=0, unit="ชิ้น", location="",
                      min_qty=0, category="", person=""):
        part_no = self._norm(part_no)
        if not part_no:
            raise StockError("กรอกรหัส part ด้วย")
        if not name.strip():
            raise StockError("กรอกชื่อ part ด้วย")
        if qty < 0:
            raise StockError("จำนวนเริ่มต้นต้องไม่ติดลบ")
        with self._conn() as con:
            if con.execute("SELECT 1 FROM parts WHERE part_no=?", (part_no,)).fetchone():
                raise StockError(f"part '{part_no}' ถูกลงทะเบียนไว้แล้ว")
            con.execute(
                "INSERT INTO parts(part_no,name,category,unit,location,qty,min_qty,created_at) "
                "VALUES (?,?,?,?,?,0,?,?)",
                (part_no, name.strip(), category, unit, location, min_qty, now()),
            )
            con.execute(
                "INSERT INTO transactions(ts,part_no,type,qty,balance_after,person,note) "
                "VALUES (?,?,?,?,?,?,?)",
                (now(), part_no, "REGISTER", 0, 0, person, "ลงทะเบียน part ใหม่"),
            )
            if qty:
                self._move(con, part_no, qty, "IN", person, "จำนวนเริ่มต้น")
        return self.get_part(part_no)

    def update_part(self, part_no, name, category="", unit="ชิ้น", location="",
                    min_qty=0, person=""):
        """แก้ข้อมูล part (ไม่รวมจำนวนคงเหลือ — ใช้ adjust แทน) และบันทึกลงประวัติ"""
        part_no = self._norm(part_no)
        name, category, unit, location = name.strip(), category.strip(), unit.strip(), location.strip()
        if not name:
            raise StockError("ชื่อ part ห้ามว่าง")
        if min_qty < 0:
            raise StockError("จำนวนขั้นต่ำต้องไม่ติดลบ")
        new = {"name": name, "category": category, "unit": unit or "ชิ้น",
               "location": location, "min_qty": int(min_qty)}
        labels = {"name": "ชื่อ", "category": "หมวด", "unit": "หน่วย",
                  "location": "ที่เก็บ", "min_qty": "ขั้นต่ำ"}
        with self._conn() as con:
            old = self._get(con, part_no)
            changed = [k for k, v in new.items() if old[k] != v]
            if changed:
                con.execute(
                    "UPDATE parts SET name=?, category=?, unit=?, location=?, min_qty=? WHERE part_no=?",
                    (new["name"], new["category"], new["unit"], new["location"], new["min_qty"], part_no))
                detail = ", ".join(f"{labels[k]}: {old[k] or '-'} → {new[k] or '-'}" for k in changed)
                con.execute(
                    "INSERT INTO transactions(ts,part_no,type,qty,balance_after,person,note) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (now(), part_no, "EDIT", 0, old["qty"], person, "แก้ไขข้อมูล " + detail))
        return self.get_part(part_no)

    def delete_part(self, part_no):
        """ลบ part พร้อมประวัติทั้งหมดของ part นั้น (กู้คืนไม่ได้)"""
        part_no = self._norm(part_no)
        with self._conn() as con:
            self._get(con, part_no)
            con.execute("DELETE FROM transactions WHERE part_no=?", (part_no,))
            con.execute("DELETE FROM parts WHERE part_no=?", (part_no,))

    def receive(self, part_no, qty, person="", note=""):
        if qty <= 0:
            raise StockError("จำนวนรับเข้าต้องมากกว่า 0")
        with self._conn() as con:
            self._move(con, self._norm(part_no), qty, "IN", person, note)
        return self.get_part(part_no)

    def issue(self, part_no, qty, person="", note=""):
        if qty <= 0:
            raise StockError("จำนวนเบิกต้องมากกว่า 0")
        with self._conn() as con:
            self._move(con, self._norm(part_no), -qty, "OUT", person, note)
        return self.get_part(part_no)

    def adjust(self, part_no, new_qty, person="", note="ปรับยอดตามการนับจริง"):
        if new_qty < 0:
            raise StockError("ยอดต้องไม่ติดลบ")
        part_no = self._norm(part_no)
        with self._conn() as con:
            cur = self._get(con, part_no)["qty"]
            self._move(con, part_no, new_qty - cur, "ADJUST", person, note)
        return self.get_part(part_no)

    # ---------- queries ----------
    def get_part(self, part_no):
        with self._conn() as con:
            return dict(self._get(con, self._norm(part_no)))

    def search(self, keyword):
        like = f"%{keyword.strip()}%"
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM parts WHERE part_no LIKE ? OR name LIKE ? OR category LIKE ? "
                "OR location LIKE ? ORDER BY part_no", (like,) * 4).fetchall()
        return [dict(r) for r in rows]

    def all_parts(self):
        with self._conn() as con:
            return [dict(r) for r in con.execute("SELECT * FROM parts ORDER BY part_no")]

    def low_stock(self):
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM parts WHERE qty <= min_qty ORDER BY qty").fetchall()
        return [dict(r) for r in rows]

    def history(self, part_no=None, limit=20):
        sql, args = "SELECT * FROM transactions", []
        if part_no:
            sql += " WHERE part_no=?"
            args.append(self._norm(part_no))
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as con:
            return [dict(r) for r in con.execute(sql, args)]

    # ---------- สถิติการใช้งาน ----------
    @staticmethod
    def _since(days: int) -> str:
        """วันแรกของช่วง 'ย้อนหลัง N วัน' (นับรวมวันนี้)"""
        return (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    def usage_by_day(self, days=30):
        """ยอดรับเข้า/เบิกจ่ายรายวัน (ไม่รวมการปรับยอด) -> [{day, in_qty, out_qty}]"""
        with self._conn() as con:
            rows = con.execute(
                "SELECT substr(ts,1,10) AS day, "
                "SUM(CASE WHEN type='IN'  THEN  qty ELSE 0 END) AS in_qty, "
                "SUM(CASE WHEN type='OUT' THEN -qty ELSE 0 END) AS out_qty "
                "FROM transactions WHERE ts >= ? GROUP BY day ORDER BY day",
                (self._since(days),)).fetchall()
        return [dict(r) for r in rows]

    def top_issued(self, days=30, limit=10):
        """part ที่ถูกเบิกมากสุดในช่วงเวลา -> [{part_no, name, out_qty}]"""
        with self._conn() as con:
            rows = con.execute(
                "SELECT t.part_no, p.name, SUM(-t.qty) AS out_qty FROM transactions t "
                "JOIN parts p ON p.part_no = t.part_no "
                "WHERE t.type='OUT' AND t.ts >= ? GROUP BY t.part_no ORDER BY out_qty DESC LIMIT ?",
                (self._since(days), limit)).fetchall()
        return [dict(r) for r in rows]

    # ====================== ผู้ใช้ / การเข้าสู่ระบบ ======================
    @staticmethod
    def _norm_user(username: str) -> str:
        return (username or "").strip().lower()

    @staticmethod
    def _check_new_password(password: str):
        if len(password or "") < MIN_PASSWORD:
            raise StockError(f"รหัสผ่านต้องยาวอย่างน้อย {MIN_PASSWORD} ตัวอักษร")

    def _validate_new_user(self, username, display_name, password, role):
        if not _USERNAME_RE.match(username):
            raise StockError("ชื่อผู้ใช้ต้องเป็นภาษาอังกฤษหรือตัวเลข 3-30 ตัว (ใช้ _ . - ได้)")
        if not (display_name or "").strip():
            raise StockError("กรอกชื่อที่ใช้แสดง (เช่น ชื่อจริง) ด้วย")
        if role not in ROLES:
            raise StockError("สิทธิ์ไม่ถูกต้อง")
        self._check_new_password(password)

    @staticmethod
    def _public(row):
        d = dict(row)
        d.pop("password_hash", None)
        return d

    def user_count(self) -> int:
        with self._conn() as con:
            return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def create_user(self, username, display_name, password, role="staff"):
        username = self._norm_user(username)
        self._validate_new_user(username, display_name, password, role)
        with self._conn() as con:
            if con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                raise StockError(f"ชื่อผู้ใช้ '{username}' ถูกใช้แล้ว")
            con.execute(
                "INSERT INTO users(username,display_name,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                (username, display_name.strip(), hash_password(password), role, now()))
        return self.get_user(username)

    def create_first_admin(self, username, display_name, password):
        """สร้างแอดมินคนแรก (ทำได้เฉพาะตอนยังไม่มีผู้ใช้เลย)"""
        username = self._norm_user(username)
        self._validate_new_user(username, display_name, password, "admin")
        with self._conn() as con:
            if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
                raise StockError("ระบบมีผู้ใช้แล้ว กรุณาเข้าสู่ระบบแทน")
            con.execute(
                "INSERT INTO users(username,display_name,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                (username, display_name.strip(), hash_password(password), "admin", now()))
        return self.get_user(username)

    def get_user(self, username):
        with self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE username=?",
                              (self._norm_user(username),)).fetchone()
        return self._public(row) if row else None

    def list_users(self):
        with self._conn() as con:
            rows = con.execute("SELECT * FROM users ORDER BY role, username").fetchall()
        return [self._public(r) for r in rows]

    def authenticate(self, username, password):
        """ตรวจรหัสผ่าน คืน dict ผู้ใช้ ถ้าผิดจะ raise StockError
        ใส่ผิดครบ MAX_FAILED ครั้ง ล็อกบัญชี LOCK_MINUTES นาที"""
        username = self._norm_user(username)
        generic = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
        error, user = None, None
        with self._conn() as con:
            row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                check_password(password or "", hash_password("dummy"))  # กันเดาชื่อจากเวลาตอบ
                error = generic
            elif row["locked_until"] and row["locked_until"] > now():
                error = f"ใส่รหัสผิดหลายครั้ง บัญชีถูกล็อกถึง {row['locked_until'][11:16]} น."
            elif not check_password(password or "", row["password_hash"]):
                failed = row["failed_count"] + 1
                if failed >= MAX_FAILED:
                    until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
                    con.execute("UPDATE users SET failed_count=0, locked_until=? WHERE username=?",
                                (until, username))
                else:
                    con.execute("UPDATE users SET failed_count=? WHERE username=?", (failed, username))
                error = generic
            elif not row["active"]:
                error = "บัญชีนี้ถูกปิดใช้งาน ติดต่อแอดมิน"
            else:
                con.execute("UPDATE users SET failed_count=0, locked_until='' WHERE username=?",
                            (username,))
                user = self._public(row)
        # raise นอก with เพื่อให้การนับรหัสผิดถูกบันทึกจริง (ไม่โดน rollback)
        if error:
            raise StockError(error)
        return user

    def set_password(self, username, new_password):
        self._check_new_password(new_password)
        with self._conn() as con:
            self._require_user(con, username)
            con.execute("UPDATE users SET password_hash=?, failed_count=0, locked_until='' WHERE username=?",
                        (hash_password(new_password), self._norm_user(username)))

    def change_own_password(self, username, old_password, new_password):
        self.authenticate(username, old_password)
        self.set_password(username, new_password)

    def _require_user(self, con, username):
        row = con.execute("SELECT * FROM users WHERE username=?", (self._norm_user(username),)).fetchone()
        if not row:
            raise StockError(f"ไม่พบผู้ใช้ '{username}'")
        return row

    def _other_active_admins(self, con, username):
        return con.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND username<>?",
            (self._norm_user(username),)).fetchone()[0]

    def set_user_active(self, username, active: bool):
        with self._conn() as con:
            row = self._require_user(con, username)
            if not active and row["role"] == "admin" and not self._other_active_admins(con, username):
                raise StockError("ปิดบัญชีแอดมินคนสุดท้ายไม่ได้")
            con.execute("UPDATE users SET active=? WHERE username=?",
                        (1 if active else 0, self._norm_user(username)))

    def set_user_role(self, username, role):
        if role not in ROLES:
            raise StockError("สิทธิ์ไม่ถูกต้อง")
        with self._conn() as con:
            row = self._require_user(con, username)
            if role != "admin" and row["role"] == "admin" and not self._other_active_admins(con, username):
                raise StockError("ลดสิทธิ์แอดมินคนสุดท้ายไม่ได้")
            con.execute("UPDATE users SET role=? WHERE username=?", (role, self._norm_user(username)))


# ===== Arize AI =====
UNITS = r"(ตัว|ชิ้น|อัน|ชุด|กล่อง|ม้วน|เส้น|pcs|pc)"

# คำสั่งภาษาอังกฤษต้องเป็นคำเต็ม ไม่งั้น 'by' จะไปจับกลางคำอย่าง Ruby / 'min' จับใน Aluminium
_L = r"(?<![A-Za-z])"   # ด้านหน้าห้ามติดตัวอักษรอังกฤษ
_R = r"(?![A-Za-z])"    # ด้านหลังห้ามติดตัวอักษรอังกฤษ
_NOTE = r"(?:หมายเหตุ|" + _L + r"note" + _R + r")\s*[:：]?\s*(.+)$"
_PERSON = r"(?:โดย|" + _L + r"by" + _R + r")\s*[:：]?\s*(\S+)"
_LOC = r"(?:ที่เก็บ|ตำแหน่ง|" + _L + r"(?:location|loc)" + _R + r")\s*[:：]?\s*(\S+)"
_MIN = r"(?:ขั้นต่ำ|" + _L + r"min" + _R + r")\s*[:：]?\s*(\d+)"
_QTY = r"(?:จำนวน|" + _L + r"qty" + _R + r")\s*[:：]?\s*(\d+)\s*" + UNITS + r"?(?=\s|$)"

HELP = """ฉันคืออะริเสะ ผู้ช่วยดูแลสต๊อกอะไหล่ ลองสั่งได้เลย เช่น
• ลงทะเบียน P001 สกรู M3 จำนวน 100 ตัว ที่เก็บ A1 ขั้นต่ำ 20
• รับเข้า P001 50
• เบิก P001 5 หมายเหตุ ซ่อมเครื่อง CNC
• เหลือเท่าไหร่ P001
• ค้นหา สกรู
• ใกล้หมด
• ประวัติ P001   (หรือ "ประวัติ" เฉยๆ เพื่อดูทั้งหมด)
• ปรับยอด P001 80   (เฉพาะแอดมิน)
• รายการทั้งหมด
(ชื่อผู้ทำรายการจะบันทึกจากบัญชีที่ล็อกอินให้อัตโนมัติ)"""

# (intent, คำสั่งไทย [จับจากหัวคำ เพราะภาษาไทยไม่เว้นวรรค], คำสั่งอังกฤษ [ต้องตรงทั้งคำ])
VERBS = [
    ("register", ("ลงทะเบียน", "เพิ่มอะไหล่"), ("register", "add")),
    ("receive", ("รับเข้า", "รับ", "เติม"), ("receive", "in")),
    ("issue", ("เบิก", "จ่าย"), ("issue", "out")),
    ("adjust", ("ปรับยอด",), ("adjust",)),
    ("low", ("ใกล้หมด",), ("low",)),
    ("history", ("ประวัติ",), ("history", "log")),
    ("search", ("ค้นหา", "หา"), ("search", "find")),
    ("check", ("เหลือ", "เช็ค"), ("check", "stock")),
    ("list", ("รายการ", "ทั้งหมด"), ("list",)),
    ("help", ("ช่วย", "สวัสดี"), ("help", "hi", "hello", "?")),
]


def _extract(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    if not m:
        return None, text
    return m, (text[:m.start()] + " " + text[m.end():]).strip()


def _split_verb(words):
    """คืน (intent, args) โดยดูจากคำแรกของประโยคเท่านั้น
    รองรับพิมพ์ติดกัน เช่น 'ค้นหาสกรู' / 'เบิกP001 5'"""
    if not words:
        return None, []
    first = words[0]
    for intent, thai, eng in VERBS:
        for k in thai:
            if first.startswith(k):
                rest = first[len(k):]
                return intent, ([rest] if rest else []) + words[1:]
        if first.lower() in eng:
            return intent, words[1:]
    return None, []


class Arize:
    name = "Arize (อะริเสะ)"

    def __init__(self, db: StockDB | None = None):
        self.db = db or StockDB()

    # ---------- 1) เข้าใจประโยค ----------
    def understand(self, text: str) -> dict:
        t = text.strip()

        m, t = _extract(_NOTE, t)
        note = m.group(1).strip() if m else ""
        m, t = _extract(_PERSON, t)
        person = m.group(1) if m else ""
        m, t = _extract(_LOC, t)
        location = m.group(1) if m else ""
        m, t = _extract(_MIN, t)
        min_qty = int(m.group(1)) if m else 0
        m, t = _extract(_QTY, t)
        qty = int(m.group(1)) if m else None
        unit = (m.group(2) if m and m.group(2) else None)

        base = {"person": person, "note": note, "location": location,
                "min_qty": min_qty, "unit": unit}
        intent, args = _split_verb(t.split())

        def first_int_after_part():
            nonlocal qty
            if qty is None:
                nums = [w for w in args[1:] if w.isdigit()]
                if nums:
                    qty = int(nums[0])

        part = args[0] if args else ""

        if intent == "register":
            if len(args) < 2:
                return {"intent": "unknown", "error": "ระบุ: ลงทะเบียน <รหัส> <ชื่อ> [จำนวน N] [ที่เก็บ X]"}
            return {**base, "intent": "register", "part_no": args[0],
                    "name": " ".join(args[1:]), "qty": qty or 0}
        if intent in ("receive", "issue", "adjust"):
            first_int_after_part()
            return {**base, "intent": intent, "part_no": part, "qty": qty}
        if intent == "low":
            return {"intent": "low"}
        if intent == "history":
            return {"intent": "history", "part_no": part or None}
        if intent == "search":
            return {"intent": "search", "keyword": " ".join(args)}
        if intent == "check":
            ws = [w for w in args if w not in ("เท่าไหร่", "เท่าไร")]
            return {"intent": "check", "part_no": ws[0] if ws else ""}
        if intent == "list":
            return {"intent": "list"}
        if intent == "help":
            return {"intent": "help"}
        return {"intent": "unknown"}

    # ---------- 2) ลงมือทำ ----------
    def handle(self, text: str, user: dict | None = None) -> str:
        """user = {'display_name':..., 'role':...} จากระบบล็อกอิน
        ถ้ามี: ชื่อผู้ทำรายการใช้ชื่อบัญชีนี้เสมอ (ไม่เชื่อสิ่งที่พิมพ์หลัง 'โดย')
        และ 'ปรับยอด' ทำได้เฉพาะแอดมิน   ถ้าไม่ส่งมา (โหมดหน้าจอดำ) ทำได้ทุกอย่าง"""
        cmd = self.understand(text)
        i = cmd["intent"]
        if user:
            cmd["person"] = user["display_name"]
            if i == "adjust" and user.get("role") != "admin":
                return "❌ ปรับยอดได้เฉพาะแอดมินเท่านั้น"
        try:
            if i == "help":
                return HELP
            if i == "unknown":
                return cmd.get("error") or "ขอโทษค่ะ ฉันยังไม่เข้าใจคำสั่งนี้ พิมพ์ 'ช่วย' เพื่อดูตัวอย่าง"
            if i == "register":
                p = self.db.register_part(cmd["part_no"], cmd["name"], cmd["qty"],
                                          cmd["unit"] or "ชิ้น", cmd["location"],
                                          cmd["min_qty"], person=cmd["person"])
                return f"✅ ลงทะเบียน {p['part_no']} {p['name']} แล้ว คงเหลือ {p['qty']} {p['unit']}"
            if i in ("receive", "issue", "adjust"):
                if not cmd.get("part_no") or cmd.get("qty") is None:
                    return "ระบุรหัส part และจำนวนด้วยนะครับ เช่น 'เบิก P001 5'"
                fn = {"receive": self.db.receive, "issue": self.db.issue, "adjust": self.db.adjust}[i]
                p = fn(cmd["part_no"], cmd["qty"], cmd["person"], cmd["note"]) if i != "adjust" \
                    else fn(cmd["part_no"], cmd["qty"], cmd["person"], cmd["note"] or "ปรับยอดตามการนับจริง")
                verb = {"receive": "รับเข้า", "issue": "เบิกจ่าย", "adjust": "ปรับยอด"}[i]
                msg = f"✅ {verb} {p['part_no']} {p['name']} สำเร็จ คงเหลือ {p['qty']} {p['unit']}"
                if i == "issue" and p["qty"] <= p["min_qty"]:
                    msg += f"\n⚠️ ใกล้หมดแล้ว (ขั้นต่ำ {p['min_qty']})"
                return msg
            if i == "check":
                p = self.db.get_part(cmd["part_no"])
                return (f"{p['part_no']} {p['name']}: เหลือ {p['qty']} {p['unit']} "
                        f"ที่เก็บ {p['location'] or '-'} (ขั้นต่ำ {p['min_qty']})")
            if i == "search":
                rows = self.db.search(cmd["keyword"])
                return self._fmt_parts(rows) or "ไม่พบรายการที่ค้นหา"
            if i == "list":
                return self._fmt_parts(self.db.all_parts()) or "ยังไม่มี part ในระบบ"
            if i == "low":
                rows = self.db.low_stock()
                return ("⚠️ รายการใกล้หมด:\n" + self._fmt_parts(rows)) if rows else "ตอนนี้ไม่มี part ที่ใกล้หมดครับ"
            if i == "history":
                rows = self.db.history(cmd.get("part_no"))
                if not rows:
                    return "ยังไม่มีประวัติ"
                return "\n".join(
                    f"{r['ts']} | {r['part_no']} | {r['type']:<8} | {r['qty']:+d} → {r['balance_after']} "
                    f"| {r['person'] or '-'} | {r['note']}" for r in rows)
        except StockError as e:
            return f"❌ {e}"
        return "ขอโทษค่ะ เกิดข้อผิดพลาดที่ไม่คาดคิด"

    @staticmethod
    def _fmt_parts(rows):
        return "\n".join(
            f"• {r['part_no']} | {r['name']} | {r['qty']} {r['unit']} | ที่เก็บ {r['location'] or '-'}"
            for r in rows)


# ===== CLI =====

if __name__ == "__main__":
    bot = Arize()
    print("อะริเสะ: สวัสดีค่ะ! พิมพ์ 'ช่วย' เพื่อดูคำสั่ง, 'exit' เพื่อออก")
    while True:
        try:
            text = input("คุณ: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("exit", "quit", "ออก"):
            break
        if text:
            print("อะริเสะ:", bot.handle(text))
