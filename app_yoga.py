# ==============================
# IMPORT – KHÔNG STREAMLIT TRƯỚC
# ==============================
import os
import re
import json
import datetime

import streamlit as st
import google.generativeai as genai

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS


# ==============================
# PAGE CONFIG – BẮT BUỘC ĐẦU TIÊN
# ==============================
st.set_page_config(
    page_title="Yoga Assistant",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ==============================
# CSS – SAFE, KHÔNG CRASH, KHÔNG XUYÊN
# ==============================
st.markdown("""
<style>

/* ===== RESET NỀN TUYỆT ĐỐI ===== */
html, body {
    background: #ffffff !important;
}

/* ROOT STREAMLIT */
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.stApp {
    background-color: #ffffff !important;
}

/* ẨN TOOLBAR AN TOÀN */
[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}

/* ===== FONT & RENDER ===== */
* {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* ===== CHAT MESSAGE ===== */
div[data-testid="stChatMessage"] {
    background-color: #f8f9fa;
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

/* ===== LINK ===== */
.stMarkdown a {
    color: #0f988b !important;
    font-weight: 600;
    text-decoration: none;
}
.stMarkdown a:hover {
    text-decoration: underline;
}

</style>
""", unsafe_allow_html=True)


# ==============================
# API CONFIG
# ==============================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("❌ Không tìm thấy GOOGLE_API_KEY trong secrets")
    st.stop()


# ==============================
# CONSTANTS
# ==============================
CURRENT_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, "bo_nao_vector")
USAGE_DB_FILE = "usage_database.json"

DAILY_LIMIT = 25
TRIAL_LIMIT = 10


# ==============================
# USAGE DB
# ==============================
def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE):
        return {}
    with open(USAGE_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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


# ==============================
# SEARCH ENGINE
# ==============================
SPECIAL_MAPPING = {
    "trồng chuối": ["sirsasana"],
    "con quạ": ["bakasana"],
    "cái cày": ["halasana"]
}

STOPWORDS = {
    "là", "của", "như", "thế", "nào",
    "tập", "bài", "cách", "tôi", "bạn",
    "muốn", "hỏi", "gì"
}

def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return {w for w in text.split() if w not in STOPWORDS and len(w) > 1}


@st.cache_resource(show_spinner=False)
def load_brain():
    if not os.path.exists(VECTOR_DB_PATH):
        return None, None

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=api_key
    )

    try:
        db = FAISS.load_local(
            VECTOR_DB_PATH,
            embeddings,
            allow_dangerous_deserialization=True
        )
        model = genai.GenerativeModel("gemini-flash-latest")
        return db, model
    except Exception:
        return None, None


db, model = load_brain()


def search_engine(query, db):
    user_keywords = clean_and_extract_keywords(query)
    injected = set()

    for key, values in SPECIAL_MAPPING.items():
        if key in query.lower():
            injected.update(values)

    if not user_keywords:
        user_keywords = set(query.lower().split())

    raw_docs = db.similarity_search(
        f"{query} {' '.join(injected)}",
        k=100
    )

    matched = []
    seen = set()

    for d in raw_docs:
        title = d.metadata.get("title", "Tài liệu Yoga")
        if title in seen:
            continue

        title_keywords = clean_and_extract_keywords(title)
        common = user_keywords.intersection(title_keywords)

        if common:
            matched.append((d, len(common) * 10))
            seen.add(title)

    matched.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched[:3]]


# ==============================
# SESSION STATE
# ==============================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "guest_usage" not in st.session_state:
    st.session_state.guest_usage = 0

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Namaste! 🙏 Chúc bạn một ngày nhiều niềm vui, bạn muốn hỏi điều gì về Yoga?"
    }]


# ==============================
# CHAT PERMISSION
# ==============================
can_chat = False

if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0:
        can_chat = True
    else:
        st.warning("⛔ Hôm nay bạn đã hỏi đủ 25 câu.")
else:
    if st.session_state.guest_usage < TRIAL_LIMIT:
        can_chat = True
    else:
        st.info(f"🔒 Dùng thử: {st.session_state.guest_usage}/{TRIAL_LIMIT} câu.")


# ==============================
# RENDER CHAT
# ==============================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)


# ==============================
# INPUT & RESPONSE
# ==============================
if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not db or not model:
                st.error("🧠 Đang kết nối não bộ, vui lòng thử lại sau.")
            else:
                top_docs = search_engine(prompt, db)

                if st.session_state.authenticated:
                    increment_member_usage(st.session_state.username)
                else:
                    st.session_state.guest_usage += 1

                context = ""
                links_markdown = ""
                final_links = {}

                if top_docs:
                    context = "\n".join(d.page_content for d in top_docs)

                    for d in top_docs:
                        title = d.metadata.get("title", "Tài liệu tham khảo")
                        url = d.metadata.get("url", "")

                        clean_title = (
                            title.replace("[", "")
                            .replace("]", "")
                            .replace("(", " - ")
                            .replace(")", "")
                        )

                        if url.startswith("http"):
                            final_links[url] = clean_title

                    if final_links:
                        links_markdown = "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                        for url, name in final_links.items():
                            links_markdown += f"- 🔗 [{name}]({url})\n"

                sys_prompt = f"""
Bạn là chuyên gia Yoga.

DỮ LIỆU:
{context}

CÂU HỎI: "{prompt}"

YÊU CẦU:
- Trả lời tối đa 5–6 gạch đầu dòng
- Không quá 100 từ
- Đi thẳng trọng tâm
- Giọng thân thiện, dứt khoát
- KHÔNG tự chèn link
"""

                try:
                    response = model.generate_content(sys_prompt).text
                    final_content = response + links_markdown
                    st.markdown(final_content, unsafe_allow_html=True)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": final_content
                    })
                except Exception as e:
                    st.error(f"❌ Lỗi AI: {e}")


# ==============================
# LOGIN
# ==============================
if not can_chat and not st.session_state.authenticated:
    st.markdown("---")

    with st.form("login"):
        st.markdown("### 🔐 Đăng nhập Thành viên")
        u = st.text_input("User")
        p = st.text_input("Pass", type="password")

        if st.form_submit_button("Vào tập"):
            if st.secrets.get("passwords", {}).get(u) == p:
                st.session_state.authenticated = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("Sai thông tin đăng nhập")

    st.markdown(
        "<div style='text-align:center;margin-top:10px'>"
        "<a href='https://zalo.me/84963759566' target='_blank' "
        "style='color:#0f988b;font-weight:600;text-decoration:none'>"
        "💬 Lấy tài khoản Zalo</a></div>",
        unsafe_allow_html=True
    )
