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
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}
    
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
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
    
    /* Style cho phần Debug */
    .debug-box { font-size: 12px; color: #666; background: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px dashed #ccc; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. KẾT NỐI (CÓ CHỨC NĂNG ĐỔI MODEL EMBEDDING)
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

# --- SIDEBAR CẤU HÌNH (ĐỂ SỬA LỖI KHÔNG TÌM THẤY DATA) ---
with st.sidebar:
    st.title("⚙️ Cấu Hình Kỹ Thuật")
    st.info("Nếu AI báo không có dữ liệu, hãy thử đổi Model bên dưới:")
    
    # Cho phép chọn model embedding
    selected_embedding_model = st.selectbox(
        "Model Đọc Dữ Liệu (Embedding):",
        ["models/text-embedding-004", "models/embedding-001"],
        index=0,
        help="Hãy thử chuyển sang embedding-001 nếu bạn dùng code cũ để tạo data."
    )
    
    # Cho phép chỉnh độ nhạy
    search_k = st.slider("Số lượng tài liệu đọc mỗi lần:", 3, 10, 5)

@st.cache_resource(hash_funcs={str: lambda x: x}) # Cache lại dựa trên tên model
def load_brain_engine_custom(model_name):
    # 1. Tải
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải Drive", 0
    
    # 2. Tìm vector_db
    def find_db_path(target):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target in dirs:
                check = os.path.join(root, target)
                if "index.faiss" in os.listdir(check): return check
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    if not text_db_path: return None, "Không tìm thấy folder vector_db", 0

    # 3. Load với Model được chọn
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # Đếm số lượng vector (check xem load được bao nhiêu bài)
        doc_count = db_text.index.ntotal 
        
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
            
        return (db_text, db_image), "OK", doc_count
    except Exception as e: return None, str(e), 0

# Load dữ liệu lại mỗi khi đổi model
with st.spinner(f"Đang đọc dữ liệu bằng {selected_embedding_model}..."):
    data_result, status, doc_count = load_brain_engine_custom(selected_embedding_model)

if status != "OK": 
    st.sidebar.error(f"Lỗi Load: {status}")
    db_text, db_image = None, None
else:
    db_text, db_image = data_result
    st.sidebar.success(f"✅ Đã load {doc_count} tài liệu!") # Báo số lượng bài tìm thấy

# =====================================================
# 3. HÀM AI (LOGIC CỐT LÕI)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        # --- THÔNG TIN ADMIN ---
        ADMIN_NAME = "Coach Nguyễn Văn A"
        ADMIN_BIO = "Chuyên gia Yoga Trị liệu."
        WEBSITE = "yogaismylife.vn"
        PROFILE_LINK = "https://zalo.me/..."
        
        # --- MODEL GEMINI FLASH ---
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        # --- CHECK DỮ LIỆU ---
        has_data = len(context_text.strip()) > 10
        instruction = "Dữ liệu tra cứu bên dưới."
        if not has_data:
            instruction = "⚠️ CẢNH BÁO: Không tìm thấy tài liệu phù hợp trong Database. HÃY DÙNG KIẾN THỨC CỦA BẠN để trả lời nhưng phải thông báo cho người dùng biết là dữ liệu nội bộ chưa có."

        sys_prompt = f"""
        VAI TRÒ: Trợ lý Yoga của {WEBSITE} (Admin: {ADMIN_NAME}).
        
        NHIỆM VỤ 1: CHẾ ĐỘ TRẢ LỜI
        - ƯU TIÊN TUYỆT ĐỐI: Dùng thông tin từ "DỮ LIỆU TRA CỨU" -> Ghi nguồn [Ref: ID].
        - Nếu "DỮ LIỆU TRA CỨU" có nội dung liên quan (dù chỉ một chút): HÃY KHAI THÁC TỐI ĐA NÓ.
        - Chỉ khi hoàn toàn không có dữ liệu: Mới dùng kiến thức y khoa chung của bạn.
        
        NHIỆM VỤ 2: BỘ LỌC
        - Hỏi sai chủ đề: REFUSE_TOPIC
        - Hỏi Admin: Giới thiệu {ADMIN_NAME}, Link: {PROFILE_LINK}.

        NHIỆM VỤ 3: TRÌNH BÀY
        - Ngắn gọn (Max 250 từ). Dùng <b>, <ul>, <li>.

        TRẠNG THÁI DỮ LIỆU: {instruction}
        
        DỮ LIỆU TRA CỨU (RAG):
        {context_text}

        LỊCH SỬ:
        {history_context}

        CÂU HỎI: "{prompt}"
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e: return f"ERR_SYS: {str(e)}"

# =====================================================
# 4. QUẢN LÝ DATABASE & SESSION
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
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga. Mời bạn đặt câu hỏi."}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id
used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 5. GIAO DIỆN
# =====================================================
with st.sidebar:
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai mật khẩu")

# Thanh đếm
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
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    with st.container(border=True):
        st.info(f"Hết lượt miễn phí ({used}/{LIMIT}). Vui lòng đăng nhập.")
        with st.form("login_limit_screen"):
            c1, c2 = st.columns(2)
            with c1: u_lim = st.text_input("User")
            with c2: p_lim = st.text_input("Pass", type="password")
            if st.form_submit_button("🔓 Mở Khóa"):
                if st.secrets["passwords"].get(u_lim) == p_lim:
                    st.session_state.authenticated = True; st.session_state.username = u_lim; st.rerun()
                else: st.error("Sai thông tin")
    st.stop()

# =====================================================
# 6. XỬ LÝ CHAT (CÓ DEBUG DỮ LIỆU)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Yoga Trị Liệu Tại Nhà</div><a href="https://yogaismylife.vn" class="promo-btn">Xem Ngay</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'])

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if st.session_state.is_blocked:
    st.error("🚫 ĐÃ KHÓA: Spam câu hỏi sai chủ đề."); st.stop()

if prompt := st.chat_input("Hỏi bệnh lý, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu dữ liệu..."):
            
            chat_history = ""
            for msg in st.session_state.messages[-5:-1]:
                chat_history += f"{msg['role']}: {re.sub(r'<[^>]*>', '', msg['content'])}\n"

            # --- DEBUG: KIỂM TRA XEM CÓ TÌM THẤY GÌ KHÔNG ---
            context_text = ""
            source_map = {}
            found_images = []
            debug_info = "" # Biến để in thông tin debug
            
            if db_text:
                try:
                    # Dùng search_k từ sidebar
                    docs = db_text.similarity_search(prompt, k=search_k)
                    
                    # Nếu có ảnh thì tìm ảnh
                    if db_image: docs += db_image.similarity_search(prompt, k=2)
                    
                    if not docs:
                        debug_info = "⚠️ Không tìm thấy vector nào khớp!"
                    else:
                        debug_info = f"✅ Tìm thấy {len(docs)} đoạn dữ liệu khớp."
                        
                    for i, d in enumerate(docs):
                        idx = i + 1
                        meta = d.metadata
                        source_map[idx] = {"url": meta.get('url', '#'), "title": meta.get('title', 'Nguồn')}
                        if meta.get('type') == 'image': found_images.append({"url": meta['image_url'], "title": meta.get('title')})
                        context_text += f"\n[Nguồn {idx}]: {d.page_content}\n"
                except Exception as e:
                    debug_info = f"❌ Lỗi tìm kiếm: {e}"
            else:
                debug_info = "❌ Chưa load được Database (Kiểm tra lại Model Embedding)"

            # In thông tin Debug (chỉ hiện cho Admin hoặc User nếu cần thiết)
            # st.caption(f"🔍 System Log: {debug_info}") 

            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    st.session_state.is_blocked = True
                    msg = "🚫 ĐÃ KHÓA: Spam sai chủ đề."
                else:
                    msg = f"⚠️ CHỈNH ĐỐN: Tôi chỉ trả lời về Yoga/Sức khỏe. (Vi phạm {st.session_state.bad_attempts}/3)"
                st.markdown(msg); st.session_state.messages.append({"role": "assistant", "content": msg})
                if st.session_state.is_blocked: st.stop()
            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"Lỗi: {ai_raw}")
            else:
                def replace_ref(match):
                    rid = int(match.group(1))
                    if rid in source_map:
                        info = source_map[rid]
                        return f" <a href='{info['url']}' target='_blank' class='ref-link'>[{rid}]</a>"
                    return ""
                
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_raw)
                
                # Hiện Debug nếu không tìm thấy dữ liệu để bạn biết
                if "Không tìm thấy tài liệu" in final_html or len(source_map) == 0:
                    st.warning("⚠️ Lưu ý: Câu trả lời này dùng kiến thức chung do không tìm thấy dữ liệu trong Database của bạn. Hãy kiểm tra lại Embedding Model ở Sidebar.")

                st.markdown(final_html, unsafe_allow_html=True)
                if found_images:
                    st.markdown("---")
                    cols = st.columns(3)
                    for i, img in enumerate(found_images):
                        with cols[i % 3]: st.image(img['url'])
                
                st.session_state.messages.append({"role": "assistant", "content": final_html, "images": found_images})
