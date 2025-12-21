import streamlit as st
import os
import re
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Yoga Guru AI", page_icon="🧘", layout="wide")

# --- CSS TÙY CHỈNH (GIAO DIỆN ĐẸP) ---
st.markdown("""
<style>
    .stChatMessage {font-size: 16px; line-height: 1.6;} 
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMarkdown a {color: #007bff !important; font-weight: bold !important; text-decoration: none;}
    .stMarkdown a:hover {text-decoration: underline;}
    div[data-testid="stForm"] {border: 1px solid #ddd; padding: 20px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- CẤU HÌNH API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("⚠️ Lỗi: Chưa cấu hình API Key.")
    st.stop()

VECTOR_DB_PATH = "bo_nao_vector"
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 15   # Giới hạn cho thành viên (15 câu/ngày)
TRIAL_LIMIT = 5    # Giới hạn dùng thử cho khách (5 câu)

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

# --- XỬ LÝ TÌM KIẾM ---
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

@st.cache_resource
def load_brain():
    if not os.path.exists(VECTOR_DB_PATH): return None, None
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    try:
        db = FAISS.load_local(VECTOR_DB_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-1.5-flash-latest') 
        return db, model
    except: return None, None

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

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧘 Yoga Guru AI")
    
    if st.session_state.authenticated:
        st.success(f"👤 {st.session_state.username}")
        used, remaining = check_member_limit(st.session_state.username)
        st.progress(used / DAILY_LIMIT)
        st.caption(f"Đã dùng: {used}/{DAILY_LIMIT} câu")
        if st.button("🚪 Đăng xuất"):
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.info(f"⚡ Dùng thử: **{st.session_state.guest_usage}/{TRIAL_LIMIT}** câu")
        if st.session_state.guest_usage >= TRIAL_LIMIT:
            st.warning("🔒 Hết lượt thử. Vui lòng đăng nhập.")
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
        else:
             st.caption("💡 Đăng nhập để sử dụng 15 câu/ngày.")
             with st.expander("🔐 Đăng nhập thành viên"):
                with st.form("login_form_guest"):
                    user_input = st.text_input("Tài khoản")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Vào"):
                        secrets_pass = st.secrets["passwords"].get(user_input)
                        if secrets_pass and secrets_pass == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.rerun()
                        else: st.error("Sai thông tin!")

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
                st.error("Lỗi kết nối DB."); st.stop()
            
            msg_placeholder = st.empty()
            msg_placeholder.markdown("🧘 *Đang tìm...*")
            
            try:
                top_docs = search_engine(prompt, db)
                
                if st.session_state.authenticated: increment_member_usage(st.session_state.username)
                else: st.session_state.guest_usage += 1

                if not top_docs:
                    resp = "Không tìm thấy thông tin phù hợp trong dữ liệu."
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

                    # --- PROMPT V32: 10 Ý - 200 TỪ ---
                    sys_prompt = f"""
                    Bạn là chuyên gia Yoga.
                    Dựa trên dữ liệu dưới đây, trả lời câu hỏi.
                    
                    DỮ LIỆU:
                    {context}
                    
                    CÂU HỎI: "{prompt}"
                    
                    YÊU CẦU TRÌNH BÀY:
                    1. Trả lời chi tiết, liệt kê khoảng **8-10 gạch đầu dòng** các ý quan trọng nhất.
                    2. Tổng độ dài khoảng **200 từ** (không quá dài, không quá ngắn).
                    3. Bỏ qua lời chào hỏi sáo rỗng, đi thẳng vào kiến thức.
                    4. Trình bày thoáng, đẹp.
                    5. KHÔNG tự viết link.
                    """
                    
                    response = model.generate_content(sys_prompt)
                    full_resp = response.text + link_md
                    msg_placeholder.markdown(full_resp)
                    st.session_state.messages.append({"role": "assistant", "content": full_resp})
                    st.rerun()

            except Exception as e: st.error("Lỗi xử lý."); print(e)
else:
    if st.session_state.authenticated:
        st.info("⛔ Hôm nay bạn đã hỏi đủ 15 câu rồi. Hẹn gặp lại ngày mai nhé!")
    else:
        st.warning(f"🔒 Bạn đã hết {TRIAL_LIMIT} câu hỏi miễn phí. Vui lòng **Đăng nhập** ở cột bên trái để tiếp tục.")
