import streamlit as st

# =====================================================
# 1. PAGE CONFIG – BẮT BUỘC LÀ LỆNH STREAMLIT ĐẦU TIÊN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. CSS – CHỈ CSS, KHÔNG PHÁ LAYOUT
# =====================================================
st.markdown("""
<style>
html, body {
    background: #ffffff !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.stApp {
    background: #ffffff !important;
}

[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}

/* CHAT UI */
div[data-testid="stChatMessage"] {
    background: #f8f9fa;
    border-radius: 14px;
    padding: 12px;
    margin-top: 22px;
    border: 1px solid #eee;
}

div[data-testid="stChatMessage"][data-test-role="user"] {
    background-color: #e3f2fd;
    flex-direction: row-reverse;
    text-align: right;
    border: none;
}

/* LINK */
.stMarkdown a {
    color: #0f988b;
    font-weight: 600;
    text-decoration: none;
}
.stMarkdown a:hover {
    text-decoration: underline;
}

/* FONT */
* {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. IMPORT KHÁC
# =====================================================
import gdown
import zipfile
import os, re, json, datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 4. API KEY
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("❌ Thiếu GOOGLE_API_KEY")
    st.stop()

# =====================================================
# 5. CONSTANT
# =====================================================
VECTOR_DB_PATH = "bo_nao_vector"
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

# =====================================================
# 6. USAGE DATABASE
# =====================================================

def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE):
        return {}
    with open(USAGE_DB_FILE, "r") as f:
        return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w") as f:
        json.dump(data, f)

def check_member_limit(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    if username not in data or data[username]["date"] != today:
        data[username] = {"date": today, "count": 0}
        save_usage_db(data)
        return 0, DAILY_LIMIT
    return data[username]["count"], DAILY_LIMIT - data[username]["count"]

def increment_member_usage(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    if username in data and data[username]["date"] == today:
        data[username]["count"] += 1
        save_usage_db(data)

# =====================================================
# 7. SEARCH ENGINE
# =====================================================
SPECIAL_MAPPING = {
    "trồng chuối": ["sirsasana"],
    "con quạ": ["bakasana"],
    "cái cày": ["halasana"]
}
STOPWORDS = {'là','của','như','thế','nào','tập','bài','cách','tôi','bạn','muốn','hỏi','gì'}

def clean_and_extract_keywords(text):
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return {w for w in text.split() if w not in STOPWORDS and len(w) > 1}

@st.cache_resource
def load_brain():
    # 1. Nếu chưa có não bộ ở /tmp/ thì tải về
    if not os.path.exists(EXTRACT_PATH):
        with st.spinner("🚀 Đang tải bộ não Yoga từ Cloud... Đợi em tí nhé!"):
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall("/tmp/")
    
    # 2. Load não bộ từ đường dẫn mới
    if not os.path.exists(EXTRACT_PATH):
        return None, None
        
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except Exception as e:
        st.error(f"Lỗi load não: {e}")
        return None, None

# Lúc gọi dùng biến db, model bình thường
db, model = load_brain()

def search_engine(query, db):
    user_keywords = clean_and_extract_keywords(query)
    injected = []
    for k,v in SPECIAL_MAPPING.items():
        if k in query.lower():
            injected += v
    docs = db.similarity_search(query + " " + " ".join(injected), k=50)
    results, seen = [], set()
    for d in docs:
        title = d.metadata.get("title","")
        if title in seen: continue
        score = len(user_keywords & clean_and_extract_keywords(title))
        if score:
            results.append(d)
            seen.add(title)
    return results[:3]

# =====================================================
# 8. SESSION STATE
# =====================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "guest_usage" not in st.session_state:
    st.session_state.guest_usage = 0
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role":"assistant",
        "content":"Namaste! 🙏 Bạn muốn hỏi điều gì hôm nay?"
    }]

# =====================================================
# 9. CHAT LIMIT
# =====================================================
can_chat = False
if st.session_state.authenticated:
    _, remain = check_member_limit(st.session_state.username)
    can_chat = remain > 0
else:
    can_chat = st.session_state.guest_usage < TRIAL_LIMIT

# =====================================================
# 10. RENDER CHAT
# =====================================================
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# =====================================================
# 11. CHAT LOGIC
# =====================================================
if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not db:
                st.error("❌ Chưa nạp được dữ liệu")
            else:
                docs = search_engine(prompt, db)
                context = "\n".join([d.page_content for d in docs])
                links = {}
                for d in docs:
                    if "url" in d.metadata:
                        links[d.metadata["url"]] = d.metadata.get("title","Tài liệu")

                sys_prompt = f"""
Bạn là chuyên gia Yoga.
DỮ LIỆU:
{context}
CÂU HỎI: {prompt}
 YÊU CẦU:
                1. Trả lời CỰC KỲ NGẮN GỌN (Tối đa 5-6 gạch đầu dòng).
                2. Tổng độ dài KHÔNG QUÁ 100 TỪ.
                3. Đi thẳng vào trọng tâm, bỏ qua lời dẫn dắt vô nghĩa.
                4. Giọng văn thân thiện, dứt khoát.
                5. KHÔNG tự chèn link (Hệ thống sẽ tự làm).
                """

                res = model.generate_content(sys_prompt).text
                if st.session_state.authenticated:
                    increment_member_usage(st.session_state.username)
                else:
                    st.session_state.guest_usage += 1

                if links:
                    res += "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                    for u,t in links.items():
                        res += f"- 🔗 [{t}]({u})\n"

                st.markdown(res, unsafe_allow_html=True)
                st.session_state.messages.append({"role":"assistant","content":res})

# =====================================================
# 12. LOGIN + ZALO (GIỮ NGUYÊN)
# =====================================================
else:
    st.markdown("---")
    with st.form("login"):
        st.markdown("### 🔐 Đăng nhập Thành viên")
        u = st.text_input("User")
        p = st.text_input("Pass", type="password")
        if st.form_submit_button("Vào tập"):
            if st.secrets["passwords"].get(u) == p:
                st.session_state.authenticated = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("Sai thông tin")

    st.markdown(
        "<div style='text-align:center;margin-top:10px'>"
        "<a href='https://zalo.me/84963759566' target='_blank' "
        "style='color:#0f988b;font-weight:600'>💬 Lấy TK Zalo</a>"
        "</div>",
        unsafe_allow_html=True
    )
