import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- 1. CẤU HÌNH TRANG (SIDEBAR CỐ ĐỊNH) ---
st.set_page_config(
    page_title="Yoga Guru AI",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="expanded"  # <-- Cố định Sidebar luôn mở
)

# --- 2. GIAO DIỆN ĐẸP (CSS) ---
st.markdown("""
<style>
    /* Chỉnh font chữ và màu nền chung */
    .stApp {background-color: #f8f9fa;}
    
    /* Tin nhắn của AI: Nền trắng, bo tròn */
    div[data-testid="stChatMessage"] {
        background-color: #ffffff;
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    
    /* Tin nhắn của User: Nền xanh nhạt */
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd;
        flex-direction: row-reverse; /* Đảo chiều avatar */
        text-align: right;
    }

    /* Sidebar đẹp hơn */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #ddd;
    }
    
    /* Link màu cam thương hiệu */
    .stMarkdown a {color: #ff6b6b !important; font-weight: bold;}
    
    /* Ẩn footer mặc định */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. CẤU HÌNH API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("⚠️ Lỗi: Chưa cấu hình API Key trong Secrets.")
    st.stop()

VECTOR_DB_PATH = "bo_nao_vector"
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

# --- 4. LOAD BRAIN (CÓ DEBUG LỖI) ---
@st.cache_resource
def load_brain():
    # Kiểm tra xem folder có tồn tại không
    if not os.path.exists(VECTOR_DB_PATH):
        st.error(f"❌ LỖI: Không tìm thấy thư mục '{VECTOR_DB_PATH}'. Bạn hãy kiểm tra lại trên GitHub xem đã upload folder này lên chưa.")
        return None, None
    
    # Kiểm tra file index có bị lỗi Git LFS không (Nếu file quá nhẹ < 10KB là lỗi)
    index_file = os.path.join(VECTOR_DB_PATH, "index.faiss")
    if os.path.exists(index_file):
        file_size = os.path.getsize(index_file)
        if file_size < 10000: # Nhỏ hơn 10KB
            st.error(f"❌ LỖI NGHIÊM TRỌNG: File dữ liệu quá nhẹ ({file_size} bytes). Đây là lỗi do Git LFS chưa tải được file gốc lên. Vui lòng xem lại bước upload Git LFS.")
            return None, None

    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        return db, model
    except Exception as e:
        st.error(f"❌ Lỗi khi nạp dữ liệu: {e}")
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
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Hỏi mình bất cứ điều gì về Yoga nhé."}]

# --- SIDEBAR CỐ ĐỊNH & ĐẸP ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2647/2647596.png", width=60) # Icon Logo
    st.title("Yoga Guru AI")
    st.markdown("---")
    
    if st.session_state.authenticated:
        st.success(f"👋 Chào Yogi, **{st.session_state.username}**!")
        used, remaining = check_member_limit(st.session_state.username)
        
        # Thanh progress bar đẹp
        percent = used / DAILY_LIMIT
        st.progress(percent)
        st.write(f"📊 Đã dùng: **{used}/{DAILY_LIMIT}** câu")
        
        if st.button("🚪 Đăng xuất", type="secondary"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.info("🌱 Chế độ: **Khách dùng thử**")
        st.metric(label="Câu hỏi còn lại", value=f"{TRIAL_LIMIT - st.session_state.guest_usage}", delta=None)
        
        if st.session_state.guest_usage >= TRIAL_LIMIT:
            st.warning("🔒 Hết lượt thử.")
            with st.form("login_form"):
                user_input = st.text_input("Tài khoản")
                pass_input = st.text_input("Mật khẩu", type="password")
                if st.form_submit_button("🔑 Đăng nhập ngay"):
                    secrets_pass = st.secrets["passwords"].get(user_input)
                    if secrets_pass and secrets_pass == pass_input:
                        st.session_state.authenticated = True
                        st.session_state.username = user_input
                        st.rerun()
                    else: st.error("Sai mật khẩu!")
        else:
             st.markdown("---")
             with st.expander("🔐 Thành viên đăng nhập"):
                with st.form("login_form_guest"):
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
    st.caption("© 2024 Yoga Guru AI")

# --- GIAO DIỆN CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- KIỂM TRA QUYỀN CHAT ---
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
                st.error("❌ Hệ thống đang bảo trì dữ liệu (Lỗi DB). Vui lòng thử lại sau.")
                st.stop()
            
            msg_placeholder = st.empty()
            msg_placeholder.markdown("🧘 *Guru đang suy ngẫm...*")
            
            try:
                top_docs = search_engine(prompt, db)
                
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1

                if not top_docs:
                    resp = "Guru chưa tìm thấy bài viết phù hợp trong thư viện."
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
                        link_md = "\n\n---\n**📚 Tham khảo chi tiết:**\n" + "\n".join([f"- [{n}]({u})" for u, n in links.items()])

                    # --- PROMPT V33: ĐẸP & GỌN ---
                    sys_prompt = f"""
                    Bạn là Yoga Guru chuyên nghiệp.
                    Dựa trên dữ liệu dưới đây, hãy trả lời câu hỏi.
                    
                    DỮ LIỆU:
                    {context}
                    
                    CÂU HỎI: "{prompt}"
                    
                    YÊU CẦU:
                    1. Trả lời dưới dạng các gạch đầu dòng (khoảng 8-10 ý).
                    2. Tổng độ dài khoảng 200 từ.
                    3. Văn phong chuyên nghiệp, đi thẳng vào vấn đề.
                    4. KHÔNG tự viết link.
                    """
                    
                    response = model.generate_content(sys_prompt)
                    full_resp = response.text + link_md
                    msg_placeholder.markdown(full_resp)
                    st.session_state.messages.append({"role": "assistant", "content": full_resp})
                    st.rerun()

            except Exception as e: 
                st.error("Lỗi hệ thống. Vui lòng thử lại."); print(e)
else:
    if st.session_state.authenticated:
        st.info("⛔ Hôm nay bạn đã hỏi đủ 15 câu rồi. Hẹn gặp lại ngày mai nhé!")
    else:
        st.warning(f"🔒 Bạn đã hết {TRIAL_LIMIT} câu hỏi dùng thử. Vui lòng **Đăng nhập** ở cột bên trái.")
