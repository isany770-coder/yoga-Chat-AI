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

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    .stChatMessage {font-size: 16px; line-height: 1.6;} 
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stMarkdown a {color: #007bff !important; font-weight: bold !important; text-decoration: none;}
    .stMarkdown a:hover {text-decoration: underline;}
    /* Style cho khung đăng nhập */
    div[data-testid="stForm"] {border: 1px solid #ddd; padding: 20px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- CẤU HÌNH API & DATABASE ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("⚠️ Lỗi: Chưa cấu hình API Key trong .streamlit/secrets.toml")
    st.stop()

VECTOR_DB_PATH = "bo_nao_vector"
USAGE_DB_FILE = "usage_database.json"
DAILY_LIMIT = 10  # Giới hạn 15 câu/ngày

# --- QUẢN LÝ QUOTA NGƯỜI DÙNG (LƯU FILE JSON) ---
def load_usage_db():
    if not os.path.exists(USAGE_DB_FILE):
        return {}
    with open(USAGE_DB_FILE, "r") as f:
        return json.load(f)

def save_usage_db(data):
    with open(USAGE_DB_FILE, "w") as f:
        json.dump(data, f)

def check_user_limit(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    
    # Nếu user chưa có trong DB hoặc qua ngày mới -> Reset
    if username not in data or data[username]["date"] != today:
        data[username] = {"date": today, "count": 0}
        save_usage_db(data)
        return 0, DAILY_LIMIT # Đã dùng 0, Còn lại 10
    
    used = data[username]["count"]
    return used, DAILY_LIMIT - used

def increment_user_usage(username):
    data = load_usage_db()
    today = str(datetime.date.today())
    
    if username in data and data[username]["date"] == today:
        data[username]["count"] += 1
        save_usage_db(data)

# --- TỪ KHÓA & LOGIC TÌM KIẾM (GIỮ NGUYÊN V30) ---
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

STOPWORDS = {
    'là', 'của', 'những', 'cái', 'việc', 'trong', 'khi', 'bị', 'với', 'cho', 'được', 
    'tại', 'vì', 'sao', 'thì', 'lại', 'mà', 'và', 'các', 'có', 'như', 'để', 'này', 
    'đó', 'về', 'theo', 'nhất', 'gì', 'thế', 'nào', 'làm', 'tập', 'bài', 'cách',
    'như', 'thế', 'nào', 'tôi', 'bạn', 'muốn', 'hỏi'
}

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
        model = genai.GenerativeModel('gemini-flash-latest') 
        return db, model
    except Exception as e:
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
    
    if not user_keywords:
        user_keywords = set(query_lower.split())

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

# --- LOGIC ĐĂNG NHẬP (SIDEBAR) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""

with st.sidebar:
    st.title("🧘 Yoga Guru AI")
    
    if not st.session_state.authenticated:
        st.subheader("🔐 Đăng nhập")
        with st.form("login_form"):
            user_input = st.text_input("Tài khoản")
            pass_input = st.text_input("Mật khẩu", type="password")
            submit_btn = st.form_submit_button("Vào tập")
            
            if submit_btn:
                # Kiểm tra trong secrets
                secrets_pass = st.secrets["passwords"].get(user_input)
                if secrets_pass and secrets_pass == pass_input:
                    st.session_state.authenticated = True
                    st.session_state.username = user_input
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else:
                    st.error("Sai tài khoản hoặc mật khẩu")
    else:
        # Đã đăng nhập
        st.success(f"Xin chào, **{st.session_state.username}**! 👋")
        
        # Kiểm tra số lượt còn lại
        used, remaining = check_user_limit(st.session_state.username)
        
        # Thanh tiến trình
        progress = used / DAILY_LIMIT
        st.progress(progress)
        st.write(f"💬 Hôm nay: **{used}/{DAILY_LIMIT}** câu")
        
        if st.button("🚪 Đăng xuất"):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.rerun()
            
    st.markdown("---")
    st.caption("Powered by Yoga Is My Life")

# --- GIAO DIỆN CHAT CHÍNH ---
if st.session_state.authenticated:
    # Check limit trước khi cho hiện khung chat
    used, remaining = check_user_limit(st.session_state.username)
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Namaste! 🙏 Trợ lý Yoga (Final Stable) đã sẵn sàng.\nChúng ta nên bắt đầu từ đâu nhỉ?."}
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if remaining > 0:
        if prompt := st.chat_input("VD: Tại sao tập bụng đau lưng? Kỹ thuật trồng chuối..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                if db is None:
                    st.error("⚠️ Lỗi kết nối Database.")
                    st.stop()
                    
                message_placeholder = st.empty()
                message_placeholder.markdown("🧘 *Đang tra cứu...*")

                try:
                    top_docs = search_engine(prompt, db)
                    
                    if not top_docs:
                        response_text = "Xin lỗi, mình không tìm thấy tài liệu phù hợp trong thư viện."
                        message_placeholder.markdown(response_text)
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                    else:
                        # Tìm thấy bài -> Trừ lượt ngay lập tức
                        increment_user_usage(st.session_state.username)
                        
                        context_text = ""
                        final_links = {}
                        for i, d in enumerate(top_docs):
                            title = d.metadata.get('title', 'No Title')
                            url = d.metadata.get('url', '#')
                            context_text += f"[TÀI LIỆU {i+1}]: {title}\nNội dung: {d.page_content}\n\n"
                            if url != '#' and "http" in url and url not in final_links:
                                 clean_title = title.replace("[", "").replace("]", "").replace("(", " - ").replace(")", "")
                                 final_links[url] = clean_title

                        links_markdown = ""
                        if final_links:
                            links_markdown = "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                            for url, name in final_links.items():
                                links_markdown += f"- 🔗 [{name}]({url})\n"

                        system_prompt = f"""
                        Bạn là chuyên gia Yoga.
                        DỮ LIỆU BÀI VIẾT:
                        {context_text}
                        CÂU HỎI: "{prompt}"
                        YÊU CẦU:
                        1. **Trung thực:** Chỉ trả lời dựa trên thông tin có trong tài liệu.
            2. **Chuyên môn:** Nếu là câu hỏi kỹ thuật, hãy hướng dẫn từng bước rõ ràng, chú ý đến hơi thở và định tuyến an toàn.
            3. **Cấu trúc:** Trả lời ngắn gọn, súc tích, sử dụng gạch đầu dòng để dễ đọc.
            4. **Lưu ý:** KHÔNG tự ý chèn đường link vào nội dung trả lời (Hệ thống sẽ tự động thêm danh sách tham khảo ở cuối).
            """
                        
                        response = model.generate_content(system_prompt)
                        full_response = response.text + links_markdown
                        
                        message_placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                        
                        # Rerun để cập nhật thanh tiến trình bên trái
                        st.rerun()

                except Exception as e:
                    st.error("Có lỗi xảy ra.")
                    print(e)
    else:
        st.warning("⛔ Bạn đã hết 10 lượt hỏi miễn phí hôm nay. Quay lại vào ngày mai nhé!")

else:
    # Màn hình chờ khi chưa đăng nhập
    st.info("👈 Vui lòng đăng nhập ở thanh bên trái để sử dụng Trợ lý Yoga.")
