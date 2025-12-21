import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Yoga Assistant", 
    page_icon="🧘", 
    layout="wide", 
    initial_sidebar_state="collapsed",
    menu_items=None
)

# --- CSS ẨN THANH CÔNG CỤ & FOOTER ---
st.markdown("""
<style>

/* ===== RESET TOÀN BỘ NỀN ===== */
html, body {
    background: #ffffff !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.stApp {
    background-color: #ffffff !important;
    opacity: 1 !important;
}

/* ===== ẨN TOOLBAR AN TOÀN (KHÔNG PHÁ LAYOUT) ===== */
[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}

/* KHÔNG hide header/footer bằng display:none */
header, footer {
    visibility: hidden;
    height: 0;
}

/* ===== FIX MOBILE TEXT MỜ ===== */
* {
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
}

iframe {
    background: #ffffff !important;
}

/* ===== CHAT UI ===== */
div[data-testid="stChatMessage"] {
    background-color: #f8f9fa;
    border-radius: 14px;
    padding: 12px;
    margin-top: 24px;
    border: 1px solid #eee;
}

div[data-testid="stChatMessage"][data-test-role="user"] {
    background-color: #e3f2fd;
    flex-direction: row-reverse;
    text-align: right;
    border: none;
}

/* ===== LINK ===== */
.stMarkdown a {
    color: #6c5ce7 !important;
    font-weight: 600;
    text-decoration: none;
}
.stMarkdown a:hover {
    text-decoration: underline;
}

/* ===== MOBILE FIX ===== */
@media (max-width: 600px) {
    body {
        overflow: auto !important;
    }
}

</style>
""", unsafe_allow_html=True)


# --- KHỞI TẠO API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except: st.stop()

CURRENT_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, "bo_nao_vector")
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

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
    return data[username]["count"], DAILY_LIMIT - data[username]["count"]
def increment_member_usage(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    if username in data and data[username]["date"] == today:
        data[username]["count"] += 1
        save_usage_db(data)

SPECIAL_MAPPING = {"trồng chuối": ["sirsasana"], "con quạ": ["bakasana"], "cái cày": ["halasana"]}
STOPWORDS = {'là', 'của', 'như', 'thế', 'nào', 'tập', 'bài', 'cách', 'tôi', 'bạn', 'muốn', 'hỏi', 'gì'}
def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return set([w for w in text.split() if w not in STOPWORDS and len(w) > 1])

@st.cache_resource
def load_brain():
    if not os.path.exists(VECTOR_DB_PATH): return None, None
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest') 
        return db, model
    except: return None, None

db, model = load_brain()

def search_engine(query, db):
    user_keywords = clean_and_extract_keywords(query)
    injected_keywords = set()
    for key, values in SPECIAL_MAPPING.items():
        if key in query.lower(): injected_keywords.update(values)
    if not user_keywords: user_keywords = set(query.lower().split())
    
    raw_docs = db.similarity_search(f"{query} {' '.join(injected_keywords)}", k=100)
    matched_docs = []
    seen = set()
    for d in raw_docs:
        title = d.metadata.get('title', 'Tài liệu Yoga')
        if title in seen: continue
        score = 0
        title_keywords = clean_and_extract_keywords(title)
        common = user_keywords.intersection(title_keywords)
        if common: score += len(common) * 10
        if score > 0: 
            matched_docs.append((d, score))
            seen.add(title)
    matched_docs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched_docs[:3]]

# --- LOGIC CHAT ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "guest_usage" not in st.session_state: st.session_state.guest_usage = 0
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Chúc bạn một ngày nhiều niềm vui, chúng ta sẽ bắt đầu từ đâu?."}]

can_chat = False
if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0: can_chat = True
    else: st.warning("⛔ Hôm nay bạn đã hỏi đủ 25 câu.")
else:
    if st.session_state.guest_usage < TRIAL_LIMIT: can_chat = True
    else: st.info(f"🔒 Dùng thử: {st.session_state.guest_usage}/{TRIAL_LIMIT} câu.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if db:
                top_docs = search_engine(prompt, db)
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1
                
                # --- PHẦN KHÔI PHỤC LOGIC LINK ĐẸP ---
                links_markdown = ""
                context = ""
                final_links = {} # Dùng dict để lọc trùng lặp link
                
                if top_docs:
                    context = "\n".join([d.page_content for d in top_docs])
                    
                    for d in top_docs:
                        title = d.metadata.get('title', 'Tài liệu tham khảo')
                        url = d.metadata.get('url', '#')
                        # Làm sạch tiêu đề (bỏ dấu ngoặc thừa nếu có)
                        clean_title = title.replace("[", "").replace("]", "").replace("(", " - ").replace(")", "")
                        
                        if url != '#' and "http" in url:
                            final_links[url] = clean_title

                    # Tạo Markdown list
                    if final_links:
                        links_markdown = "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                        for url, name in final_links.items():
                            links_markdown += f"- 🔗 [{name}]({url})\n"
                
                sys_prompt = f"""
                Bạn là chuyên gia Yoga.
                DỮ LIỆU BÀI VIẾT:
                {context}
                CÂU HỎI: "{prompt}"
                YÊU CẦU:
                1. Trả lời CỰC KỲ NGẮN GỌN (Tối đa 5-6 gạch đầu dòng).
                2. Tổng độ dài KHÔNG QUÁ 100 TỪ.
                3. Đi thẳng vào trọng tâm, bỏ qua lời dẫn dắt vô nghĩa.
                4. Giọng văn thân thiện, dứt khoát.
                5. KHÔNG tự chèn link (Hệ thống sẽ tự làm).
                """
                
                try:
                    response_text = model.generate_content(sys_prompt).text
                    final_content = response_text + links_markdown
                    st.markdown(final_content, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": final_content})
                except Exception as e:
                    st.error(f"Lỗi AI: {e}")
            else: st.error("Đang kết nối não bộ...")
else:
    if not st.session_state.authenticated:
        st.markdown("---")
        with st.form("login"):
            st.markdown("### 🔐 Đăng nhập Thành viên")
            u = st.text_input("User")
            p = st.text_input("Pass", type="password")
            if st.form_submit_button("Vào tập"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai thông tin!")
        st.markdown(f"<div style='text-align:center; margin-top:10px'><a href='https://zalo.me/84963759566' target='_blank' style='color:#6c5ce7; text-decoration:none; font-weight:bold'>💬 Lấy TK Zalo</a></div>", unsafe_allow_html=True)
