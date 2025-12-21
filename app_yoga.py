import streamlit as st
import os
import re
import json
import datetime
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
import extra_streamlit_components as stx

# --- 1. CẤU HÌNH TRANG & CSS (KHÔI PHỤC CHUẨN GIAO DIỆN ẢNH) ---
st.set_page_config(
    page_title="Yoga Assistant", 
    page_icon="🧘", 
    layout="wide", 
    initial_sidebar_state="collapsed",
    menu_items=None
)

st.markdown("""
<style>
    /* 1. Ẩn các thành phần thừa */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 2. Căn chỉnh container chính */
    .block-container {
        padding-top: 1rem !important;
        max-width: 800px !important;
    }
    
    /* 3. Style tin nhắn chuẩn như ảnh */
    .stApp {background-color: white;}
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa !important; 
        border-radius: 15px !important; 
        padding: 16px !important; 
        margin-top: 20px !important;
        border: 1px solid #eee !important;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #ffffff !important; 
        border: 1px solid #e0e0e0 !important;
    }

    /* 4. Link tham khảo màu tím chuẩn */
    .stMarkdown a {
        color: #6c5ce7 !important; 
        font-weight: 600 !important; 
        text-decoration: none !important;
    }
    .stMarkdown a:hover { text-decoration: underline !important; }

    /* 5. Paywall Card chuyên nghiệp */
    .paywall-container {
        border: 2px solid #6c5ce7;
        background-color: #f3f0ff;
        border-radius: 20px;
        padding: 30px;
        text-align: center;
        margin-top: 30px;
        box-shadow: 0 4px 15px rgba(108, 92, 231, 0.1);
    }
    .btn-zalo {
        display: inline-block;
        background-color: #6c5ce7;
        color: white !important;
        padding: 10px 25px;
        border-radius: 50px;
        font-weight: bold;
        text-decoration: none !important;
        margin-top: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. QUẢN LÝ COOKIE & GIỚI HẠN ---
@st.cache_resource(experimental_allow_widgets=True)
def get_manager(): return stx.CookieManager()

cookie_manager = get_manager()
DAILY_LIMIT = 25
TRIAL_LIMIT = 10
USAGE_DB_FILE = "usage_database.json"

def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

def get_guest_usage():
    val = cookie_manager.get("yoga_guest_usage")
    today = str(datetime.date.today())
    if val:
        try:
            data = json.loads(val)
            if data.get("date") == today: return data.get("count", 0)
        except: pass
    return 0

def increment_guest_usage():
    current = get_guest_usage()
    today = str(datetime.date.today())
    cookie_manager.set("yoga_guest_usage", json.dumps({"date": today, "count": current + 1}), 
                       expires_at=datetime.datetime.now() + datetime.timedelta(days=1))
    time.sleep(0.1) # Đợi cookie ghi file

# --- 3. KHỞI TẠO API & NÃO BỘ ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except: st.stop()

@st.cache_resource
def load_brain():
    path = "bo_nao_vector"
    if not os.path.exists(path): return None, None
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    db = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    model = genai.GenerativeModel('gemini-flash-latest') 
    return db, model

db, model = load_brain()

# --- 4. ENGINE TÌM KIẾM ---
SPECIAL_MAPPING = {"trồng chuối": ["sirsasana"], "con quạ": ["bakasana"], "cái cày": ["halasana"]}
STOPWORDS = {'là', 'của', 'như', 'thế', 'nào', 'tập', 'bài', 'cách', 'tôi', 'bạn', 'muốn', 'hỏi', 'gì'}

def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return set([w for w in text.split() if w not in STOPWORDS and len(w) > 1])

def search_engine(query, db):
    user_keywords = clean_and_extract_keywords(query)
    injected = []
    for k, v in SPECIAL_MAPPING.items():
        if k in query.lower(): injected.extend(v)
    
    raw_docs = db.similarity_search(f"{query} {' '.join(injected)}", k=50)
    matched = []
    seen = set()
    for d in raw_docs:
        title = d.metadata.get('title', 'Tài liệu')
        if title in seen: continue
        score = 0
        title_keywords = clean_and_extract_keywords(title)
        common = user_keywords.intersection(title_keywords)
        if common: score += len(common) * 10
        if score > 0:
            matched.append((d, score))
            seen.add(title)
    matched.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched[:3]]

# --- 5. LOGIC CHAT & PAYWALL ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Chúc bạn một ngày nhiều niềm vui, chúng ta sẽ bắt đầu từ đâu?"}]

# Kiểm tra lượt dùng
guest_count = get_guest_usage()
can_chat = False

if st.session_state.authenticated:
    can_chat = True # Thành viên không giới hạn trong phiên này (hoặc check file json của bạn)
else:
    if guest_count < TRIAL_LIMIT:
        can_chat = True
    else:
        can_chat = False

# Render lịch sử
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# Xử lý Chat
if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if db:
                if not st.session_state.authenticated:
                    increment_guest_usage()
                
                top_docs = search_engine(prompt, db)
                context = "\n".join([d.page_content for d in top_docs]) if top_docs else ""
                
                # Tạo link đẹp chuẩn tím
                links_md = ""
                final_links = {d.metadata.get('url'): d.metadata.get('title') for d in top_docs if d.metadata.get('url', '#') != '#'}
                if final_links:
                    links_md = "\n\n---\n📚 **Tài liệu tham khảo:**\n"
                    for url, title in final_links.items():
                        clean_t = title.replace("[", "").replace("]", "").split("(")[0]
                        links_md += f"- 🔗 [{clean_t}]({url})\n"
                
                sys_prompt = f"Bạn là chuyên gia Yoga. Trả lời CỰC KỲ NGẮN GỌN (max 6 ý, <100 từ). Dữ liệu: {context}\nCâu hỏi: {prompt}"
                
                try:
                    ai_resp = model.generate_content(sys_prompt).text
                    full_content = ai_resp + links_md
                    st.markdown(full_content, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": full_content})
                except: st.error("AI đang bận, thử lại sau nhé!")
            else: st.error("Não bộ chưa sẵn sàng.")
else:
    # HIỂN THỊ CỬA CHẶN (PAYWALL) KHI HẾT LƯỢT
    st.markdown(f"""
    <div class="paywall-container">
        <h2 style="color:#6c5ce7">🧘‍♀️ Bạn đã hoàn thành bài tập trải nghiệm!</h2>
        <p>Bạn đã sử dụng hết <b>{TRIAL_LIMIT}/{TRIAL_LIMIT}</b> lượt hỏi miễn phí hôm nay.<br>
        Để tiếp tục hành trình Yoga không giới hạn cùng AI chuyên gia, hãy trở thành thành viên ngay.</p>
        <a href="https://zalo.me/84963759566" target="_blank" class="btn-zalo">💎 Đăng ký Thành viên qua Zalo</a>
    </div>
    """, unsafe_allow_html=True)
    
    # Form đăng nhập cho thành viên cũ
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔑 Bạn đã có tài khoản? Đăng nhập tại đây"):
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Vào tập"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True
                    st.rerun()
                else: st.error("Sai thông tin đăng nhập!")
