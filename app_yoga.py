import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import re
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH CƠ BẢN
# =====================================================
st.set_page_config(page_title="Yoga Assistant Pro", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header, footer, .stDeployButton {display: none !important;}
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    .ref-link { color: #00796b; font-weight: bold; text-decoration: none; background: #e0f2f1; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOAD DATA (GIỮ NGUYÊN)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except: st.error("Chưa cấu hình API Key"); st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải"
    
    def find_db_path(target):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target in dirs and "index.faiss" in os.listdir(os.path.join(root, target)):
                return os.path.join(root, target)
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    if not text_db_path: return None, "Thiếu vector_db"

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        db_image = None
        if image_db_path: db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

data_result, status = load_brain_engine_safe()
if status != "OK": st.error(status); st.stop()
db_text, db_image = data_result

# =====================================================
# 3. QUẢN LÝ USER (ĐƠN GIẢN HÓA ĐỂ TRÁNH LỖI TRẮNG MÀN HÌNH)
# =====================================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0 # Biến đếm lỗi
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False # Biến khóa

# Hàm đếm lượt
def check_limit():
    # Logic đơn giản: Nếu chưa đăng nhập thì giới hạn 5, đăng nhập rồi thì 50
    limit = 50 if st.session_state.authenticated else 5
    if "usage_count" not in st.session_state: st.session_state.usage_count = 0
    return st.session_state.usage_count, limit

used, limit = check_limit()

# Sidebar Login
with st.sidebar:
    if not st.session_state.authenticated:
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("Login"):
            if st.secrets["passwords"].get(u) == p:
                st.session_state.authenticated = True; st.rerun()
            else: st.error("Sai pass")

# Hiển thị Limit
if used >= limit:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.error(f"Hết lượt ({used}/{limit}). Vui lòng F5 hoặc đăng nhập.")
    st.stop()

# =====================================================
# 4. CHAT LOGIC (QUAY VỀ LOGIC CŨ CỦA BẠN + THÊM BLOCK)
# =====================================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]: st.image(img['url'])

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# KIỂM TRA KHÓA TRƯỚC KHI CHAT
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN ĐÃ BỊ KHÓA DO HỎI SAI CHỦ ĐỀ 3 LẦN.")
    st.stop()

if prompt := st.chat_input("Hỏi gì đi bạn..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)
    st.session_state.usage_count += 1

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm..."):
            try:
                # 1. TÌM MODEL (Code cũ của bạn chạy ngon đoạn này)
                valid_model = 'models/gemini-1.5-flash'
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            if 'flash' in m.name.lower(): valid_model = m.name; break
                except: pass
                model = genai.GenerativeModel(valid_model)

                # 2. TÌM KIẾM DỮ LIỆU
                docs = db_text.similarity_search(prompt, k=5)
                if db_image: docs += db_image.similarity_search(prompt, k=2)

                context_text = ""
                source_map = {}
                found_images = []
                
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    meta = d.metadata
                    source_map[doc_id] = {"url": meta.get('url', '#'), "title": meta.get('title', 'Nguồn')}
                    if meta.get('type') == 'image': found_images.append({"url": meta['image_url'], "title": meta.get('title')})
                    context_text += f"\n[Nguồn {doc_id}]: {d.page_content}\n"

                # 3. PROMPT (Thêm yêu cầu REFUSE_TOPIC để chặn)
                sys_prompt = f"""
                Bạn là Trợ lý Yoga Y Khoa (Website: yogaismylife.vn - Admin: Coach Nguyễn Văn A).
                
                QUY TẮC AN TOÀN:
                - Nếu câu hỏi KHÔNG liên quan Yoga/Sức khỏe/Admin (ví dụ: xổ số, chính trị, code...): Trả lời duy nhất: REFUSE_TOPIC
                
                YÊU CẦU TRẢ LỜI:
                - Ngắn gọn dưới 200 từ.
                - Dùng thông tin từ DỮ LIỆU bên dưới. Nếu không có, dùng kiến thức của bạn.
                - Khi dùng nguồn, ghi: [Ref: ID]
                
                DỮ LIỆU:
                {context_text}
                
                CÂU HỎI: "{prompt}"
                """

                response = model.generate_content(sys_prompt)
                ai_resp = response.text.strip()

                # 4. XỬ LÝ LOGIC BLOCK (MỚI THÊM VÀO)
                if "REFUSE_TOPIC" in ai_resp:
                    st.session_state.bad_attempts += 1
                    msg = f"⚠️ Tôi chỉ trả lời về Yoga. (Lần {st.session_state.bad_attempts}/3)"
                    if st.session_state.bad_attempts >= 3:
                        st.session_state.is_blocked = True
                        msg = "🚫 ĐÃ KHÓA: Bạn hỏi sai chủ đề 3 lần."
                    
                    st.markdown(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    if st.session_state.is_blocked: st.stop()
                
                else:
                    # 5. XỬ LÝ LINK (GIỮ NGUYÊN CODE CŨ CỦA BẠN - CHẠY PHÀ PHÀ)
                    def replace_ref(match):
                        ref_id = int(match.group(1))
                        if ref_id in source_map:
                            info = source_map[ref_id]
                            return f" <a href='{info['url']}' target='_blank' class='ref-link'>[{ref_id}]</a>"
                        return ""
                    
                    final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_resp)
                    st.markdown(final_html, unsafe_allow_html=True)
                    
                    if found_images:
                        st.markdown("---")
                        cols = st.columns(3)
                        for i, img in enumerate(found_images):
                            with cols[i % 3]: st.image(img['url'])
                    
                    st.session_state.messages.append({"role": "assistant", "content": final_html, "images": found_images})

            except Exception as e:
                st.error(f"Lỗi: {e}")
