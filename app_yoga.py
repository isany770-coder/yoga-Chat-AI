import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- CẤU HÌNH CƠ BẢN ---
st.set_page_config(page_title="Yoga Guru", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

# --- CSS "DỌN RÁC" TRIỆT ĐỂ (FIX LỖI TRẮNG MÀN HÌNH) ---
st.markdown("""
<style>
    /* 1. Ẩn thanh công cụ Streamlit (3 chấm, Fullscreen) */
    [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    .stAppDeployButton {display: none !important;}
    
    /* 2. Ẩn Footer "Built with Streamlit" */
    footer {visibility: hidden !important; display: none !important;}
    #MainMenu {visibility: hidden !important; display: none !important;}
    
    /* 3. Ẩn Header mặc định nhưng giữ khoảng cách để không bị dính lên trên */
    header[data-testid="stHeader"] {background: transparent !important;}
    
    /* 4. Tinh chỉnh Chat cho đẹp */
    .stApp {background-color: #ffffff;}
    div[data-testid="stChatMessage"] {
        background-color: #f0f2f6; border-radius: 15px; padding: 10px; margin-bottom: 10px;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e8f0fe; flex-direction: row-reverse; text-align: right;
    }
    
    /* 5. Ẩn Avatar mặc định cho gọn */
    .stChatMessage .st-emotion-cache-1p1m4ay {display: none;}
</style>
""", unsafe_allow_html=True)

# --- CẤU HÌNH API & DATABASE (GIỮ NGUYÊN) ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except: st.stop()

CURRENT_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, "bo_nao_vector")
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 15
TRIAL_LIMIT = 5

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
    for d in raw_docs:
        score = 0
        title_keywords = clean_and_extract_keywords(d.metadata.get('title', ''))
        common = user_keywords.intersection(title_keywords)
        if common: score += len(common) * 10
        if score > 0: matched_docs.append((d, score))
    matched_docs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched_docs[:4]] # Lấy ít thôi cho nhanh

# --- LOGIC CHÍNH ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "guest_usage" not in st.session_state: st.session_state.guest_usage = 0
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Guru đây."}]

# --- GIAO DIỆN (BỎ SIDEBAR, DỒN HẾT VÀO GIỮA CHO MOBILE) ---
can_chat = False
if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0: can_chat = True
    else: st.warning("⛔ Hôm nay bạn đã hỏi đủ 15 câu.")
else:
    if st.session_state.guest_usage < TRIAL_LIMIT: can_chat = True
    else: st.info("🔒 Hết lượt dùng thử.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if db:
                top_docs = search_engine(prompt, db)
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1
                
                context = "\n".join([d.page_content for d in top_docs]) if top_docs else ""
                response = model.generate_content(f"Bạn là Yoga Guru. Dữ liệu: {context}. Câu hỏi: {prompt}. Trả lời ngắn gọn 5 ý chính. Không link.").text
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                st.error("Lỗi DB.")
else:
    # FORM ĐĂNG NHẬP (HIỆN KHI HẾT LƯỢT)
    if not st.session_state.authenticated:
        with st.form("login"):
            u = st.text_input("User")
            p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai!")
