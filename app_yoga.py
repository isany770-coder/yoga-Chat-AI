import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS (GIAO DIỆN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Tùy chỉnh: Làm đẹp khung chat, ẩn header mặc định, thiết kế thẻ quảng cáo
st.markdown("""
<style>
    /* Ẩn Header mặc định của Streamlit */
    header[data-testid="stHeader"] {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Nền trắng sạch sẽ */
    .stApp { background-color: #ffffff; }

    /* Khung Chat Input cố định dưới cùng */
    div[data-testid="stChatInput"] {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 90%;
        max-width: 800px;
        z-index: 1000;
        background-color: white;
        border-radius: 30px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        padding: 5px;
        border: 1px solid #e0e0e0;
    }
    
    /* Thanh Quảng Cáo (Banner) */
    .promo-banner {
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%);
        border-left: 5px solid #ff9800;
        padding: 12px 20px;
        margin-bottom: 25px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .promo-text { color: #e65100; font-weight: bold; font-size: 15px; }
    .promo-sub { color: #ef6c00; font-size: 13px; }
    .promo-btn {
        background-color: #ff9800; color: white !important;
        padding: 8px 16px; border-radius: 20px;
        text-decoration: none; font-weight: bold; font-size: 13px;
        box-shadow: 0 2px 5px rgba(230, 81, 0, 0.3);
        transition: all 0.3s;
    }
    .promo-btn:hover { background-color: #e65100; transform: translateY(-1px); }

    /* Giao diện tin nhắn */
    .stChatMessage { padding: 10px; border-radius: 10px; }
    div[data-testid="stMarkdownContainer"] p { font-size: 16px; line-height: 1.6; }
    
    /* Hộp nguồn tham khảo */
    .source-box {
        background-color: #f1f8e9;
        border: 1px solid #c5e1a5;
        border-radius: 10px;
        padding: 15px;
        margin-top: 15px;
        font-size: 0.9em;
    }
    .source-title { font-weight: bold; color: #33691e; margin-bottom: 8px; display: flex; align-items: center; gap: 5px; }
    .source-link { 
        display: block; margin-bottom: 6px; 
        text-decoration: none; color: #2e7d32; 
        font-weight: 500; transition: 0.2s;
    }
    .source-link:hover { color: #1b5e20; text-decoration: underline; }
    .tag-type { 
        font-size: 0.7em; padding: 2px 6px; border-radius: 4px; 
        margin-right: 8px; font-weight: bold; text-transform: uppercase;
    }
    .tag-science { background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; }
    .tag-blog { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }

    /* Thanh giới hạn lượt dùng */
    .usage-bar-wrapper {
        position: fixed; top: 0; left: 0; width: 100%; height: 4px;
        background: #f0f0f0; z-index: 9999;
    }
    .usage-fill { height: 100%; background: linear-gradient(90deg, #4db6ac, #009688); transition: width 0.5s; }
    .usage-badge {
        position: fixed; top: 10px; right: 10px;
        background: rgba(255,255,255,0.95);
        padding: 4px 12px; border-radius: 15px;
        font-size: 12px; color: #00796b; font-weight: bold;
        border: 1px solid #b2dfdb; z-index: 10000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. KHỞI TẠO NÃO BỘ (BACKEND)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Lỗi: Chưa cấu hình secrets.toml (Thiếu API Key hoặc File ID)")
    st.stop()

# Đường dẫn file
ZIP_PATH = "/tmp/brain_data.zip"
EXTRACT_PATH = "/tmp/brain_data_extracted"
DB_PATH = "user_usage.db" # Database SQLite an toàn

@st.cache_resource
def load_brain_engine():
    """Tải và khởi động não bộ AI một lần duy nhất"""
    # 1. Tải file nếu chưa có
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            
            with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            
            # Dọn dẹp RAM ngay lập tức
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            gc.collect()
        except Exception as e:
            return None, None, f"Lỗi tải dữ liệu: {str(e)}"

    # 2. Tìm file FAISS
    vector_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_path = root
                break
        if vector_path: break
    
    if not vector_path:
        return None, None, "Không tìm thấy file vector (.faiss)"

    # 3. Load Model
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        vector_db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        chat_model = genai.GenerativeModel('gemini-flash-latest')
        return vector_db, chat_model, "OK"
    except Exception as e:
        return None, None, f"Lỗi khởi động AI: {str(e)}"

db, model, status = load_brain_engine()

if status != "OK":
    st.warning(f"⚠️ Đang bảo trì hệ thống não bộ: {status}. Vui lòng thử lại sau 1 phút.")
    st.stop()

# =====================================================
# 3. QUẢN LÝ USER & DATABASE (CHỐNG SẬP)
# =====================================================
def init_db():
    """Tạo database SQLite nếu chưa có"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tạo bảng: user_id | ngày | số lần dùng
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
    conn.commit()
    conn.close()

def check_usage(user_id):
    """Kiểm tra số lượt đã dùng hôm nay"""
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_usage(user_id):
    """Tăng số lượt dùng lên 1"""
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Thử insert, nếu trùng (đã có hôm nay) thì update
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit()
    conn.close()

# Khởi tạo DB khi chạy app
init_db()

# Lấy ID người dùng (Nếu chưa đăng nhập thì dùng IP giả lập)
def get_user_key():
    if st.session_state.get("authenticated"):
        return st.session_state.username
    # Lấy IP để giới hạn khách vãng lai
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        headers = _get_headers()
        return headers.get("X-Forwarded-For", "guest_unknown").split(",")[0]
    except:
        return "guest_unknown"

# =====================================================
# 4. LOGIC CHÍNH (SESSION & AUTH)
# =====================================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role":"assistant", "content":"Namaste! 🙏 Tôi là AI Yoga. Bạn đang gặp vấn đề gì (đau lưng, mất ngủ, hay cần lộ trình tập)?"}]

user_id = get_user_key()
used_count = check_usage(user_id)

# Cấu hình giới hạn
LIMIT = 30 if st.session_state.authenticated else 5
can_chat = used_count < LIMIT

# Hiển thị thanh tiến trình sử dụng
percent = min(100, int((used_count / LIMIT) * 100))
st.markdown(f"""
    <div class="usage-bar-wrapper"><div class="usage-fill" style="width: {percent}%;"></div></div>
    <div class="usage-badge">⚡ {used_count}/{LIMIT} lượt</div>
""", unsafe_allow_html=True)

# =====================================================
# 5. GIAO DIỆN CHAT & XỬ LÝ
# =====================================================

# A. Banner Quảng Cáo (Chỉ hiện khi chưa đăng nhập hoặc lượt dùng ít)
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div>
            <div class="promo-text">🎁 Ưu đãi độc quyền hôm nay!</div>
            <div class="promo-sub">Combo Thảm tập + Gạch Yoga giảm 30% - Freeship toàn quốc</div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Săn Deal Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# B. Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# C. Xử lý khi Hết lượt (Chặn chat & Hiện form đăng nhập)
if not can_chat:
    st.markdown("""
    <div style="text-align:center; padding:30px; border:2px dashed #ff9800; border-radius:15px; margin-top:20px; background:#fff8e1;">
        <h3 style="color:#ef6c00;">🚫 Đã hết lượt dùng thử</h3>
        <p>Vui lòng đăng nhập để tiếp tục tra cứu không giới hạn.</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        u = col1.text_input("Username")
        p = col2.text_input("Password", type="password")
        if st.form_submit_button("Đăng Nhập Ngay", use_container_width=True):
            stored_pass = st.secrets["passwords"].get(u)
            if stored_pass and p == stored_pass:
                st.session_state.authenticated = True
                st.session_state.username = u
                st.success("Đăng nhập thành công! Đang tải lại...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Sai tài khoản hoặc mật khẩu!")
    st.stop() # Dừng app ở đây, không cho chat tiếp

# D. Xử lý Chat Logic (Khi người dùng nhập)
if prompt := st.chat_input("Hỏi tôi về sức khỏe, bài tập..."):
    # 1. Hiển thị tin nhắn user
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id) # Trừ lượt dùng

    # 2. Xử lý AI
    with st.chat_message("assistant"):
        with st.spinner("🧘 Đang tra cứu dữ liệu y khoa & yoga..."):
            try:
                # BƯỚC 1: Tìm kiếm (RAG) - Chỉ lấy top 15 để chính xác
                docs = db.similarity_search(prompt, k=15)
                
                # BƯỚC 2: Lọc & Chuẩn bị Context
                context_text = ""
                unique_links = {} # Dùng để khử trùng lặp link
                
                for d in docs:
                    url = d.metadata.get('url', '')
                    title = d.metadata.get('title', 'Tài liệu')
                    type_ = d.metadata.get('type', 'blog')
                    
                    # Chỉ thêm vào context
                    context_text += f"Nguồn: {title}\nNội dung: {d.page_content}\n---\n"
                    
                    # Lưu link lại để hiển thị sau (nếu url hợp lệ)
                    if url and "http" in url and url not in unique_links:
                        unique_links[url] = {"title": title, "type": type_}

                # BƯỚC 3: Tạo Prompt cho Gemini
                sys_prompt = f"""
                Bạn là Trợ lý Yoga chuyên nghiệp. Dựa vào thông tin sau để trả lời:
                {context_text}
                
                Câu hỏi: {prompt}
                
                Yêu cầu:
                1. Trả lời thân thiện, ngắn gọn, đi thẳng vào vấn đề.
                2. Nếu là bệnh lý, khuyên đi khám bác sĩ trước.
                3. Tuyệt đối KHÔNG bịa ra kiến thức nếu không có trong "Nguồn".
                4. Trình bày bằng Markdown, dùng gạch đầu dòng cho dễ đọc.
                """
                
                # Gọi Gemini
                response = model.generate_content(sys_prompt)
                ai_text = response.text

                # BƯỚC 4: Ghép Link nguồn vào cuối (Chỉ hiện 3 link liên quan nhất)
                if unique_links:
                    ai_text += "\n\n" + "<div class='source-box'><div class='source-title'>📚 Nguồn tham khảo:</div>"
                    # Lấy tối đa 4 link đầu tiên từ kết quả tìm kiếm (thường là liên quan nhất)
                    count_link = 0
                    for url, info in unique_links.items():
                        if count_link >= 4: break
                        tag_class = "tag-science" if info['type'] == 'science' else "tag-blog"
                        tag_label = "KHOA HỌC" if info['type'] == 'science' else "BÀI VIẾT"
                        ai_text += f"<a href='{url}' target='_blank' class='source-link'><span class='tag-type {tag_class}'>{tag_label}</span> {info['title']}</a>"
                        count_link += 1
                    ai_text += "</div>"

                st.markdown(ai_text, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})

            except Exception as e:
                st.error("Hệ thống đang quá tải, vui lòng hỏi lại sau 5 giây.")
                print(f"Error: {e}")
