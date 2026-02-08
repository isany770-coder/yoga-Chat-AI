import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import re
import time
import uuid
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Ẩn Header/Footer */
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}

    /* Khung chat */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Banner */
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
    
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 6px; border-radius: 4px; margin: 0 2px;
        font-size: 0.9em; border: 1px solid #b2dfdb;
    }
    
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. KẾT NỐI DATA (ĐÃ SỬA MODEL CHUẨN THEO KEY CỦA CỤ)
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
        except: return None, "Lỗi tải dữ liệu"
    
    # 2. Tìm đường dẫn file index (Xử lý folder lồng nhau)
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path): return check_path
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    if not text_db_path: return None, "Không tìm thấy vector_db"

    try:
        # === QUAN TRỌNG: ĐÂY LÀ MODEL CỤ VỪA SOI ĐƯỢC ===
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001", 
            google_api_key=api_key
        )
        # ================================================
        
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

with st.spinner("Đang khởi động hệ thống..."):
    data_result, status = load_brain_engine_safe()

if status != "OK": st.error(f"Lỗi: {status}"); st.stop()
db_text, db_image = data_result

# =====================================================
# 3. HÀM AI THÔNG MINH (TỐI ƯU RAG)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        ADMIN_NAME = "An Nguyễn" 
        WEBSITE = "yogaismylife.vn"
        
        # Tìm model chat (Flash)
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        sys_prompt = f"""
        VAI TRÒ: Trợ lý Yoga Y Khoa của **{WEBSITE}**.
        
        NHIỆM VỤ:
        1. Dựa CHỦ YẾU vào "DỮ LIỆU TRA CỨU" bên dưới để trả lời.
        2. Bắt buộc trích dẫn nguồn bằng cú pháp: [Ref: ID] ngay sau thông tin.
        3. Nếu dữ liệu không có thông tin, hãy dùng kiến thức chuyên gia Yoga để trả lời và nói rõ: "Theo kiến thức chuyên môn (ngoài tài liệu)..."
        
        DỮ LIỆU TRA CỨU:
        {context_text}

        LỊCH SỬ CHAT:
        {history_context}

        CÂU HỎI: "{prompt}"
        """
        
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERR_SYS: {str(e)}"

# =====================================================
# 4. DATABASE & SESSION
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

if "user_id" not in st.session_state: st.session_state.user_id = str(uuid.uuid4())[:8]
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga Y Khoa. Bạn cần hỗ trợ gì?"}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id
used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 5. GIAO DIỆN CHÍNH
# =====================================================
with st.sidebar:
    st.title("🔐 VIP Access")
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai mật khẩu")

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

if is_limit_reached:
    # (Giữ nguyên code xử lý limit của cụ)
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    if not st.session_state.hide_limit_modal:
        st.warning("Hết lượt dùng thử. Vui lòng liên hệ Admin.")
        st.stop()

# Hiển thị Chat
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Ưu đãi VIP đang chờ bạn!</div><a href="https://yogaismylife.vn" class="promo-btn">Xem Ngay</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'], use_container_width=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# =====================================================
# 6. XỬ LÝ CHAT (CÓ BẮT LỖI CHI TIẾT)
# =====================================================
if st.session_state.is_blocked: st.error("🚫 TÀI KHOẢN ĐÃ BỊ KHÓA"); st.stop()

if prompt := st.chat_input("Nhập câu hỏi..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu tài liệu Yoga..."):
            
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            context_text = ""
            source_map = {}
            found_images = []
            
            # --- START SEARCH ---
            try:
                # 1. Tìm text
                docs = db_text.similarity_search(prompt, k=4)
                
                # 2. Tìm ảnh (nếu có)
                if db_image: 
                    docs += db_image.similarity_search(prompt, k=2)

                if docs:
                    for i, d in enumerate(docs):
                        idx = i + 1
                        meta = d.metadata
                        link = meta.get('url') or meta.get('source') or '#'
                        title = meta.get('title') or f"Tài liệu {idx}"
                        source_map[idx] = {"url": link, "title": title}
                        
                        if meta.get('type') == 'image' or meta.get('image_url'):
                            found_images.append({"url": meta.get('image_url'), "title": title})

                        content_snippet = d.page_content.replace("\n", " ")[:1500]
                        context_text += f"\n[Ref: {idx}] (Nguồn: {title}): {content_snippet}\n"
                
            except Exception as e:
                st.error(f"❌ Lỗi tìm kiếm: {str(e)}")
                # Vẫn cho AI trả lời dù tìm kiếm lỗi
                context_text = "Hệ thống tra cứu đang bảo trì. Dùng kiến thức chuyên môn."

            # --- START AI ---
            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                msg = "⚠️ Tôi chỉ hỗ trợ kiến thức Yoga."
                st.markdown(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})
            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"Lỗi AI: {ai_raw}")
            else:
                def replace_ref(match):
                    try:
                        rid = int(match.group(1))
                        if rid in source_map:
                            info = source_map[rid]
                            return f'''<a href="{info['url']}" target="_blank" class="ref-link">[{rid}]</a>'''
                    except: pass
                    return ""
                
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_raw, flags=re.IGNORECASE)
                st.markdown(final_html, unsafe_allow_html=True)
                
                if found_images:
                    cols = st.columns(3)
                    for i, img in enumerate(found_images):
                        with cols[i % 3]: st.image(img['url'], use_container_width=True)
                
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": final_html, 
                    "images": found_images
                })
