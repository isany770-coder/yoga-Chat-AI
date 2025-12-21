import streamlit as st
import os
import re
import json
import datetime
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
import extra_streamlit_components as stx # Thư viện quản lý Cookie

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Yoga Assistant", 
    page_icon="🧘", 
    layout="wide", 
    initial_sidebar_state="collapsed",
    menu_items=None
)

# --- CSS GIAO DIỆN & PAYWALL ---
st.markdown("""
<style>
    /* 1. Ẩn menu thừa */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 2. Đẩy nội dung lên trên */
    .block-container { padding-top: 1rem !important; }
    
    /* 3. Bong bóng chat */
    .stApp {background-color: white;}
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa; border-radius: 15px; padding: 12px; margin-top: 20px;
        border: 1px solid #eee;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd; flex-direction: row-reverse; text-align: right; border: none;
    }
    
    /* 4. Link tham khảo */
    .stMarkdown a { color: #6c5ce7 !important; font-weight: bold !important; text-decoration: none; }
    .stMarkdown a:hover { text-decoration: underline; }

    /* 5. GIAO DIỆN HẾT LƯỢT (PAYWALL) */
    .paywall-container {
        border: 2px solid #6c5ce7;
        background-color: #f3f0ff;
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        margin: 50px auto;
        max-width: 600px;
        box-shadow: 0 10px 25px rgba(108, 92, 231, 0.15);
    }
    .paywall-btn {
        display: inline-block;
        background-color: #6c5ce7;
        color: white !important;
        padding: 12px 35px;
        border-radius: 50px;
        font-weight: bold;
        text-decoration: none !important;
        margin-top: 20px;
        font-size: 18px;
        transition: transform 0.2s;
    }
    .paywall-btn:hover { transform: scale(1.05); }
</style>
""", unsafe_allow_html=True)

# --- KHỞI TẠO COOKIE MANAGER (CHẶN F5) ---
@st.cache_resource(experimental_allow_widgets=True)
def get_manager(): return stx.CookieManager()

cookie_manager = get_manager()

# --- KHỞI TẠO API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except: st.stop()

CURRENT_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, "bo_nao_vector")
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 5 # Giới hạn số câu hỏi cho khách (Ví dụ: 5 câu)

# --- HÀM QUẢN LÝ USER ---
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

# --- HÀM QUẢN LÝ KHÁCH (DÙNG COOKIE) ---
def get_guest_usage_cookie():
    cookie_val = cookie_manager.get("guest_usage_data")
    today = str(datetime.date.today())
    if cookie_val:
        try:
            # Cookie lưu dạng string, cần parse
            if isinstance(cookie_val, str): data = json.loads(cookie_val)
            else: data = cookie_val # Đôi khi stx trả về dict luôn
            
            if data.get("date") == today:
                return data.get("count", 0)
        except: pass
    return 0

def increment_guest_usage_cookie(current_count):
    today = str(datetime.date.today())
    new_data = {"date": today, "count": current_count + 1}
    # Lưu cookie 1 ngày
    cookie_manager.set("guest_usage_data", json.dumps(new_data), key="set_guest", expires_at=datetime.datetime.now() + datetime.timedelta(days=1))

# --- LOGIC TÌM KIẾM ---
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
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Chúc bạn một ngày an lành, bạn muốn tập gì hôm nay?"}]

# Kiểm tra quyền Chat
can_chat = False
guest_usage = get_guest_usage_cookie() # Lấy từ Cookie (không bị reset khi F5)

if st.session_state.authenticated:
    used, remaining = check_member_limit(st.session_state.username)
    if remaining > 0: 
        can_chat = True
    else: 
        st.warning("⛔ Hôm nay bạn đã hỏi đủ 25 câu.")
else:
    if guest_usage < TRIAL_LIMIT:
        can_chat = True
        st.caption(f"🔒 Dùng thử miễn phí: {guest_usage}/{TRIAL_LIMIT} câu")
    else:
        can_chat = False

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

# GIAO DIỆN CHÍNH
if can_chat:
    # 1. Nếu còn lượt -> Hiện ô chat
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if db:
                # Tăng lượt dùng (Cookie hoặc DB)
                if st.session_state.authenticated: 
                    increment_member_usage(st.session_state.username)
                else: 
                    increment_guest_usage_cookie(guest_usage)
                    # Cập nhật biến tạm thời để UI phản hồi ngay (dù cookie cần reload mới thấy giá trị mới)
                    guest_usage += 1
                
                top_docs = search_engine(prompt, db)
                
                links_markdown = ""
                context = ""
                final_links = {} 
                
                if top_docs:
                    context = "\n".join([d.page_content for d in top_docs])
                    for d in top_docs:
                        title = d.metadata.get('title', 'Tài liệu tham khảo')
                        url = d.metadata.get('url', '#')
                        clean_title = title.replace("[", "").replace("]", "").replace("(", " - ").replace(")", "")
                        if url != '#' and "http" in url:
                            final_links[url] = clean_title

                    if final_links:
                        links_markdown = "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                        for url, name in final_links.items():
                            links_markdown += f"- 🔗 [{name}]({url})\n"
                
                sys_prompt = f"""
                Bạn là chuyên gia Yoga.
                DỮ LIỆU BÀI VIẾT: {context}
                CÂU HỎI: "{prompt}"
                 YÊU CẦU:
                1. Trả lời CỰC KỲ NGẮN GỌN (Tối đa 5-6 gạch đầu dòng).
                2. Tổng độ dài KHÔNG QUÁ 100 TỪ.
                3. Đi thẳng vào trọng tâm, bỏ qua lời dẫn dắt vô nghĩa.
                4. Giọng văn thân thiện, dứt khoát.
                5. KHÔNG tự chèn link (Hệ thống sẽ tự làm).
                """
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
    # 2. Nếu HẾT LƯỢT -> Hiện Paywall (Chỉ hiện khi chưa đăng nhập)
    if not st.session_state.authenticated:
        # Sử dụng HTML entities &#129496; thay cho icon Yoga để tránh lỗi Syntax
        st.markdown(f"""
        <div class="paywall-container">
            <h2 style="color:#6c5ce7; margin-bottom:15px">&#129496; Bạn đã hoàn thành bài tập thử nghiệm!</h2>
            <p style="font-size:16px; color:#555">
                Bạn đã sử dụng hết <b>{TRIAL_LIMIT}/{TRIAL_LIMIT}</b> câu hỏi miễn phí hôm nay.<br>
                Để tiếp tục hành trình Yoga không giới hạn, hãy trở thành thành viên ngay.
            </p>
            <a href="https://zalo.me/84963759566" target="_blank" class="paywall-btn">💎 Đăng ký Thành viên qua Zalo</a>
        </div>
        """, unsafe_allow_html=True)

# 3. Form Đăng nhập (Luôn hiện ở dưới cùng nếu chưa login)
if not st.session_state.authenticated:
    st.markdown("<br><hr>", unsafe_allow_html=True)
    with st.expander("🔑 Bạn đã có tài khoản? Đăng nhập tại đây"):
        with st.form("login"):
            u = st.text_input("Tên đăng nhập")
            p = st.text_input("Mật khẩu", type="password")
            if st.form_submit_button("Vào tập"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai thông tin!")
