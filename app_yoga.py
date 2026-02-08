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
# 2. KẾT NỐI DATA
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
    # 1. Tải và giải nén (Giữ nguyên)
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu"
    
    # 2. Tìm đường dẫn file index
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
        # === QUAY VỀ MODEL MỚI NHẤT (VÌ ĐÃ UPDATE THƯ VIỆN) ===
        # Thư viện mới (v1.0.0+) sẽ tự động xử lý được model này mà không bị lỗi 404
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=api_key
        )
        
        # Thử load DB. Nếu DB cũ được tạo bằng model 001 thì kết quả tìm kiếm có thể kém đi 
        # nhưng ÍT NHẤT nó sẽ không báo lỗi đỏ nữa. 
        # Nếu muốn chuẩn 100% thì cần tạo lại file index.faiss bằng model 004.
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
# 3. HÀM AI THÔNG MINH (BẢN FIX: TỰ ĐỘNG DÙNG KIẾN THỨC KHI THIẾU DATA)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        # --- 1. THÔNG TIN CÁ NHÂN ---
        ADMIN_NAME = "An Nguyễn" 
        ADMIN_BIO = "Kỹ sư khoa học máy tính"
        WEBSITE = "yogaismylife.vn"
        PROFILE_LINK = "https://yogaismylife.vn/nguoi-sang-lap-hanh-trinh-tao-nen-yogaismylife-vn/"
        
        # --- 2. TÌM MODEL ---
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
       # --- 3. SYSTEM PROMPT (ÉP BUỘC DÙNG DATA) ---
        # Chỉ dẫn rõ ràng hơn: Input là Ref ID, Output phải là Ref ID
        sys_prompt = f"""
        VAI TRÒ: Trợ lý Yoga Y Khoa chuyên nghiệp của {WEBSITE}.
        
        QUY TẮC BẤT DI BẤT DỊCH:
        1. DỮ LIỆU LÀ VUA: Phải ưu tiên tuyệt đối thông tin trong phần "DỮ LIỆU TRA CỨU" bên dưới.
        2. TRÍCH DẪN: Mọi thông tin lấy từ dữ liệu PHẢI trích dẫn bằng cú pháp chính xác: [Ref: ID].
           - Ví dụ: "Yoga giúp giảm đau lưng [Ref: 1], cải thiện giấc ngủ [Ref: 2]."
        3. KHI KHÔNG CÓ DỮ LIỆU: Nếu và CHỈ NẾU trong "DỮ LIỆU TRA CỨU" hoàn toàn không nhắc đến vấn đề hỏi, hãy dùng kiến thức Yoga chuẩn y khoa để trả lời và nói rõ: "Theo kiến thức chuyên môn (chưa có trong tài liệu của {ADMIN_NAME})..."
        
        ĐỊNH DẠNG TRẢ LỜI:
        - Dùng thẻ <b> để in đậm ý chính.
        - Dùng danh sách <ul><li> cho các bước hoặc lợi ích.
        - Giọng văn: Thân thiện, khuyến khích, chuyên gia (Namaste).

        DỮ LIỆU TRA CỨU (Kèm ID để trích dẫn):
        {context_text}

        LỊCH SỬ CHAT:
        {history_context}

        CÂU HỎI NGƯỜI DÙNG: "{prompt}"
        
        TRẢ LỜI (Ngắn gọn, súc tích, CÓ TRÍCH DẪN [Ref: ID]):
        """
        
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERR_SYS: {str(e)}"

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

# Session
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

# --- Sidebar (Chỉ hiện khi đã đăng nhập hoặc muốn đăng nhập chủ động) ---
with st.sidebar:
    st.title("🔐 VIP Access")
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
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

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (GIỮ NGUYÊN)
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False
    
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    if not st.session_state.hide_limit_modal:
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        with col_center:
            with st.container(border=True):
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử...<br>
                            Liên hệ Admin để nhận mã kích hoạt:
                        </p>
                        <a href="https://zalo.me/84963759566" target="_blank" 
                           style="display: inline-block; width: 100%; background-color: #009688; 
                                  color: white; padding: 12px 0; border-radius: 30px; 
                                  text-decoration: none; font-weight: bold; margin: 15px 0;">
                           💬 Nhận mã kích hoạt qua Zalo
                        </a>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập Ngay"):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Thành công!")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("❌ Sai thông tin")
        st.stop()

# =====================================================
# 6. HIỂN THỊ CHAT (KHI CHƯA HẾT LƯỢT)
# =====================================================

# Lịch sử chat
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Ưu đãi VIP đang chờ bạn!</div><a href="https://yogaismylife.vn" class="promo-btn">Xem Ngay</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'])

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# XỬ LÝ CHAT
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN ĐÃ BỊ KHÓA do hỏi sai chủ đề nhiều lần. Vui lòng F5.")
    st.stop()

# =====================================================
# THAY THẾ TOÀN BỘ PHẦN XỬ LÝ CHAT Ở CUỐI FILE BẰNG ĐOẠN NÀY
# =====================================================

if prompt := st.chat_input("Nhập câu hỏi..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner("Đang đọc tài liệu..."):
            
            # 1. Lịch sử chat
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            # 2. Tìm kiếm (CÓ BÁO LỖI)
            context_text = ""
            source_map = {}
            found_images = []
            
            # --- DEBUG BLOCK: Kiểm tra xem DB có dữ liệu không ---
            try:
                # Nếu index chưa load được thì db_text sẽ None hoặc lỗi
                num_docs = db_text.index.ntotal
                # st.caption(f"🔍 Trạng thái kho: {num_docs} vector. Model: {db_text.embeddings.model}")
            except:
                st.error("❌ Lỗi nghiêm trọng: Kho dữ liệu chưa được nạp thành công!")
                st.stop()
            # ---------------------------------------------------

            try:
                # Tăng k lên 5 để tìm kỹ hơn
                docs = db_text.similarity_search(prompt, k=5)
                
                if db_image: 
                    try:
                        docs += db_image.similarity_search(prompt, k=2)
                    except Exception as e_img:
                        st.warning(f"⚠️ Lỗi tìm ảnh (bỏ qua): {str(e_img)}")

                if not docs:
                    context_text = "" # Để trống để AI tự xử lý
                else:
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
                # ĐÂY LÀ CHỖ QUAN TRỌNG NHẤT: BÁO LỖI RA MÀN HÌNH
                st.error(f"❌ Lỗi Tìm Kiếm: {str(e)}")
                st.info("💡 Mẹo: Chụp ảnh lỗi này gửi cho kỹ thuật để sửa ngay lập tức.")
                st.stop()

            # 3. Gọi AI
            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            # 4. Xử lý hiển thị
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                msg = "⚠️ Tôi chỉ hỗ trợ kiến thức về Yoga."
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
                            return f'''<a href="{info['url']}" target="_blank" 
                                        style="background:#e0f2f1; color:#00695c; font-weight:bold; 
                                        padding:0 5px; border-radius:4px; text-decoration:none; 
                                        font-size:0.8em;">[{rid}]</a>'''
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
