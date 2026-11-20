"""แอปเว็บ: streamlit run arize_web.py   (หรือดับเบิลคลิก run_web.bat)"""
import base64
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from arize import Arize, HELP, StockDB, StockError

st.set_page_config(page_title="Arize - Stock Parts", page_icon="🔧", layout="wide")

# ====================== ธีม (แก้สีได้ที่ตัวแปรด้านล่าง) ======================
THEME = {
    "bg1": "#070b14",        # พื้นหลังเข้ม
    "bg2": "#0e1626",        # พื้นหลังการ์ด
    "line": "#1f2d4a",       # สีเส้นขอบ
    "text": "#e6edf7",       # สีตัวอักษร
    "muted": "#8b9bb8",      # ตัวอักษรรอง
    "accent": "#00e5ff",     # สีเน้นหลัก (ฟ้านีออน)
    "accent2": "#7c4dff",    # สีเน้นรอง (ม่วง)
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600;700&display=swap');
:root {{
  --bg1:{THEME['bg1']}; --bg2:{THEME['bg2']}; --line:{THEME['line']};
  --text:{THEME['text']}; --muted:{THEME['muted']};
  --a1:{THEME['accent']}; --a2:{THEME['accent2']};
}}
html, body, .stApp, .stMarkdown, p, label, h1, h2, h3, h4, button, input, textarea,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-baseweb="tab"] {{ font-family:'Kanit', sans-serif !important; }}
/* คืนฟอนต์ไอคอนของ Streamlit (ไม่งั้นไอคอนจะกลายเป็นตัวหนังสือ เช่น smart_toy) */
.material-symbols-rounded, .material-symbols-outlined, [data-testid="stIconMaterial"],
span[class*="material"] {{ font-family:'Material Symbols Rounded','Material Symbols Outlined' !important; }}
.stApp {{
  background:
    radial-gradient(900px 500px at 85% -10%, rgba(124,77,255,.18), transparent 60%),
    radial-gradient(800px 500px at -10% 10%, rgba(0,229,255,.12), transparent 60%),
    var(--bg1);
  color:var(--text);
}}
header[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding-top:2rem; max-width:1250px; }}

/* หัวเรื่อง */
h1 {{
  font-weight:700 !important; letter-spacing:.5px;
  background:linear-gradient(90deg,var(--a1),var(--a2));
  -webkit-background-clip:text; background-clip:text; color:transparent !important;
}}
h2, h3, label, p, span, div {{ color:var(--text); }}
small, .stCaption, [data-testid="stCaptionContainer"] {{ color:var(--muted) !important; }}

