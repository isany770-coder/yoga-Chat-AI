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
# ĐÃ BỎ THƯ VIỆN COOKIE GÂY LỖI
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG (BẮT BUỘC ĐỂ ĐẦU TIÊN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. CSS GIAO DIỆN (ĐÃ FIX LẠI CHO AN TOÀN)
# =====================================================
st.markdown("""
<style>
    /* Ẩn Header/Footer nhưng không ẩn nội dung chính */
    header[data-testid="stHeader"] {display: none;}
    footer {display: none;}
    .stDeployButton {display:none;}

    /* Căn chỉnh khung chat */
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
# 3. KẾT NỐI DỮ LIỆU & AI
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ LỖI: Chưa cấu hình secrets.toml. Vui lòng kiểm tra lại file secrets.")
    st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine_safe():
    # 1. Tải dữ liệu
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu từ Drive"
    
    # 2. Tìm vector DB
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path): return check_path
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    if not text_db_path: return None, "Không tìm thấy dữ liệu vector_db"

    # 3. Load DB
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

# Gọi hàm load
with st.spinner("Đang khởi động não bộ AI..."):
    data_result, status = load_brain_engine_safe()

if status != "OK": st.error(f"Lỗi khởi động: {status}"); st.stop()
db_text, db_image = data_result

# Hàm gọi AI tối ưu (Chặn spam)
def get_ai_response(prompt, context_text, history_context):
    try:
        generation_config = {"temperature": 0.5, "max_output_tokens": 1000}
        model = genai.GenerativeModel('models/gemini-1.5-flash', generation_config=generation_config)

        sys_prompt = f"""
        BẠN LÀ CHUYÊN GIA YOGA & TRỊ LIỆU.
        QUY TẮC: Chỉ trả lời về Yoga, Sức khỏe, Thiền, Dinh dưỡng.
        Nếu câu hỏi KHÔNG LIÊN QUAN (xổ số, chính trị, code, v.v.), trả lời duy nhất: REFUSE_TOPIC
        
        DỮ LIỆU: {context_text}
        LỊCH SỬ: {history_context}
        CÂU HỎI: "{prompt}"
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERR_SYS: {str(e)}"

# =====================================================
# 4. QUẢN LÝ NGƯỜI DÙNG (DATABASE LOCAL)
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    conn.commit(); conn.close()
init_db()

def check_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    r = c.fetchone(); conn.close()
    return r[0] if r else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

# --- Định danh người dùng (Đơn giản hóa để không bị trắng màn hình) ---
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False

# Xác định ID dùng để tính limit
current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id

# Kiểm tra limit
used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 5. GIAO DIỆN CHÍNH
# =====================================================

# --- Sidebar Login ---
with st.sidebar:
    st.title("🔐 Khu Vực VIP")
    if st.session_state.authenticated:
        st.success(f"Chào {st.session_state.username}")
        if st.button("Đăng xuất"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Đăng Nhập"):
                # Sửa lại logic check pass từ secrets
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.rerun()
                else: st.error("Sai mật khẩu")

# --- Thanh đếm lượt ---
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

# --- Màn hình Hết Hạn ---
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    
    if not st.session_state.hide_limit_modal:
        st.info(f"🚫 Bạn ({current_user}) đã hết lượt miễn phí hôm nay.")
        if st.button("🔑 Đăng nhập để mở khóa"):
            st.session_state.hide_limit_modal = True # Tắt modal để hiện sidebar login
            st.rerun()
        st.stop()

# --- Lịch sử Chat ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là AI Yoga. Bạn cần hỗ trợ gì?"}]

if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Ưu đãi độc quyền cho thành viên VIP!</div>
        <a href="https://yogaismylife.vn" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'], caption=img['title'])

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# =====================================================
# 6. XỬ LÝ CHAT (LOGIC CUỐI CÙNG)
# =====================================================
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN TẠM KHÓA: Phát hiện spam câu hỏi sai chủ đề.")
    st.stop()

if prompt := st.chat_input("Nhập câu hỏi tại đây..."):
    # 1. Hiện câu hỏi
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    # 2. Xử lý AI
    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            
            # Lấy ngữ cảnh chat
            chat_history = ""
            for msg in st.session_state.messages[-5:-1]:
                role_t = "User" if msg["role"] == "user" else "Bot"
                chat_history += f"{role_t}: {re.sub(r'<[^>]*>', '', msg['content'])}\n"

            # Tìm kiếm
            context_text = ""
            source_map = {}
            found_images = []
            try:
                docs = db_text.similarity_search(prompt, k=4)
                if db_image: docs += db_image.similarity_search(prompt, k=2)
                for i, d in enumerate(docs):
                    idx = i + 1
                    meta = d.metadata
                    source_map[idx] = {"url": meta.get('url', '#'), "title": meta.get('title', 'Nguồn')}
                    if meta.get('type') == 'image': found_images.append({"url": meta['image_url'], "title": meta.get('title')})
                    context_text += f"\n[Nguồn {idx}]: {d.page_content}\n"
            except: pass

            # Gọi AI
            ai_raw = get_ai_response(prompt, context_text, chat_history)

            # Xử lý kết quả
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    st.session_state.is_blocked = True
                    msg = "🚫 **ĐÃ KHÓA:** Bạn hỏi sai chủ đề quá 3 lần. F5 để reset."
                else:
                    msg = f"⚠️ **CẢNH BÁO:** Chỉ trả lời về Yoga. (Lần {st.session_state.bad_attempts}/3)"
                
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                if st.session_state.is_blocked: st.stop()
            
            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"Lỗi: {ai_raw}")
            else:
                # Format Link
                def replace_ref(match):
                    rid = int(match.group(1))
                    if rid in source_map:
                        info = source_map[rid]
                        return f" <a href='{info['url']}' target='_blank' class='ref-link'>[{rid}]</a>"
                    return ""
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_raw)
                
                st.markdown(final_html, unsafe_allow_html=True)
                if found_images:
                    st.markdown("---")
                    cols = st.columns(3)
                    for i, img in enumerate(found_images):
                        with cols[i % 3]: st.image(img['url'])
                
                st.session_state.messages.append({"role": "assistant", "content": final_html, "images": found_images})
