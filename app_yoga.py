import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- CẤU HÌNH LOGO & ZALO ---
LOGO_URL = "https://yogaismylife.vn/wp-content/uploads/2025/02/png-lo-final.webp"
ZALO_LINK = "https://zalo.me/84963759566"

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Yoga Guru AI",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed" # Mặc định đóng cho gọn mobile
)

# --- 2. CSS "PHẪU THUẬT THẨM MỸ" (FIX LỖI MẤT NÚT) ---
st.markdown("""
<style>
    /* 1. Ẩn Footer "Built with Streamlit" */
    footer {display: none !important; visibility: hidden !important;}
    #MainMenu {display: none !important;}
    
    /* 2. Ẩn Nút Deploy & Toolbar bên phải (3 chấm, Fullscreen) */
    .stAppDeployButton {display: none !important;}
    [data-testid="stToolbar"] {display: none !important; visibility: hidden !important;}
    
    /* 3. QUAN TRỌNG: Giữ lại Header nhưng làm trong suốt để hiện nút 3 gạch */
    header[data-testid="stHeader"] {
        background: transparent !important;
        z-index: 1 !important;
    }
    
    /* 4. Tinh chỉnh giao diện Chat */
    .stApp {background-color: #ffffff;}
    
    /* Bong bóng chat */
    div[data-testid="stChatMessage"] {
        background-color: #f1f3f4; 
        border-radius: 20px; 
        padding: 15px; 
        border: none;
        margin-bottom: 10px;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e8f0fe; /* Màu xanh nhạt Google */
        flex-direction: row-reverse; 
        text-align: right;
    }
    
    /* 5. Nút Zalo đẹp */
    .stLinkButton a {
        background-color: #0068ff !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        text-align: center !important;
        border: none !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    
    /* 6. Form đăng nhập đẹp */
    div[data-testid="stForm"] {
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        background: #fafafa;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. CẤU HÌNH API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("⚠️ Lỗi: Chưa cấu hình API Key.")
    st.stop()

# --- 4. CẤU HÌNH ĐƯỜNG DẪN ---
CURRENT_DIR = os.getcwd()
VECTOR_DB_FOLDER = "bo_nao_vector"
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, VECTOR_DB_FOLDER)
USAGE_DB_FILE = "usage_database.json"

DAILY_LIMIT = 15
TRIAL_LIMIT = 5

# --- QUẢN LÝ QUOTA ---
def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

def check_member_limit(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    if username not in data or data[username]["date"] != today:
        data[username] = {"date": today, "count": 0}
        save_usage_db(data)
        return 0, DAILY_LIMIT
    used = data[username]["count"]
    return used, DAILY_LIMIT - used

def increment_member_usage(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    if username in data and data[username]["date"] == today:
        data[username]["count"] += 1
        save_usage_db(data)

# --- XỬ LÝ TỪ KHÓA ---
SPECIAL_MAPPING = {
    "trồng chuối": ["sirsasana", "headstand"],
    "con quạ": ["bakasana", "crow"],
    "cái cày": ["halasana", "plow"],
    "tam giác": ["trikonasana", "triangle"],
    "xác chết": ["savasana", "corpse"],
    "bánh xe": ["chakrasana", "wheel"],
    "chó úp mặt": ["adho mukha svanasana", "downward facing dog"],
    "rắn hổ mang": ["bhujangasana", "cobra"]
}
STOPWORDS = {'là', 'của', 'như', 'thế', 'nào', 'tập', 'bài', 'cách', 'tôi', 'bạn', 'muốn', 'hỏi', 'gì'}

def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    return set([w for w in words if w not in STOPWORDS and len(w) > 1])

# --- 5. LOAD BRAIN ---
@st.cache_resource
def load_brain():
    if not os.path.exists(VECTOR_DB_PATH):
        st.error(f"❌ Lỗi: Không tìm thấy DB."); return None, None
    index_file = os.path.join(VECTOR_DB_PATH, "index.faiss")
    if not os.path.exists(index_file): return None, None
    if os.path.getsize(index_file) < 100000:
        st.error(f"❌ Lỗi: File DB quá nhẹ (Lỗi Git LFS)."); return None, None

    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest') 
        return db, model
    except Exception: return None, None

db, model = load_brain()

def search_engine(query, db):
    query_lower = query.lower()
    user_keywords = clean_and_extract_keywords(query)
    injected_keywords = set()
    for key, values in SPECIAL_MAPPING.items():
        if key in query_lower:
            injected_keywords.update(values)
            user_keywords.update(values)
    if not user_keywords: user_keywords = set(query_lower.split())
    vector_query = f"{query} {' '.join(injected_keywords)}"
    raw_docs = db.similarity_search(vector_query, k=200)
    matched_docs = []
    for d in raw_docs:
        title = d.metadata.get('title', 'No Title')
        content = d.page_content
        title_keywords = clean_and_extract_keywords(title)
        score = 0
        common_words = user_keywords.intersection(title_keywords)
        if len(common_words) > 0: score += len(common_words) * 10
        if score > 0: matched_docs.append((d, score))
    matched_docs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched_docs[:6]]

# --- TRẠNG THÁI PHIÊN ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "guest_usage" not in st.session_state: st.session_state.guest_usage = 0
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Guru đã sẵn sàng."}]

# --- SIDEBAR (VẪN GIỮ ĐỂ LOGOUT/INFO) ---
with st.sidebar:
    st.image(LOGO_URL, width=60)
    st.title("Yoga Guru")
    if st.session_state.authenticated:
        st.success(f"Hi, {st.session_state.username}!")
        if st.button("Đăng xuất"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.info("Chế độ khách.")
    
    st.markdown("---")
    st.link_button("📲 Lấy TK VIP (Zalo)", ZALO_LINK)

# --- LOGIC QUYỀN CHAT ---
can_chat = False
limit_reached_msg = ""

if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0: can_chat = True
    else: limit_reached_msg = "⛔ Bạn đã hết 15 câu hỏi hôm nay."
else:
    if st.session_state.guest_usage < TRIAL_LIMIT: 
        can_chat = True
    else: 
        limit_reached_msg = "🔒 Hết lượt dùng thử."

# --- GIAO DIỆN CHÍNH ---
# 1. Hiển thị Lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 2. Xử lý logic Chat hoặc Đăng nhập
if can_chat:
    if prompt := st.chat_input("Hỏi Guru về Yoga..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            if db is None: st.error("Lỗi hệ thống."); st.stop()
            msg_placeholder = st.empty()
            msg_placeholder.markdown("🧘 *Guru đang nghĩ...*")
            
            try:
                top_docs = search_engine(prompt, db)
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1

                if not top_docs:
                    resp = "Guru chưa tìm thấy thông tin phù hợp."
                    msg_placeholder.markdown(resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})
                else:
                    context = ""
                    for i, d in enumerate(top_docs):
                        context += f"Nội dung: {d.page_content}\n\n"
                    
                    sys_prompt = f"""
                    Bạn là Yoga Guru. Dữ liệu: {context}
                    Câu hỏi: "{prompt}"
                    Yêu cầu: Trả lời ngắn gọn (8-10 ý), ~200 từ, không link.
                    """
                    response = model.generate_content(sys_prompt)
                    msg_placeholder.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    st.rerun()
            except Exception as e: st.error(f"Lỗi: {e}")

else:
    # --- KHI HẾT LƯỢT: HIỆN FORM ĐĂNG NHẬP NGAY GIỮA MÀN HÌNH ---
    st.divider()
    st.warning(limit_reached_msg)
    
    if not st.session_state.authenticated:
        st.markdown("### 🔐 Đăng nhập để tiếp tục")
        with st.form("login_form_main"):
            col1, col2 = st.columns(2)
            with col1: user_input = st.text_input("Tài khoản")
            with col2: pass_input = st.text_input("Mật khẩu", type="password")
            
            if st.form_submit_button("Đăng nhập ngay", use_container_width=True):
                secrets_pass = st.secrets["passwords"].get(user_input)
                if secrets_pass and secrets_pass == pass_input:
                    st.session_state.authenticated = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Sai thông tin đăng nhập!")
        
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'><a href='{ZALO_LINK}' target='_blank' style='color: #0068ff; text-decoration: none; font-weight: bold;'>Chưa có tài khoản? Nhắn Zalo lấy ngay 👉</a></div>", unsafe_allow_html=True)