/* แท็บ */
.stTabs [data-baseweb="tab-list"] {{ gap:6px; border-bottom:1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{
  background:var(--bg2); border:1px solid var(--line); border-bottom:none;
  border-radius:10px 10px 0 0; padding:8px 18px; color:var(--muted);
}}
.stTabs [aria-selected="true"] {{
  color:var(--a1) !important; border-color:var(--a1);
  box-shadow:0 -2px 14px rgba(0,229,255,.25);
}}
.stTabs [data-baseweb="tab-highlight"] {{ background:var(--a1); }}

/* ช่องกรอก */
.stTextInput input, .stNumberInput input, .stTextArea textarea,
div[data-baseweb="select"] > div {{
  background:var(--bg2) !important; color:var(--text) !important;
  border:1px solid var(--line) !important; border-radius:10px !important;
}}
.stTextInput input:focus, .stNumberInput input:focus {{
  border-color:var(--a1) !important; box-shadow:0 0 0 2px rgba(0,229,255,.25) !important;
}}

/* ปุ่ม */
.stButton > button, .stFormSubmitButton > button {{
  background:linear-gradient(90deg,var(--a1),var(--a2)); color:#04101c !important;
  font-weight:600; border:none; border-radius:10px; padding:.5rem 1.6rem;
  transition:transform .15s, box-shadow .15s;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover {{
  transform:translateY(-2px); box-shadow:0 6px 22px rgba(0,229,255,.35);
}}

/* ฟอร์ม + การ์ดตัวเลข */
[data-testid="stForm"] {{
  background:var(--bg2); border:1px solid var(--line); border-radius:16px; padding:1.4rem;
}}
[data-testid="stMetric"] {{
  background:linear-gradient(160deg,var(--bg2),#0a1120);
  border:1px solid var(--line); border-left:3px solid var(--a1);
  border-radius:14px; padding:14px 18px;
  box-shadow:0 4px 24px rgba(0,0,0,.35);
}}
[data-testid="stMetricValue"] {{ color:var(--a1) !important; font-weight:700; }}
[data-testid="stMetricLabel"] p {{ color:var(--muted) !important; }}

/* ตาราง / แชท / แจ้งเตือน */
[data-testid="stDataFrame"] {{ border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
[data-testid="stChatMessage"] {{
  background:var(--bg2); border:1px solid var(--line); border-radius:14px;
}}
[data-testid="stAlert"] {{ border-radius:12px; }}
[data-testid="stSidebar"] {{ background:var(--bg2); border-right:1px solid var(--line); }}
[data-testid="stSidebar"] .stButton > button {{ width:100%; }}
::-webkit-scrollbar {{ width:8px; height:8px; }}
::-webkit-scrollbar-thumb {{ background:var(--line); border-radius:8px; }}
</style>
""", unsafe_allow_html=True)

# กันเบราว์เซอร์แปลหน้าเว็บผิดภาษาอัตโนมัติ
try:
    import streamlit.components.v1 as components
    components.html("""<script>
try {
  const d = window.parent.document;
  d.documentElement.lang = 'th';
  d.documentElement.setAttribute('translate', 'no');
  const m = d.createElement('meta'); m.name = 'google'; m.content = 'notranslate';
  d.head.appendChild(m);
} catch (e) {}
</script>""", height=0)
except Exception:
    pass  # ถ้า Streamlit รุ่นใหม่เอาฟีเจอร์นี้ออก แอปยังทำงานต่อได้ตามปกติ


@st.cache_resource
def get_db():
    return StockDB()


db = get_db()
bot = Arize(db)

# ====================== ตัวการ์ตูนอะริเสะ (วาดด้วย SVG ไม่ต้องมีไฟล์รูป) ======================
# อยากเปลี่ยนเป็นรูปของตัวเอง: ใส่ไฟล์รูปไว้โฟลเดอร์เดียวกัน เช่น "arize.png"
# แล้วแก้บรรทัด AVATAR = "arize.png"
AVATAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
<defs>
<clipPath id="c"><circle cx="100" cy="100" r="100"/></clipPath>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a9e2ff"/><stop offset="1" stop-color="#e9f8ff"/></linearGradient>
<linearGradient id="hair" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b57b0"/><stop offset="1" stop-color="#1b2552"/></linearGradient>
<linearGradient id="iris" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c3f9e"/><stop offset=".55" stop-color="#2f8cf0"/><stop offset="1" stop-color="#7ff0ff"/></linearGradient>
<linearGradient id="hat" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe45c"/><stop offset="1" stop-color="#ffb81f"/></linearGradient>
<linearGradient id="jk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9a4a"/><stop offset="1" stop-color="#f26b1d"/></linearGradient>
</defs>
<g clip-path="url(#c)">
<rect width="200" height="200" fill="url(#bg)"/>
<g fill="#fff" opacity=".95">
<path d="M26 44 l2.2 6.5 6.5 2.2 -6.5 2.2 -2.2 6.5 -2.2 -6.5 -6.5 -2.2 6.5 -2.2z"/>
<path d="M172 60 l1.8 5 5 1.8 -5 1.8 -1.8 5 -1.8 -5 -5 -1.8 5 -1.8z"/>
<circle cx="170" cy="30" r="2.5"/><circle cx="22" cy="100" r="2"/><circle cx="182" cy="108" r="1.8"/>
</g>
<!-- back hair -->
<path d="M48 92 C32 124 34 164 46 182 L154 182 C166 164 168 124 152 92 Z" fill="url(#hair)"/>
<path d="M148 90 C180 96 188 140 166 172 C168 142 160 120 146 108 Z" fill="url(#hair)"/>
<circle cx="149" cy="96" r="5.5" fill="#ff7a2f"/>
<!-- neck -->
<rect x="89" y="138" width="22" height="24" rx="8" fill="#ffd6bd"/>
<!-- jacket -->
<path d="M18 200 C20 172 52 158 84 154 L116 154 C148 158 180 172 182 200 Z" fill="url(#jk)"/>
<path d="M86 154 L100 180 L114 154 Z" fill="#ffffff"/>
<path d="M80 153 L100 183 L91 187 L70 158 Z" fill="#e85d10"/>
<path d="M120 153 L100 183 L109 187 L130 158 Z" fill="#e85d10"/>
<path d="M34 190 L66 184 L68 190 L35 196 Z" fill="#fff1b8"/>
<path d="M166 190 L134 184 L132 190 L165 196 Z" fill="#fff1b8"/>
<rect x="124" y="168" width="26" height="13" rx="2.5" fill="#fff" stroke="#1b2552" stroke-width="1.5"/>
<rect x="128" y="172" width="12" height="2" fill="#7b8ab8"/><rect x="128" y="176" width="18" height="2" fill="#b7c2e0"/>
<!-- face -->
<path d="M56 96 C56 128 76 150 100 150 C124 150 144 128 144 96 C144 70 124 58 100 58 C76 58 56 70 56 96 Z" fill="#ffe8d8"/>
<path d="M60 118 C66 136 82 148 100 149 C84 142 70 132 64 112 Z" fill="#f6cdb6" opacity=".55"/>
<!-- blush -->
<ellipse cx="66" cy="125" rx="8" ry="4.5" fill="#ff9fb0" opacity=".65"/>
<ellipse cx="134" cy="125" rx="8" ry="4.5" fill="#ff9fb0" opacity=".65"/>
<path d="M61 124 l3 -4 M66 125 l3 -4 M71 126 l3 -4" stroke="#ff7f95" stroke-width="1.2" stroke-linecap="round" opacity=".7"/>
<path d="M139 124 l-3 -4 M134 125 l-3 -4 M129 126 l-3 -4" stroke="#ff7f95" stroke-width="1.2" stroke-linecap="round" opacity=".7"/>
<!-- eyes -->
<g>
<ellipse cx="80" cy="109" rx="11.5" ry="13.5" fill="#fff"/>
<ellipse cx="80" cy="110" rx="9.6" ry="12.4" fill="url(#iris)"/>
<ellipse cx="80" cy="110" rx="4.6" ry="7" fill="#0a1a47"/>
<circle cx="76" cy="103" r="4" fill="#fff"/><circle cx="85" cy="116" r="2" fill="#fff"/><circle cx="83" cy="104" r="1.1" fill="#fff"/>
<path d="M66 104 C67 92 78 91 85 92 C91 93 94 99 94 104 C90 98 80 96 66 104 Z" fill="#161d42"/>
<path d="M66 104 L61 101" stroke="#161d42" stroke-width="2.6" stroke-linecap="round"/>
</g>
<g>
<ellipse cx="120" cy="109" rx="11.5" ry="13.5" fill="#fff"/>
<ellipse cx="120" cy="110" rx="9.6" ry="12.4" fill="url(#iris)"/>
<ellipse cx="120" cy="110" rx="4.6" ry="7" fill="#0a1a47"/>
<circle cx="116" cy="103" r="4" fill="#fff"/><circle cx="125" cy="116" r="2" fill="#fff"/><circle cx="123" cy="104" r="1.1" fill="#fff"/>
<path d="M134 104 C133 92 122 91 115 92 C109 93 106 99 106 104 C110 98 120 96 134 104 Z" fill="#161d42"/>
<path d="M134 104 L139 101" stroke="#161d42" stroke-width="2.6" stroke-linecap="round"/>
</g>
<!-- brows, nose, mouth -->
<path d="M69 88 Q79 83 91 87" stroke="#232e63" stroke-width="2" fill="none" stroke-linecap="round"/>
<path d="M109 87 Q121 83 131 88" stroke="#232e63" stroke-width="2" fill="none" stroke-linecap="round"/>
<path d="M100 122 q-1.5 2 0 3" stroke="#e3a592" stroke-width="1.6" fill="none" stroke-linecap="round"/>
<path d="M92 130 Q100 139 108 130 Q100 134 92 130 Z" fill="#e0525f" stroke="#c43f4e" stroke-width="1.2" stroke-linejoin="round"/>
<!-- side locks -->
<path d="M55 98 C46 122 48 154 60 174 C66 156 64 128 66 106 Z" fill="url(#hair)"/>
<path d="M145 98 C154 122 152 154 140 174 C134 156 136 128 134 106 Z" fill="url(#hair)"/>
<!-- bangs -->
<path d="M52 102 C50 82 62 76 76 76 L124 76 C138 76 150 82 148 102 C142 92 136 91 130 96 C125 102 119 98 115 90 C111 99 105 101 100 93 C95 101 89 99 85 90 C81 98 75 102 70 96 C64 91 58 92 52 102 Z" fill="url(#hair)"/>
<path d="M72 84 Q82 80 92 86 M108 86 Q118 80 128 84" stroke="#7d97e8" stroke-width="2" fill="none" stroke-linecap="round" opacity=".8"/>
<!-- hard hat -->
<path d="M50 84 C50 32 150 32 150 84 Z" fill="url(#hat)"/>
<rect x="94" y="36" width="12" height="46" rx="6" fill="#ffb013"/>
<path d="M64 62 C70 46 88 40 98 40" stroke="#fff8c9" stroke-width="4" fill="none" stroke-linecap="round" opacity=".85"/>
<rect x="42" y="78" width="116" height="12" rx="6" fill="#f5a30f"/>
<circle cx="100" cy="65" r="8" fill="#fff" stroke="#f08d00" stroke-width="1.5"/>
<circle cx="100" cy="65" r="5.2" fill="none" stroke="#f08d00" stroke-width="2.4" stroke-dasharray="2.6 1.8"/>
<circle cx="100" cy="65" r="2.2" fill="#f08d00"/>
</g></svg>"""
AVATAR_FALLBACK = "data:image/svg+xml;base64," + base64.b64encode(AVATAR_SVG.encode("utf-8")).decode()
USER_AVATAR = "🧑‍🔧"


@st.cache_resource
def load_avatar():
    """ใช้รูป arize.png ในโฟลเดอร์เดียวกับไฟล์นี้ (ย่อ + ตัดเป็นวงกลมให้อัตโนมัติ)
    ถ้าไม่มีไฟล์ หรืออ่านไม่ได้ จะใช้ตัวการ์ตูนที่วาดไว้ด้านบนแทน"""
    try:
        import io
        from pathlib import Path
        from PIL import Image, ImageDraw, ImageOps

        size, scale = 256, 4
        im = Image.open(Path(__file__).resolve().parent / "arize.png").convert("RGBA")
        im = ImageOps.fit(im, (size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size * scale, size * scale), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
        im.putalpha(mask.resize((size, size), Image.Resampling.LANCZOS))
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return AVATAR_FALLBACK


AVATAR = load_avatar()

# ====================== ตัวช่วย ======================
try:
    import openpyxl  # noqa: F401  (ใช้ตอนสร้างไฟล์ Excel)
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

ROLE_TH = {"admin": "แอดมิน", "staff": "พนักงาน"}
PART_COLS = {"part_no": "รหัส", "name": "ชื่อ", "category": "หมวด", "unit": "หน่วย",
             "location": "ที่เก็บ", "qty": "คงเหลือ", "min_qty": "ขั้นต่ำ", "created_at": "ลงทะเบียนเมื่อ"}
HIST_COLS = {"id": "#", "ts": "เวลา", "part_no": "รหัส", "type": "ประเภท", "qty": "จำนวน",
             "balance_after": "คงเหลือหลังทำรายการ", "person": "ผู้ทำรายการ", "note": "หมายเหตุ"}


def notify(msg: str):
    """เก็บข้อความ 'สำเร็จ' ไว้แสดงหลังรีเฟรชหน้า (ให้ตัวเลข/ตารางทุกจุดอัปเดตทันที)
    แล้วเรียก st.rerun() ต่อ"""
    st.session_state["_flash"] = msg
    st.session_state.pop("xlsx", None)  # ข้อมูลเปลี่ยนแล้ว ไฟล์ Excel ที่เตรียมไว้เก่าแล้ว


def parts_df(rows):
    return pd.DataFrame(rows).rename(columns=PART_COLS)


def hist_df(rows):
    return pd.DataFrame(rows).rename(columns=HIST_COLS)


def style_low(df):
    """ไฮไลต์แถวสีแดงเมื่อคงเหลือ <= ขั้นต่ำ"""
    def row_style(row):
        low = row["คงเหลือ"] <= row["ขั้นต่ำ"]
        return ["background-color: rgba(255,82,82,.20); color: #ff9a9a" if low else "" for _ in row]
    try:
        return df.style.apply(row_style, axis=1)
    except Exception:
        return df  # ไม่มี jinja2 ฯลฯ — แสดงตารางธรรมดาแทน


def csv_bytes(df) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig ให้ Excel เปิดภาษาไทยไม่เพี้ยน


def xlsx_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for title, d in sheets.items():
            d.to_excel(xw, sheet_name=title, index=False)
            ws = xw.sheets[title]
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col if c.value is not None), default=0)
                ws.column_dimensions[col[0].column_letter].width = min(width + 3, 50)
    return buf.getvalue()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def render_header():
    h1, h2 = st.columns([1, 9], vertical_alignment="center")
    h1.image(AVATAR, width=96)
    h2.title("Arize (อะริเสะ) — ระบบจัดการสต๊อกอะไหล่")


# ====================== เข้าสู่ระบบ ======================
def auth_gate() -> dict:
    """คืนข้อมูลผู้ใช้ที่ล็อกอินอยู่ ถ้ายังไม่ได้ล็อกอินจะโชว์หน้า login แล้วหยุดสคริปต์"""
    sess = st.session_state.get("user")
    if sess:
        fresh = db.get_user(sess["username"])   # เช็คซ้ำทุกครั้ง: ถูกปิดบัญชี/เปลี่ยนสิทธิ์ ให้มีผลทันที
        if fresh and fresh["active"]:
            st.session_state["user"] = fresh
            return fresh
        st.session_state.pop("user", None)

    render_header()
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        if db.user_count() == 0:
            st.subheader("ตั้งค่าครั้งแรก: สร้างบัญชีแอดมิน")
            st.caption("ยังไม่มีผู้ใช้ในระบบ — บัญชีแรกจะเป็นแอดมิน (เพิ่มพนักงานได้ภายหลังในแท็บ 'ผู้ใช้')")
            with st.form("setup"):
                un = st.text_input("ชื่อผู้ใช้ (อังกฤษ/ตัวเลข เช่น admin)")
                dn = st.text_input("ชื่อที่แสดง (เช่น ชื่อจริง)")
                pw = st.text_input("รหัสผ่าน", type="password")
                pw2 = st.text_input("ยืนยันรหัสผ่าน", type="password")
                if st.form_submit_button("สร้างบัญชีแอดมิน"):
                    if pw != pw2:
                        st.error("รหัสผ่านสองช่องไม่ตรงกัน")
                    else:
                        try:
                            st.session_state["user"] = db.create_first_admin(un, dn, pw)
                            st.rerun()
                        except StockError as e:
                            st.error(str(e))
        else:
            st.subheader("เข้าสู่ระบบ")
            with st.form("login"):
                un = st.text_input("ชื่อผู้ใช้")
                pw = st.text_input("รหัสผ่าน", type="password")
                if st.form_submit_button("เข้าสู่ระบบ"):
                    try:
                        st.session_state["user"] = db.authenticate(un, pw)
                        st.rerun()
                    except StockError as e:
                        st.error(str(e))
    st.stop()


user = auth_gate()
is_admin = user["role"] == "admin"

with st.sidebar:
    st.markdown(f"### {user['display_name']}")
    st.caption(f"@{user['username']} · {ROLE_TH[user['role']]}")
    with st.expander("เปลี่ยนรหัสผ่าน"):
        with st.form("chpw", clear_on_submit=True):
            old_pw = st.text_input("รหัสผ่านเดิม", type="password")
            new_pw = st.text_input("รหัสผ่านใหม่", type="password")
            new_pw2 = st.text_input("ยืนยันรหัสผ่านใหม่", type="password")
            if st.form_submit_button("เปลี่ยนรหัสผ่าน"):
                if new_pw != new_pw2:
                    st.error("รหัสผ่านใหม่สองช่องไม่ตรงกัน")
                else:
                    try:
                        db.change_own_password(user["username"], old_pw, new_pw)
                        st.success("เปลี่ยนรหัสผ่านแล้ว")
                    except StockError as e:
                        st.error(str(e))
    if st.button("ออกจากระบบ"):
        for k in ("user", "chat", "xlsx"):
            st.session_state.pop(k, None)
        st.rerun()

if (_msg := st.session_state.pop("_flash", None)):
    st.toast(_msg, icon="✅")

# ====================== หน้าหลัก ======================
render_header()

# แถบสรุปตัวเลข (ทุกการบันทึกสั่ง rerun ต่อ จึงอัปเดตทันที)
_all = db.all_parts()
c1, c2, c3 = st.columns(3)
c1.metric("จำนวนรายการ part", f"{len(_all):,}")
c2.metric("จำนวนชิ้นรวมในคลัง", f"{sum(p['qty'] for p in _all):,}")
c3.metric("ใกล้หมด ⚠️", f"{len(db.low_stock()):,}")
st.write("")

labels = ["💬 คุยกับอะริเสะ", "📦 สต๊อก", "➕ ลงทะเบียน part", "↔️ รับเข้า / เบิกจ่าย", "🕒 ประวัติ", "📊 สถิติ"]
if is_admin:
    labels += ["🛠️ แก้ไข / ลบ part", "👥 ผู้ใช้"]
_tabs = st.tabs(labels)
tab_chat, tab_stock, tab_reg, tab_move, tab_hist, tab_stats = _tabs[:6]

# ---------- แชท ----------
with tab_chat:
    if "chat" not in st.session_state:
        st.session_state.chat = [("assistant", HELP)]
    def _fmt(m: str) -> str:
        """ทำให้ข้อความแชทอ่านง่าย: แต่ละบรรทัดขึ้นบรรทัดใหม่จริง และ • กลายเป็นรายการ"""
        lines = []
        for ln in str(m).split("\n"):
            s = ln.strip()
            if s.startswith("•"):
                s = "- " + s.lstrip("• ").strip()
                lines.append(s)
            else:
                lines.append(s + "  ")  # ท้ายบรรทัดเว้นวรรค 2 ช่อง = ขึ้นบรรทัดใหม่ใน markdown
        return "\n".join(lines)

    for role, msg in st.session_state.chat:
        with st.chat_message(role, avatar=AVATAR if role == "assistant" else USER_AVATAR):
            st.markdown(_fmt(msg) if role == "assistant" else msg)
    if prompt := st.chat_input("สั่งงานอะริเสะ เช่น เบิก P001 5"):
        st.session_state.chat.append(("user", prompt))
        st.session_state.chat.append(("assistant", bot.handle(prompt, user)))
        st.rerun()

# ---------- สต๊อก ----------
with tab_stock:
    kw = st.text_input("ค้นหา (รหัส / ชื่อ / ที่เก็บ)")
    rows = db.search(kw) if kw else db.all_parts()
    if rows:
        df = parts_df(rows)
        st.dataframe(style_low(df), hide_index=True)
        st.caption("แถวสีแดง = ของใกล้หมด (คงเหลือ ≤ ขั้นต่ำ)")
        b1, b2, b3 = st.columns([1.2, 1.2, 2.6])
        b1.download_button("⬇️ CSV (ตามที่แสดง)", csv_bytes(df), f"arize_stock_{stamp()}.csv", "text/csv")
        if HAS_XLSX:
            if b2.button("📥 เตรียมไฟล์ Excel"):
                st.session_state["xlsx"] = (
                    f"arize_{stamp()}.xlsx",
                    xlsx_bytes({"สต๊อก": parts_df(db.all_parts()),
                                "ประวัติ": hist_df(db.history(limit=1_000_000))}))
            if "xlsx" in st.session_state:
                _name, _data = st.session_state["xlsx"]
                b3.download_button("⬇️ ดาวน์โหลด Excel (สต๊อก + ประวัติทั้งหมด)", _data, _name,
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            b2.caption("ติดตั้ง openpyxl เพื่อ export Excel")
    else:
        st.info("ยังไม่มีข้อมูล")
    low = db.low_stock()
    if low:
        st.warning("⚠️ ใกล้หมด: " + ", ".join(f"{r['part_no']} ({r['qty']})" for r in low))

# ---------- ลงทะเบียน ----------
with tab_reg:
    with st.form("reg", clear_on_submit=True):
        c1, c2 = st.columns(2)
        part_no = c1.text_input("รหัส part *")
        name = c2.text_input("ชื่อ part *")
        category = c1.text_input("หมวดหมู่")
        unit = c2.text_input("หน่วย", value="ชิ้น")
        location = c1.text_input("ที่เก็บ")
        qty = c2.number_input("จำนวนเริ่มต้น", min_value=0, step=1)
        min_qty = c1.number_input("จำนวนขั้นต่ำ (แจ้งเตือน)", min_value=0, step=1)
        c2.text_input("ผู้บันทึก", value=user["display_name"], disabled=True)
        if st.form_submit_button("ลงทะเบียน"):
            try:
                db.register_part(part_no, name, int(qty), unit, location, int(min_qty), category,
                                 user["display_name"])
                notify(f"ลงทะเบียน {part_no.strip().upper()} แล้ว")
                st.rerun()
            except StockError as e:
                st.error(str(e))

# ---------- รับเข้า / เบิกจ่าย ----------
with tab_move:
    parts = {f"{p['part_no']} — {p['name']} (เหลือ {p['qty']})": p["part_no"] for p in db.all_parts()}
    if parts:
        actions = ["เบิกจ่าย", "รับเข้า"] + (["ปรับยอด (ตามนับจริง)"] if is_admin else [])
        with st.form("move", clear_on_submit=True):
            choice = st.selectbox("เลือก part", list(parts))
            action = st.radio("การทำรายการ", actions, horizontal=True)
            amount = st.number_input("จำนวน (ถ้าปรับยอด = ยอดที่นับได้จริง)", min_value=0, step=1)
            st.text_input("ผู้ทำรายการ", value=user["display_name"], disabled=True)
            note = st.text_input("หมายเหตุ")
            if st.form_submit_button("บันทึก"):
                try:
                    if action == "เบิกจ่าย":
                        p = db.issue(parts[choice], int(amount), user["display_name"], note)
                    elif action == "รับเข้า":
                        p = db.receive(parts[choice], int(amount), user["display_name"], note)
                    else:
                        p = db.adjust(parts[choice], int(amount), user["display_name"],
                                      note or "ปรับยอดตามการนับจริง")
                    notify(f"สำเร็จ — {p['part_no']} คงเหลือ {p['qty']} {p['unit']}")
                    st.rerun()
                except StockError as e:
                    st.error(str(e))
    else:
        st.info("ลงทะเบียน part ก่อนนะคะ")

# ---------- ประวัติ ----------
with tab_hist:
    pn = st.text_input("กรองตามรหัส part (เว้นว่าง = ทั้งหมด)")
    h = db.history(pn or None, limit=200)
    if h:
        hdf = hist_df(h)
        st.dataframe(hdf, hide_index=True)
        st.caption("แสดงล่าสุด 200 รายการ — ประวัติทั้งหมดดาวน์โหลดเป็น Excel ได้ที่แท็บ 'สต๊อก'")
        st.download_button("⬇️ CSV (ตามที่แสดง)", csv_bytes(hdf), f"arize_history_{stamp()}.csv", "text/csv")
    else:
        st.info("ยังไม่มีประวัติ")

# ---------- สถิติ ----------
with tab_stats:
    days = st.radio("ช่วงเวลา", [7, 30, 90], index=1, horizontal=True, format_func=lambda d: f"ย้อนหลัง {d} วัน")
    ddf = pd.DataFrame(db.usage_by_day(days), columns=["day", "in_qty", "out_qty"])
    ddf["day"] = pd.to_datetime(ddf["day"])
    ddf = (ddf.set_index("day")
              .reindex(pd.date_range(end=pd.Timestamp.now().normalize(), periods=days), fill_value=0)
              .rename(columns={"in_qty": "รับเข้า", "out_qty": "เบิกจ่าย"}))
    if ddf.to_numpy().sum() == 0:
        st.info("ยังไม่มีการรับเข้า/เบิกจ่ายในช่วงนี้")
    else:
        k1, k2 = st.columns(2)
        k1.metric("รับเข้ารวม", f"{int(ddf['รับเข้า'].sum()):,}")
        k2.metric("เบิกจ่ายรวม", f"{int(ddf['เบิกจ่าย'].sum()):,}")
        st.markdown("**รับเข้า / เบิกจ่าย รายวัน**")
        st.bar_chart(ddf, color=["#00e5ff", "#7c4dff"])
        top = db.top_issued(days)
        if top:
            st.markdown("**part ที่ถูกเบิกมากที่สุด**")
            tdf = pd.DataFrame(top).rename(columns={"part_no": "รหัส", "name": "ชื่อ", "out_qty": "เบิกจ่าย"})
            st.dataframe(tdf, hide_index=True, column_config={
                "เบิกจ่าย": st.column_config.ProgressColumn(
                    "เบิกจ่าย", min_value=0, max_value=int(tdf["เบิกจ่าย"].max()), format="%d")})

# ====================== เฉพาะแอดมิน ======================
if is_admin:
    tab_edit, tab_users = _tabs[6:8]

    with tab_edit:
        plist = db.all_parts()
        if not plist:
            st.info("ยังไม่มี part ให้แก้ไข")
        else:
            opts = {f"{p['part_no']} — {p['name']}": p for p in plist}
            sel = st.selectbox("เลือก part", list(opts), key="edit_sel")
            p = opts[sel]
            pn = p["part_no"]
            st.caption(f"คงเหลือ {p['qty']} {p['unit']} — แก้จำนวนให้ใช้ 'ปรับยอด' ในแท็บรับเข้า / เบิกจ่าย")
            with st.form(f"edit_{pn}"):
                e1, e2 = st.columns(2)
                e_name = e1.text_input("ชื่อ part *", value=p["name"], key=f"e_name_{pn}")
                e_cat = e2.text_input("หมวดหมู่", value=p["category"], key=f"e_cat_{pn}")
                e_unit = e1.text_input("หน่วย", value=p["unit"], key=f"e_unit_{pn}")
                e_loc = e2.text_input("ที่เก็บ", value=p["location"], key=f"e_loc_{pn}")
                e_min = e1.number_input("จำนวนขั้นต่ำ", min_value=0, step=1, value=int(p["min_qty"]),
                                        key=f"e_min_{pn}")
                if st.form_submit_button("บันทึกการแก้ไข"):
                    try:
                        db.update_part(pn, e_name, e_cat, e_unit, e_loc, int(e_min), user["display_name"])
                        notify(f"แก้ไข {pn} แล้ว")
                        st.rerun()
                    except StockError as e:
                        st.error(str(e))

            st.divider()
            st.markdown("##### 🗑️ ลบ part")
            st.warning("ลบแล้วกู้คืนไม่ได้ และประวัติทั้งหมดของ part นี้จะถูกลบไปด้วย "
                       "(ดาวน์โหลด Excel เก็บไว้ก่อนได้ที่แท็บ 'สต๊อก')")
            confirm = st.text_input(f"พิมพ์รหัส {pn} เพื่อยืนยันการลบ", key=f"del_confirm_{pn}")
            if st.button("ลบ part นี้", key=f"del_btn_{pn}"):
                if confirm.strip().upper() == pn:
                    try:
                        db.delete_part(pn)
                        notify(f"ลบ {pn} แล้ว")
                        st.rerun()
                    except StockError as e:
                        st.error(str(e))
                else:
                    st.error("รหัสที่พิมพ์ไม่ตรง ยังไม่ได้ลบ")

    with tab_users:
        ulist = db.list_users()
        udf = pd.DataFrame(ulist)[["username", "display_name", "role", "active", "created_at"]]
        udf["role"] = udf["role"].map(ROLE_TH)
        udf["active"] = udf["active"].map({1: "ใช้งาน", 0: "ปิดใช้งาน"})
        udf.columns = ["ชื่อผู้ใช้", "ชื่อที่แสดง", "สิทธิ์", "สถานะ", "สร้างเมื่อ"]
        st.dataframe(udf, hide_index=True)
        st.caption("แอดมิน = ทำได้ทุกอย่าง (รวมปรับยอด/แก้ไข/ลบ part/จัดการผู้ใช้)  •  "
                   "พนักงาน = ดู ลงทะเบียน รับเข้า เบิกจ่าย และ export")

        st.markdown("##### ➕ เพิ่มผู้ใช้")
        with st.form("newuser", clear_on_submit=True):
            u1, u2 = st.columns(2)
            n_user = u1.text_input("ชื่อผู้ใช้ (อังกฤษ/ตัวเลข)")
            n_disp = u2.text_input("ชื่อที่แสดง")
            n_pw = u1.text_input("รหัสผ่านเริ่มต้น", type="password")
            n_role = u2.selectbox("สิทธิ์", ["staff", "admin"], format_func=ROLE_TH.get)
            if st.form_submit_button("เพิ่มผู้ใช้"):
                try:
                    db.create_user(n_user, n_disp, n_pw, n_role)
                    notify(f"เพิ่มผู้ใช้ {n_user.strip().lower()} แล้ว")
                    st.rerun()
                except StockError as e:
                    st.error(str(e))

        st.markdown("##### ⚙️ จัดการผู้ใช้เดิม")
        target = st.selectbox("เลือกผู้ใช้", [u["username"] for u in ulist], key="um_target")
        tu = db.get_user(target)
        m1, m2 = st.columns(2)
        with m1:
            new_pw = st.text_input("ตั้งรหัสผ่านใหม่ให้ผู้ใช้นี้", type="password", key=f"um_pw_{target}")
            if st.button("รีเซ็ตรหัสผ่าน", key=f"um_reset_{target}"):
                try:
                    db.set_password(target, new_pw)
                    notify(f"ตั้งรหัสผ่านใหม่ให้ {target} แล้ว")
                    st.rerun()
                except StockError as e:
                    st.error(str(e))
        with m2:
            if target == user["username"]:
                st.caption("เปลี่ยนสิทธิ์ / ปิดบัญชีของตัวเองไม่ได้ (ให้แอดมินคนอื่นทำ)")
            else:
                flip = "staff" if tu["role"] == "admin" else "admin"
                if st.button(f"เปลี่ยนสิทธิ์เป็น{ROLE_TH[flip]}", key=f"um_role_{target}"):
                    try:
                        db.set_user_role(target, flip)
                        notify(f"{target} เป็น{ROLE_TH[flip]}แล้ว")
                        st.rerun()
                    except StockError as e:
                        st.error(str(e))
                if st.button("ปิดบัญชีนี้" if tu["active"] else "เปิดบัญชีนี้", key=f"um_act_{target}"):
                    try:
                        db.set_user_active(target, not tu["active"])
                        notify(f"{'ปิด' if tu['active'] else 'เปิด'}บัญชี {target} แล้ว")
                        st.rerun()
                    except StockError as e:
                        st.error(str(e))
