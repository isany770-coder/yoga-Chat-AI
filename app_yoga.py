import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- CẤU HÌNH LOGO (THAY LINK ẢNH CỦA BÁC VÀO ĐÂY) ---
LOGO_URL = "https://yogaismylife.vn/wp-content/uploads/2025/02/png-lo-final.webp" 
ZALO_LINK = "https://zalo.me/84963759566"

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Yoga Guru AI",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. GIAO DIỆN CSS ---
st.markdown("""
<style>
    .stApp {background-color: #f8f9fa;}
    div[data-testid="stChatMessage"] {
        background-color: #ffffff; border-radius: 15px; padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd; flex-direction: row-reverse; text-align: right;
    }
    section[data-testid="stSidebar"] {background-color: #ffffff; border-right: 1px solid #ddd;}
    .stMarkdown a {color: #ff6b6b !important; font-weight: bold;}
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    
    /* Style cho nút Zalo */
    .stLinkButton a {
        background-color: #0068ff !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        text-align: center !important;
        border: none !important;
    }
    .stLinkButton a:hover {
        background-color: #0056d6 !important;
    }
    /* Ẩn hoàn toàn Header và Hamburger Menu (3 gạch) */
    header[data-testid="stHeader"] {
        display: none;
    }
    
    /* Ẩn nút "Deploy" và các nút quản lý khác */
    .stAppDeployButton {
        display: none;
    }

    /* Ẩn footer "Made with Streamlit" */
    footer {
        visibility: hidden;
    }
    
    /* Đẩy nội dung lên cao vì đã mất Header */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. CẤU HÌNH API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("⚠️ Lỗi: Chưa cấu hình API Key trong Secrets.")
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
    "trồng chuối": ["sirsasana", "headstand", "đứng bằng đầu"],
    "con quạ": ["bakasana", "crow"],
    "cái cày": ["halasana", "plow"],
    "tam giác": ["trikonasana", "triangle"],
    "xác chết": ["savasana", "corpse"],
    "bánh xe": ["chakrasana", "wheel"],
    "chó úp mặt": ["adho mukha svanasana", "downward facing dog"],
    "rắn hổ mang": ["bhujangasana", "cobra"]
}
STOPWORDS = {'là', 'của', 'những', 'cái', 'việc', 'trong', 'khi', 'bị', 'với', 'cho', 'được', 'tại', 'vì', 'sao', 'thì', 'lại', 'mà', 'và', 'các', 'có', 'như', 'để', 'này', 'đó', 'về', 'theo', 'nhất', 'gì', 'thế', 'nào', 'làm', 'tập', 'bài', 'cách', 'như', 'thế', 'nào', 'tôi', 'bạn', 'muốn', 'hỏi'}

def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    return set([w for w in words if w not in STOPWORDS and len(w) > 1])

# --- 5. LOAD BRAIN ---
@st.cache_resource
def load_brain():
    if not os.path.exists(VECTOR_DB_PATH):
        st.error(f"❌ Lỗi: Không tìm thấy thư mục '{VECTOR_DB_FOLDER}'.")
        return None, None
    index_file = os.path.join(VECTOR_DB_PATH, "index.faiss")
    if not os.path.exists(index_file):
        st.error(f"❌ Lỗi: Thiếu file index.faiss")
        return None, None
    if os.path.getsize(index_file) < 100000:
        st.error(f"❌ Lỗi: File dữ liệu quá nhẹ (Lỗi Git LFS).")
        return None, None

    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest') 
        return db, model
    except Exception as e:
        st.error(f"❌ Lỗi nạp DB: {e}")
        return None, None

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
        if len(common_words) > 0:
            score += len(common_words) * 10
            for inj in injected_keywords:
                if inj in title.lower(): score += 500
            match_ratio = len(common_words) / len(user_keywords) if len(user_keywords) > 0 else 0
            if match_ratio >= 0.5: score += 50
        if score == 0:
            content_keywords = clean_and_extract_keywords(content[:500])
            common_content = user_keywords.intersection(content_keywords)
            if len(common_content) > 0: score += len(common_content)
        if score > 0: matched_docs.append((d, score))
    matched_docs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched_docs[:6]]

# --- TRẠNG THÁI PHIÊN ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "guest_usage" not in st.session_state: st.session_state.guest_usage = 0
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Guru đã sẵn sàng."}]

# --- SIDEBAR ---
with st.sidebar:
    # 1. LOGO
    st.image(LOGO_URL, width=80) 
    st.title("Yoga Guru AI")
    st.markdown("---")
    
    # 2. TRẠNG THÁI NGƯỜI DÙNG
    if st.session_state.authenticated:
        st.success(f"👋 Xin chào, **{st.session_state.username}**!")
        used, remaining = check_member_limit(st.session_state.username)
        st.progress(used / DAILY_LIMIT)
        st.caption(f"Đã dùng: {used}/{DAILY_LIMIT} câu")
        if st.button("🚪 Đăng xuất", type="secondary"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.info("🌱 Chế độ: **Dùng thử**")
        st.metric(label="Câu hỏi còn lại", value=f"{TRIAL_LIMIT - st.session_state.guest_usage}", delta=None)
        
        # Form đăng nhập
        with st.expander("🔐 Đăng nhập Thành viên"):
             with st.form("login_form"):
                user_input = st.text_input("Tài khoản")
                pass_input = st.text_input("Mật khẩu", type="password")
                if st.form_submit_button("Đăng nhập"):
                    secrets_pass = st.secrets["passwords"].get(user_input)
                    if secrets_pass and secrets_pass == pass_input:
                        st.session_state.authenticated = True
                        st.session_state.username = user_input
                        st.rerun()
                    else: st.error("Sai thông tin!")

    st.markdown("---")
    
    # 3. NÚT ZALO LẤY TÀI KHOẢN (MỚI)
    st.markdown("### 💬 Cần tài khoản VIP?")
    st.link_button("📲 Nhắn Zalo lấy TK ngay", ZALO_LINK)
    
    st.caption("© 2024 Yoga Guru AI")

# --- GIAO DIỆN CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- XỬ LÝ CHAT ---
can_chat = False
if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0: can_chat = True
else:
    if st.session_state.guest_usage < TRIAL_LIMIT: can_chat = True

if can_chat:
    if prompt := st.chat_input("VD: Đau lưng tập gì? Kỹ thuật con quạ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            if db is None:
                st.error("❌ Hệ thống đang khởi động. Vui lòng thử lại sau giây lát.")
                st.stop()
            
            msg_placeholder = st.empty()
            msg_placeholder.markdown("🧘 *Guru đang suy ngẫm...*")
            
            try:
                top_docs = search_engine(prompt, db)
                
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1

                if not top_docs:
                    resp = "Guru chưa tìm thấy bài viết phù hợp."
                    msg_placeholder.markdown(resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})
                else:
                    context = ""
                    links = {}
                    for i, d in enumerate(top_docs):
                        title = d.metadata.get('title', 'No Title')
                        url = d.metadata.get('url', '#')
                        context += f"[BÀI {i+1}]: {title}\nNội dung: {d.page_content}\n\n"
                        if url != '#' and "http" in url and url not in links:
                             clean = title.replace("[", "").replace("]", "").replace("(", " - ").replace(")", "")
                             links[url] = clean
                    
                    link_md = ""
                    if links:
                        link_md = "\n\n---\n**📚 Tham khảo:**\n" + "\n".join([f"- [{n}]({u})" for u, n in links.items()])

                    sys_prompt = f"""
                    Bạn là Yoga Guru chuyên nghiệp.
                    Dữ liệu: {context}
                    Câu hỏi: "{prompt}"
                    Yêu cầu:
                    1. Trả lời bằng gạch đầu dòng (8-10 ý).
                    2. Độ dài ~200 từ.
                    3. Văn phong chuyên gia, ngắn gọn.
                    4. KHÔNG tự viết link.
                    """
                    
                    response = model.generate_content(sys_prompt)
                    full_resp = response.text + link_md
                    msg_placeholder.markdown(full_resp)
                    st.session_state.messages.append({"role": "assistant", "content": full_resp})
                    st.rerun()

            except Exception as e: 
                st.error(f"Lỗi: {e}"); print(e)
else:
    if st.session_state.authenticated:
        st.info("⛔ Hết lượt hôm nay.")
    else:
        st.warning(f"🔒 Hết lượt dùng thử. Vui lòng Đăng nhập hoặc bấm nút **Lấy TK Zalo** bên dưới.")
