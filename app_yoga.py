import streamlit as st
import os
import re
import json
import datetime
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
import extra_streamlit_components as stx # THƯ VIỆN QUẢN LÝ COOKIE

# --- 1. CẤU HÌNH TRANG & CSS CAO CẤP ---
st.set_page_config(
    page_title="Yoga Assistant AI", 
    page_icon="🧘‍♀️", 
    layout="centered", # Dùng centered để giống app chat mobile hơn
    initial_sidebar_state="collapsed"
)

# CSS Tùy chỉnh: Chat Bubble đẹp, Ẩn linh tinh, Paywall Card
st.markdown("""
<style>
    /* Ẩn Header, Footer, Menu mặc định */
    [data-testid="stToolbar"], header, footer {display: none !important;}
    .block-container {padding-top: 1rem !important; padding-bottom: 5rem !important;}
    
    /* CHAT BUBBLE STYLE */
    .chat-row {display: flex; margin-bottom: 10px;}
    .user-row {justify-content: flex-end;}
    .bot-row {justify-content: flex-start;}
    
    .chat-bubble {
        padding: 12px 16px;
        border-radius: 15px;
        max-width: 80%;
        font-size: 16px;
        line-height: 1.5;
        position: relative;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }
    .user-bubble {
        background: linear-gradient(135deg, #6c5ce7, #a29bfe);
        color: white;
        border-bottom-right-radius: 2px;
    }
    .bot-bubble {
        background-color: #f1f2f6;
        color: #2d3436;
        border-bottom-left-radius: 2px;
        border: 1px solid #dfe6e9;
    }
    
    /* LINK STYLE */
    .bot-bubble a {color: #d63031 !important; font-weight: bold; text-decoration: none;}
    .bot-bubble a:hover {text-decoration: underline;}

    /* PAYWALL CARD STYLE */
    .paywall-container {
        border: 2px solid #e17055;
        background-color: #fff0eb;
        border-radius: 20px;
        padding: 25px;
        text-align: center;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(225, 112, 85, 0.2);
        animation: fadeIn 0.5s;
    }
    @keyframes fadeIn {from {opacity:0; transform: translateY(20px);} to {opacity:1; transform: translateY(0);}}
    
    .paywall-title {font-size: 22px; font-weight: bold; color: #d63031; margin-bottom: 10px;}
    .paywall-text {font-size: 16px; color: #636e72; margin-bottom: 20px;}
    
    .btn-zalo {
        display: inline-block;
        background-color: #0068ff;
        color: white !important;
        padding: 10px 25px;
        border-radius: 50px;
        font-weight: bold;
        text-decoration: none;
        box-shadow: 0 4px 6px rgba(0, 104, 255, 0.3);
        transition: transform 0.2s;
    }
    .btn-zalo:hover {transform: scale(1.05);}
</style>
""", unsafe_allow_html=True)

# --- KHỞI TẠO API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except: st.stop()

# --- CẤU HÌNH HỆ THỐNG ---
CURRENT_DIR = os.getcwd()
VECTOR_DB_PATH = os.path.join(CURRENT_DIR, "bo_nao_vector")
TRIAL_LIMIT = 10 # Giới hạn 10 câu
cookie_manager = stx.CookieManager()

def get_guest_usage():
    # CHỖ SỬA QUAN TRỌNG: Đợi 0.2s để trình duyệt kịp gửi cookie lên
    time.sleep(0.2)
    cookie_data = cookie_manager.get("yoga_guest_usage")
    today = str(datetime.date.today())
    
    if cookie_data:
        try:
            data = json.loads(cookie_data)
            if data.get("date") != today:
                new_data = {"date": today, "count": 0}
                cookie_manager.set("yoga_guest_usage", json.dumps(new_data), key="set_reset")
                return 0
            return data.get("count", 0)
        except:
            return 0
    return 0

def increment_guest_usage():
    current = get_guest_usage()
    today = str(datetime.date.today())
    new_data = {"date": today, "count": current + 1}
    cookie_manager.set("yoga_guest_usage", json.dumps(new_data), expires_at=datetime.datetime.now() + datetime.timedelta(days=1), key="set_inc")
    time.sleep(0.1)

# --- LOAD BRAIN (CACHE) ---
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

# --- HÀM TÌM KIẾM ---
SPECIAL_MAPPING = {"trồng chuối": ["sirsasana"], "con quạ": ["bakasana"], "cái cày": ["halasana"]}
STOPWORDS = {'là', 'của', 'như', 'thế', 'nào', 'tập', 'bài', 'cách', 'tôi', 'bạn', 'muốn', 'hỏi', 'gì', 'cho', 'em', 'mình'}

