import streamlit as st
import os
import re
import json
import datetime
import uuid # Thêm thư viện để tạo ID cho khách
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

# --- CSS ẨN THANH CÔNG CỤ & FOOTER & UI MỚI ---
st.markdown("""
<style>
    /* 1. Ẩn menu 3 chấm, Header, Footer, Toolbar */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 2. Đẩy nội dung lên sát mép trên */
    .block-container {
        padding-top: 3rem !important; /* Tăng padding để nhường chỗ cho thanh bar */
    }
    
    /* 3. Bong bóng chat đẹp */
    .stApp {background-color: white;}
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa; border-radius: 15px; padding: 12px; margin-top: 30px;
        border: 1px solid #eee;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd; flex-direction: row-reverse; text-align: right; border: none;
    }
    
    /* 4. Link tham khảo (Style Markdown chuẩn) */
    .stMarkdown a {
        color: #6c5ce7 !important; 
        font-weight: bold !important; 
        text-decoration: none;
    }
    .stMarkdown a:hover {
        text-decoration: underline;
    }

    /* 5. THANH PROGRESS BAR XỊN XÒ */
    .usage-bar-container {
        position: fixed; top: 0; left: 0; width: 100%; height: 6px;
        background-color: #f0f0f0; z-index: 999999;
    }
    .usage-bar-fill {
        height: 100%; 
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        transition: width 0.5s ease-in-out;
    }
    .usage-text {
        position: fixed; top: 10px; right: 20px; 
        background: rgba(255,255,255,0.9); padding: 5px 15px; border-radius: 20px;
        font-size: 12px; color: #555; font-weight: bold;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 999998;
    }

    /* 6. MODAL THÔNG BÁO HẾT LƯỢT */
    .limit-modal {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(8px);
        z-index: 1000000;
        display: flex; align-items: center; justify-content: center;
        flex-direction: column;
    }
    .limit-box {
        background: white; padding: 40px; border-radius: 25px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.2);
        text-align: center; max-width: 400px;
        border: 1px solid #eee;
        animation: popup 0.5s cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }
    @keyframes popup {
        0% { transform: scale(0.5); opacity: 0; }
        100% { transform: scale(1); opacity: 1; }
    }
    .limit-icon { font-size: 60px; margin-bottom: 20px; }
    .limit-title { font-size: 24px; font-weight: 800; color: #ff6b6b; margin-bottom: 10px; }
    .limit-desc { color: #666; margin-bottom: 25px; line-height: 1.5; }
    .limit-btn {
        background: linear-gradient(135deg, #6c5ce7, #a29bfe);
        color: white !important; padding: 12px 30px; border-radius: 50px;
        text-decoration: none; font-weight: bold; display: inline-block;
        box-shadow: 0 5px 15px rgba(108, 92, 231, 0.3);
        transition: transform 0.2s;
    }
    .limit-btn:hover { transform: translateY(-3px); }
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

# --- XỬ LÝ USER & KHÁCH (CHỐNG F5) ---
# Lấy hoặc tạo Guest ID cố định trên URL
if "guest_id" not in st.query_params:
    st.query_params["guest_id"] = str(uuid.uuid4())
GUEST_ID = f"guest_{st.query_params['guest_id']}"

def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

# Hàm kiểm tra chung cho cả Member và Khách (Lưu vào DB để chống F5)
def check_usage_limit(user_key, limit_max):
    data = load_usage_db()
    today = str(datetime.date.today())
    
    # Nếu user chưa có hoặc khác ngày -> Reset
    if user_key not in data or data[user_key]["date"] != today:
        data[user_key] = {"date": today, "count": 0}
        save_usage_db(data)
        return 0, limit_max
    
    current = data[user_key]["count"]
    return current, limit_max - current

def increment_usage(user_key):
    data = load_usage_db()
    today = str(datetime.date.today())
    if user_key in data and data[user_key]["date"] == today:
        data[user_key]["count"] += 1
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
if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Chúc bạn một ngày nhiều niềm vui, chúng ta sẽ bắt đầu từ đâu?."}]

# Xác định User hiện tại và Giới hạn
current_user_key = st.session_state.username if st.session_state.authenticated else GUEST_ID
current_limit_max = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT

# Lấy thông tin sử dụng (Đã được lưu bền vững trong JSON)
used_count, remaining_count = check_usage_limit(current_user_key, current_limit_max)
percent_used = (used_count / current_limit_max) * 100

# --- HIỂN THỊ THANH BAR ---
st.markdown(f"""
    <div class="usage-bar-container">
        <div class="usage-bar-fill" style="width: {percent_used}%;"></div>
    </div>
    <div class="usage-text">
        ⚡ Lượt dùng: {used_count}/{current_limit_max}
    </div>
""", unsafe_allow_html=True)

# --- HIỂN THỊ MODAL NẾU HẾT LƯỢT ---
if remaining_count <= 0:
    st.markdown(f"""
    <div class="limit-modal">
        <div class="limit-box">
            <div class="limit-icon">🧘‍♀️</div>
            <div class="limit-title">Đã hết năng lượng!</div>
            <div class="limit-desc">
                Bạn đã dùng hết {current_limit_max} câu hỏi miễn phí hôm nay.<br>
                Hãy quay lại vào ngày mai hoặc đăng nhập để tập luyện tiếp nhé!
            </div>
            <a href="https://zalo.me/84963759566" target="_blank" class="limit-btn">💬 Liên hệ Admin</a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    can_chat = False
else:
    can_chat = True

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

if can_chat:
    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if db:
                # Tăng lượt dùng ngay khi hỏi (Lưu vào JSON ngay lập tức)
                increment_usage(current_user_key)
                
                # Cập nhật lại thanh bar ngay lập tức bằng cách rerun (tạo cảm giác mượt)
                # Tuy nhiên rerun sẽ reload cả trang, nên ta chấp nhận bar cập nhật ở lần tương tác sau 
                # hoặc dùng placeholder nếu muốn phức tạp hơn. Ở đây giữ đơn giản.
                
                top_docs = search_engine(prompt, db)
                
                # --- PHẦN KHÔI PHỤC LOGIC LINK ĐẸP ---
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
                    # Rerun nhẹ để cập nhật thanh bar
                    st.rerun() 
                except Exception as e:
                    st.error(f"Lỗi AI: {e}")
            else: st.error("Đang kết nối não bộ...")
else:
    # Nếu hết lượt thì ẩn khung chat input bằng cách không gọi st.chat_input
    pass

# --- THAY THẾ ĐOẠN FORM ĐĂNG NHẬP BẰNG CODE NÀY ---
if not st.session_state.authenticated and can_chat: 
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập Thành viên (Bấm để mở)"):
        with st.form("login"):
            st.markdown("### Đăng nhập hệ thống")
            u = st.text_input("Tên đăng nhập")
            p = st.text_input("Mật khẩu", type="password")
            
            # Chia cột cho 2 nút bấm nằm ngang hàng
            col_btn1, col_btn2 = st.columns([1, 1])
            
            with col_btn1:
                submit = st.form_submit_button("Đăng nhập ngay", use_container_width=True)
            
            with col_btn2:
                # Nút liên hệ giả lập bằng HTML để giống style nút bấm của Streamlit
                st.markdown(f"""
                    <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: none;">
                        <div style="
                            background-color: white; 
                            color: #6c5ce7; 
                            border: 1px solid #6c5ce7;
                            padding: 8px 16px; 
                            border-radius: 8px; 
                            text-align: center; 
                            font-weight: 500;
                            font-size: 14px;
                            line-height: 1.6;
                            height: 38px;
                            transition: all 0.3s;
                        " onmouseover="this.style.background='#f3f0ff'" onmouseout="this.style.background='white'">
                            💬 Lấy tài khoản
                        </div>
                    </a>
                """, unsafe_allow_html=True)

            if submit:
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.rerun()
                else: 
                    st.error("Sai thông tin rồi!")
