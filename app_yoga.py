import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import re
import time
import uuid
import extra_streamlit_components as stx
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Ẩn Header/Footer mặc định */
    header, footer, [data-testid="stToolbar"], .stDeployButton { display: none !important; }

    /* Đẩy nội dung lên sát mép trên */
    .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 120px !important;
        max-width: 100%;
    }

    /* Khung chat */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Banner Quảng Cáo */
    .promo-banner {
        background: linear-gradient(90deg, #e0f2f1 0%, #b2dfdb 100%);
        padding: 10px 15px; margin-bottom: 20px; border-radius: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #80cbc4;
    }
    .promo-text { color: #00695c; font-weight: bold; font-size: 14px; }
    .promo-btn {
        background-color: #00796b; color: white !important; padding: 6px 12px;
        border-radius: 15px; text-decoration: none; font-weight: bold; font-size: 12px;
        white-space: nowrap;
    }

    /* Style Link Ref bấm được */
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 6px; border-radius: 4px; margin: 0 2px;
        font-size: 0.9em; border: 1px solid #b2dfdb;
    }
    .ref-link:hover { background: #00796b; color: white; border-color: #004d40; }

    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOAD DATA & MODEL (AN TOÀN)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine_safe():
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu từ Drive"
    
    # 2. Tìm đường dẫn vector DB
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path):
                    return check_path
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    
    if not text_db_path: return None, "Lỗi: Không tìm thấy não chữ (vector_db)"

    # 3. Load Vector DB
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

data_result, status = load_brain_engine_safe()
if status != "OK": st.error(f"Lỗi: {status}"); st.stop()
db_text, db_image = data_result

# =====================================================
# 3. HÀM XỬ LÝ AI THÔNG MINH (CÓ CHẶN SPAM)
# =====================================================
def get_ai_response(prompt, context_text, history_context):
    try:
        # Cấu hình Model cứng để chạy nhanh
        generation_config = {"temperature": 0.5, "max_output_tokens": 1000}
        model = genai.GenerativeModel('models/gemini-1.5-flash', generation_config=generation_config)

        sys_prompt = f"""
        BẠN LÀ CHUYÊN GIA YOGA & TRỊ LIỆU.
        
        QUY TẮC QUAN TRỌNG NHẤT:
        - Nhiệm vụ: Trả lời về Yoga, Sức khỏe, Giải phẫu học, Thiền, Dinh dưỡng.
        - Nếu câu hỏi KHÔNG LIÊN QUAN (xổ số, chính trị, code, tình yêu, tán gẫu vô nghĩa...), hãy trả lời duy nhất: REFUSE_TOPIC
        
        DỮ LIỆU TRA CỨU:
        {context_text}
        
        LỊCH SỬ CHAT:
        {history_context}
        
        CÂU HỎI: "{prompt}"
        
        YÊU CẦU:
        - Trả lời ngắn gọn, có tâm, dưới 200 từ.
        - Nếu dùng thông tin từ nguồn RAG: Ghi chú [Ref: ID].
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERR_SYS: {str(e)}"

# =====================================================
# 4. HỆ THỐNG QUẢN LÝ (DB, AUTH, LOGS)
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    conn.execute('CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user_id TEXT, question TEXT, answer TEXT)')
    conn.commit(); conn.close()

def log_chat_to_db(user, q, a):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO chat_logs (timestamp, user_id, question, answer) VALUES (?, ?, ?, ?)", (now, user, q, a))
        conn.commit(); conn.close()
    except: pass

def check_usage(user):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user, today))
    r = c.fetchone(); conn.close()
    return r[0] if r else 0

def increment_usage(user):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user, today))
    conn.commit(); conn.close()

init_db()

# --- Xử lý Cookie & Auth ---
cookie_manager = stx.CookieManager(key="yoga_pro_manager")
time.sleep(0.1) 
vip_cookie = cookie_manager.get(cookie="yoga_vip_user")
guest_cookie = cookie_manager.get(cookie="yoga_guest_id")

if vip_cookie:
    st.session_state.authenticated = True
    st.session_state.username = vip_cookie
    current_user_id = vip_cookie
elif guest_cookie:
    st.session_state.authenticated = False
    current_user_id = guest_cookie
else:
    new_id = str(uuid.uuid4())[:8]
    cookie_manager.set("yoga_guest_id", new_id, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
    current_user_id = new_id
    st.rerun()

# --- Tính toán giới hạn ---
used = check_usage(current_user_id)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# --- Khởi tạo Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Namaste {current_user_id}! 🙏 Tôi có thể giúp gì cho sức khỏe của bạn?"}]
if "bad_attempts" not in st.session_state: 
    st.session_state.bad_attempts = 0 # Đếm số lần hỏi linh tinh
if "is_blocked" not in st.session_state: 
    st.session_state.is_blocked = False # Trạng thái khóa

# =====================================================
# 5. GIAO DIỆN PHỤ (SIDEBAR, COUNTER, LIMIT)
# =====================================================
with st.sidebar:
    st.title("🔐 Khu Vực VIP")
    if st.session_state.authenticated:
        st.success(f"User: {st.session_state.username}")
        if st.button("Đăng xuất"):
            cookie_manager.delete("yoga_vip_user")
            st.session_state.authenticated = False
            st.rerun()
    else:
        with st.form("login_form"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Đăng Nhập"):
                if st.secrets["passwords"].get(u) == p:
                    cookie_manager.set("yoga_vip_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=7))
                    st.rerun()
                else: st.error("Sai thông tin")

# Thanh đếm lượt
percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""
<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;">
    <div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; 
                border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;">
        <span>⚡ {used}/{LIMIT}</span>
        <div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Màn hình hết hạn (Nếu quá giới hạn dùng)
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    if not st.session_state.hide_limit_modal:
        st.info("🚫 Đã hết lượt dùng thử hôm nay. Vui lòng liên hệ Admin hoặc đăng nhập.")
        with st.form("login_limit"):
            user = st.text_input("User"); pwd = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(user) == pwd:
                    cookie_manager.set("yoga_vip_user", user); st.rerun()
        st.stop()

# =====================================================
# 6. HIỂN THỊ CHAT & XỬ LÝ
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Freeship + tài khoản VIP giảm 30%!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'], caption=img['title'])

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# --- XỬ LÝ LOGIC CHAT (QUAN TRỌNG) ---

# 1. Kiểm tra block
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN TẠM KHÓA: Bạn đã hỏi sai chủ đề quá 3 lần. Vui lòng tải lại trang (F5) để reset.")
    st.stop()

if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    # User input
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user_id)

    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            
            # A. Lấy Context & Lịch sử
            chat_history = ""
            for msg in st.session_state.messages[-5:-1]:
                role_txt = "User" if msg["role"] == "user" else "Bot"
                content_clean = re.sub(r'<[^>]*>', '', msg["content"])
                chat_history += f"{role_txt}: {content_clean}\n"

            # B. Tìm kiếm RAG
            context_text = ""
            source_map = {}
            found_images = []
            try:
                docs = db_text.similarity_search(prompt, k=4)
                if db_image: docs += db_image.similarity_search(prompt, k=2)
                
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    meta = d.metadata
                    source_map[doc_id] = {"url": meta.get('url', '#'), "title": meta.get('title', 'Nguồn')}
                    if meta.get('type') == 'image' and meta.get('image_url'):
                        found_images.append({"url": meta['image_url'], "title": meta.get('title', '')})
                    context_text += f"\n[Nguồn {doc_id}]: {d.page_content}\n"
            except Exception as e: st.warning(f"Lỗi tìm kiếm: {e}")

            # C. Gọi AI & Check Spam
            ai_raw = get_ai_response(prompt, context_text, chat_history)

            # D. Xử lý kết quả
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    st.session_state.is_blocked = True
                    msg = "🚫 **CẢNH BÁO:** Bạn đã hỏi sai chủ đề 3 lần. Hệ thống tạm khóa. F5 để thử lại."
                else:
                    msg = f"⚠️ **Nhắc nhở:** Tôi chỉ hỗ trợ Yoga & Sức khỏe. (Vi phạm: {st.session_state.bad_attempts}/3)"
                
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                if st.session_state.is_blocked: st.stop()

            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"❌ Lỗi hệ thống: {ai_raw}")
            
            else:
                # Thành công -> Format Link Ref
                def replace_ref(match):
                    ref_id = int(match.group(1))
                    if ref_id in source_map:
                        info = source_map[ref_id]
                        if info['url'] and info['url'] != '#':
                            return f" <a href='{info['url']}' target='_blank' class='ref-link' title='{info['title']}'>[{ref_id}]</a>"
                    return ""
                
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_raw)
                st.markdown(final_html, unsafe_allow_html=True)
                
                # Hiện ảnh nếu có
                if found_images:
                    st.markdown("---")
                    cols = st.columns(3)
                    for i, img in enumerate(found_images):
                        with cols[i % 3]: st.image(img['url'], caption=img['title'])
                
                # Lưu log
                st.session_state.messages.append({"role": "assistant", "content": final_html, "images": found_images})
                log_chat_to_db(current_user_id, prompt, ai_raw)

                # Upsell
                YOGA_SOLUTIONS = {
                    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu"]},
                    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","kỹ thuật","chỉnh sửa"]},
                }
                for k, v in YOGA_SOLUTIONS.items():
                    if any(key in prompt.lower() for key in v['key']):
                        st.markdown(f"""<div style="margin-top:10px; padding:8px; background:#e0f2f1; border-radius:8px; border:1px solid #009688;">
                        <span style="font-weight:bold;">{v['name']}</span> <a href="{v['url']}" target="_blank" style="float:right; background:#00796b; color:white; padding:2px 10px; border-radius:10px; text-decoration:none; font-size:12px;">Xem ngay</a>
                        </div>""", unsafe_allow_html=True)
                        break