def clean_and_extract_keywords(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return set([w for w in text.split() if w not in STOPWORDS and len(w) > 1])

@st.cache_data(ttl=3600) 
def search_engine(query):
    if not db: return []
    user_keywords = clean_and_extract_keywords(query)
    injected_keywords = set()
    for key, values in SPECIAL_MAPPING.items():
        if key in query.lower(): injected_keywords.update(values)
    
    search_query = f"{query} {' '.join(injected_keywords)}"
    raw_docs = db.similarity_search(search_query, k=50)
    
    if not user_keywords: user_keywords = set(query.lower().split())
    
    matched_docs = []
    seen = set()
    for d in raw_docs:
        title = d.metadata.get('title', 'Tài liệu Yoga')
        if title in seen: continue
        score = 0
        title_keywords = clean_and_extract_keywords(title)
        common = user_keywords.intersection(title_keywords)
        if common: score += len(common) * 10
        matched_docs.append((d, score))
        seen.add(title)
        
    matched_docs.sort(key=lambda x: x[1], reverse=True)
    return [x[0] for x in matched_docs[:3]]

# --- LOGIC SESSION ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Thở sâu và hỏi mình bất cứ điều gì về Yoga nhé."}]
if "show_login" not in st.session_state: st.session_state.show_login = False

# Lấy số lần đã dùng từ Cookie
current_usage = 0
remaining = 0
if st.session_state.authenticated:
    current_usage = 0 
    remaining = 999 
else:
    current_usage = get_guest_usage()
    remaining = TRIAL_LIMIT - current_usage

# --- GIAO DIỆN CHAT ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-row user-row"><div class="chat-bubble user-bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-row bot-row"><div class="chat-bubble bot-bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)

# 2. Xử lý Input & Paywall
if st.session_state.authenticated or remaining > 0:
    if not st.session_state.authenticated:
        progress = current_usage / TRIAL_LIMIT
        st.progress(progress)
        st.caption(f"🌱 Dùng thử miễn phí: {current_usage}/{TRIAL_LIMIT} câu hỏi.")

    if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

if st.session_state.messages[-1]["role"] == "user":
    prompt = st.session_state.messages[-1]["content"]
    
    if not st.session_state.authenticated and get_guest_usage() >= TRIAL_LIMIT:
        st.error("Bạn đã hết lượt dùng thử. Vui lòng F5 để xem hướng dẫn.")
        st.stop()

    with st.spinner("Đang kết nối năng lượng... 🧘‍♀️"):
        top_docs = search_engine(prompt)
        
        if not st.session_state.authenticated:
            increment_guest_usage()
        
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
                links_markdown = "<br><b>📚 Tham khảo:</b><br>"
                for url, name in final_links.items():
                    links_markdown += f"• <a href='{url}' target='_blank'>{name}</a><br>"
        
        sys_prompt = f"""
        Bạn là chuyên gia Yoga.
        DỮ LIỆU BÀI VIẾT:
        {context}
        CÂU HỎI: "{prompt}"
        YÊU CẦU TRẢ LỜI:
        1. Trả lời CỰC KỲ NGẮN GỌN (Tối đa 5-6 gạch đầu dòng).
        2. Tổng độ dài KHÔNG QUÁ 100 TỪ.
        3. Đi thẳng vào trọng tâm, bỏ qua lời dẫn dắt vô nghĩa.
        4. Giọng văn thân thiện, dứt khoát.
        5. KHÔNG tự chèn link (Hệ thống sẽ tự làm).
        """
        try:
            response_text = model.generate_content(sys_prompt).text
            final_html = response_text.replace("\n", "<br>") + links_markdown
            st.session_state.messages.append({"role": "assistant", "content": final_html})
            st.rerun()
        except:
            st.error("Hệ thống đang quá tải, thử lại sau nhé.")

# 3. PAYWALL - CHẶN CỬA KHI HẾT LƯỢT
if not st.session_state.authenticated and remaining <= 0:
    st.markdown("""
    <div class="paywall-container">
        <div style="font-size: 40px;">🎁</div>
        <div class="paywall-title">Bạn đã dùng hết 10 câu hỏi miễn phí hôm nay!</div>
        <p class="paywall-text">Việc tập luyện cần sự kiên trì và một người dẫn đường tận tụy.<br>Để tiếp tục được hỗ trợ không giới hạn và nhận lộ trình riêng:</p>
        <a href="https://zalo.me/84963759566" target="_blank" class="btn-zalo">💬 Mở khóa Full Tính Năng (Zalo)</a>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔑 Đăng nhập thành viên (Nếu đã có Key)"):
        st.session_state.show_login = True

if st.session_state.show_login and not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("🔐 Đăng nhập")
        u = st.text_input("Tên đăng nhập")
        p = st.text_input("Mật khẩu", type="password")
        if st.form_submit_button("Vào tập"):
            if st.secrets["passwords"].get(u) == p:
                st.session_state.authenticated = True; st.session_state.username = u; st.session_state.show_login = False
                st.success("Chào mừng trở lại!"); time.sleep(1); st.rerun()
            else: st.error("Sai thông tin rồi!")
