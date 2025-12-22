import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
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

# =====================================================
# 2. CSS GIAO DIỆN (ĐÃ TỐI ƯU HIỂN THỊ QUẢNG CÁO)
# =====================================================
st.markdown("""
<style>
    /* Nền trắng chữ đen cho hệ thống */
    [data-testid="stAppViewContainer"], .stApp {
        background-color: white !important;
        color: #31333F !important;
    }
    
    /* CHỈ ép màu đen cho chữ trong khung Chat */
    div[data-testid="stChatMessage"] p {
        color: #31333F !important;
    }

    /* Ẩn toolbar/header của Streamlit */
    [data-testid="stToolbar"], header, footer {
        display: none !important;
    }

    /* --- CSS QUẢNG CÁO (FIX LỖI MẤT CHỮ) --- */
    .ad-banner {
        position: fixed;
        bottom: 85px; left: 15px; right: 15px;
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%) !important;
        border: 2px solid #ffcc80 !important;
        border-radius: 12px;
        padding: 12px 15px;
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    .ad-content {
        color: #e65100 !important; /* Ép màu cam đậm cho chữ quảng cáo */
        font-weight: 800 !important;
        font-size: 15px !important;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .ad-btn {
        background-color: #e65100 !important;
        color: white !important;
        padding: 8px 18px;
        border-radius: 25px;
        text-decoration: none !important;
        font-weight: bold !important;
        font-size: 13px !important;
    }

    /* Input Chat nổi */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 20px !important;
        z-index: 10000;
        background-color: white !important;
    }

    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background: #f0f0f0; z-index: 10001; }
    .usage-bar-fill { height: 100%; background: #0f988b; }
    .usage-text { position: fixed; top: 10px; right: 15px; background: white; padding: 2px 10px; border-radius: 10px; font-size: 11px; color: #0f988b; font-weight: bold; border: 1px solid #0f988b; z-index: 10001; }

    .main .block-container { padding-bottom: 220px !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. KẾT NỐI API & DATABASE (GIỮ NGUYÊN)
# =====================================================
FILE_ID_DRIVE = "1vOvvanNvDaLwP8Xs4nn1UhkciRvTxzyA"
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
EXTRACT_PATH = "/tmp/bo_nao_vector"

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Thiếu API KEY")
    st.stop()

@st.cache_resource
def load_brain():
    if not os.path.exists(EXTRACT_PATH):
        try:
            output_zip = "/tmp/data.zip"
            gdown.download(URL_DRIVE, output_zip, quiet=True)
            with zipfile.ZipFile(output_zip, 'r') as z:
                z.extractall("/tmp/")
        except: return None, None
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return db, model
    except: return None, None

db, model = load_brain()

# Quản lý Database
USAGE_DB_FILE = "/tmp/usage_db.json"
def get_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

user_key = st.session_state.username if st.session_state.authenticated else "anonymous_guest"
db_data = get_data()
today = str(datetime.date.today())

if user_key not in db_data or db_data[user_key].get("date") != today:
    db_data[user_key] = {"date": today, "count": 0, "history": []}

used = db_data[user_key]["count"]
limit = 25 if st.session_state.authenticated else 10
st.session_state.messages = db_data[user_key]["history"]

# Thanh tiến trình lượt dùng
st.markdown(f'<div class="usage-bar-container"><div class="usage-bar-fill" style="width:{(used/limit)*100}%;"></div></div><div class="usage-text">⚡ {used}/{limit}</div>', unsafe_allow_html=True)

# =====================================================
# 4. HIỂN THỊ QUẢNG CÁO & CHAT
# =====================================================

# Quảng cáo hiện khi chưa đăng nhập
if not st.session_state.authenticated:
    st.markdown("""
    <div class="ad-banner">
        <div class="ad-content">
            <span>🎁</span> Combo Thảm + Gạch Yoga giảm 30%!
        </div>
        <a href="https://yogaismylife.vn/khuyen-mai" target="_blank" class="ad-btn">Xem ngay 👉</a>
    </div>
    """, unsafe_allow_html=True)

# Hiển thị lịch sử chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# Xử lý Chat Input
if used < limit:
    if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
        db_data[user_key]["count"] += 1
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if db:
                docs = db.similarity_search(prompt, k=3)
                context = "\n".join([d.page_content for d in docs])
                
                # System Prompt: (Giữ nguyên theo ý bác)
            sys_prompt = (
                f"Bạn là chuyên gia Yoga. Hãy trả lời dựa trên DỮ LIỆU NGUỒN.\n"
                f"1. Trả lời NGẮN GỌN (tối đa 6-7 gạch đầu dòng, dưới 100 từ).\n"
                f"2. Đi thẳng vào trọng tâm chuyên môn.\n"
                f"3. Chỉ dùng thông tin có trong NGUỒN bên dưới.\n"
                f"4. Tuyệt đối không tự bịa link hoặc chèn link vào bài viết.\n\n"
                f"DỮ LIỆU NGUỒN:\n{context_string}\n\n"
                f"CÂU HỎI: {prompt}"
            )
                
                try:
                    response = model.generate_content(sys_prompt).text
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    db_data[user_key]["history"] = st.session_state.messages
                    save_data(db_data)
                    st.rerun()
                except:
                    st.error("Lỗi kết nối AI.")
else:
    st.warning("Bạn đã hết lượt dùng hôm nay. Vui lòng đăng nhập để nhận thêm!")

# Form đăng nhập cuối trang
if not st.session_state.authenticated:
    with st.expander("🔐 Đăng nhập Member"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Xác nhận"):
            if u == "admin" and p == "yoga888":
                st.session_state.authenticated = True
                st.session_state.username = u
                st.rerun()
