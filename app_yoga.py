import streamlit as st

# =====================================================
# 1. PAGE CONFIG - PHẢI LÀ DÒNG ĐẦU TIÊN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. CSS - ÉP GIAO DIỆN TRẮNG & LAYOUT NÚT SONG SONG
# =====================================================
st.markdown("""
<style>
    /* Ép nền trắng tuyệt đối */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #212121 !important;
    }
    
    /* Ẩn hoàn toàn Toolbar và Footer để nhúng Iframe cho đẹp */
    [data-testid="stToolbar"], header, footer {
        display: none !important;
    }

    /* THANH PROGRESS BAR CỐ ĐỊNH */
    .usage-bar-container {
        position: fixed; top: 0; left: 0; width: 100%; height: 5px;
        background-color: #f0f0f0; z-index: 999999;
    }
    .usage-bar-fill {
        height: 100%; 
        background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%);
        transition: width 0.5s ease-in-out;
    }
    .usage-text {
        position: fixed; top: 10px; right: 20px; 
        background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px;
        font-size: 11px; color: #333; font-weight: bold;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 999998;
    }

    /* CHAT UI */
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa !important; border-radius: 12px; padding: 10px; margin-top: 20px;
    }
    
    /* STYLE NÚT ZALO GIẢ LẬP NÚT STREAMLIT */
    .zalo-btn {
        display: block; width: 100%; background-color: white; 
        color: #0f988b !important; border: 1px solid #0f988b;
        padding: 8px 16px; border-radius: 8px; text-align: center; 
        font-weight: 500; font-size: 14px; line-height: 1.6;
        height: 38.5px; text-decoration: none !important; transition: all 0.3s;
    }
    .zalo-btn:hover { background-color: #f0f9f8; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. IMPORT THƯ VIỆN
# =====================================================
import gdown, zipfile, os, re, json, datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# Cấu hình nạp dữ liệu từ Drive (Não 500MB)
FILE_ID_DRIVE = "1vOvvanNvDaLwP8Xs4nn1UhkciRvTxzyA" 
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
OUTPUT_ZIP = "/tmp/bo_nao_vector.zip"
EXTRACT_PATH = "/tmp/bo_nao_vector"

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Thiếu API KEY")
    st.stop()

# =====================================================
# 4. LOAD NÃO BỘ (DÙNG /TMP/ ĐỂ TRÁNH CRASH)
# =====================================================
@st.cache_resource
def load_brain():
    if not os.path.exists(EXTRACT_PATH):
        try:
            with st.spinner("🚀 Đang khởi động trí tuệ nhân tạo..."):
                gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=True)
                with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                    zip_ref.extractall("/tmp/")
                if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
        except Exception: return None, None

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except: return None, None

db, model = load_brain()

# =====================================================
# 5. QUẢN LÝ LƯỢT DÙNG (CHỐNG F5 BẰNG JSON)
# =====================================================
USAGE_DB_FILE = "/tmp/usage_db_v2.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_usage_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_usage_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state: st.session_state.messages = [{"role":"assistant","content":"Namaste! 🙏 Thật vui được gặp bạn. Hôm nay chúng ta sẽ bắt đầu từ đâu?"}]

# Xác định người dùng và giới hạn
today = str(datetime.date.today())
usage_db = get_usage_data()
user_key = st.session_state.username if st.session_state.authenticated else "anonymous_guest"

if user_key not in usage_db or usage_db[user_key]["date"] != today:
    usage_db[user_key] = {"date": today, "count": 0}
    save_usage_data(usage_db)

used = usage_db[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))

# Thanh tiến trình đồng bộ với Widget
st.markdown(f"""
    <div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div>
    <div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>
""", unsafe_allow_html=True)

# =====================================================
# 6. HIỂN THỊ CHAT & XỬ LÝ (BẢN TỐI ƯU TỔNG LỰC)
# =====================================================
# Khởi tạo can_chat để tránh lỗi biến
can_chat = used < limit

# Hiển thị lịch sử chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if can_chat:
    if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
        # 1. Hiển thị tin nhắn người dùng ngay lập tức
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Xử lý logic AI
        with st.chat_message("assistant"):
            if db:
                # Tăng k=20 để lục tung 15 triệu từ tìm bài Nghiên cứu/Giải mã
                docs = db.similarity_search(prompt, k=20)
                
                # Tạo trí nhớ ngắn hạn (lấy 3 câu hội thoại gần nhất)
                history = ""
                for m in st.session_state.messages[-4:-1]:
                    role = "Người dùng" if m["role"] == "user" else "Chuyên gia"
                    history += f"{role}: {m['content'][:150]}\n"

                # Phân loại tài liệu: Ưu tiên Nghiên cứu/Giải mã
                study_docs = []
                general_docs = []
                study_keywords = ["nghiên cứu", "giải mã", "rct", "meta", "khoa học", "chứng minh", "cơ chế"]

                for d in docs:
                    title = d.metadata.get('title', '').lower()
                    if any(kw in title for kw in study_keywords):
                        study_docs.append(d)
                    else:
                        general_docs.append(d)

                # Ép AI đọc tối đa 10 đoạn dữ liệu (ưu tiên bài nghiên cứu lên trước)
                final_docs = (study_docs + general_docs)[:10]
                
                context_parts = []
                source_map = {} 
                for d in final_docs:
                    t = d.metadata.get('title', 'Tài liệu Yoga')
                    u = d.metadata.get('url', '#')
                    # Xóa sạch số thứ tự nguồn trong context để AI không bắt chước
                    context_parts.append(f"TIÊU ĐỀ: {t}\nNỘI DUNG: {d.page_content}")
                    source_map[u] = t

                context_string = "\n\n".join(context_parts)
                
                # PROMPT TỐI ƯU: Có trí nhớ, cực sạch, ưu tiên khoa học
                sys_prompt = f"""Bạn là chuyên gia Yoga khoa học. Hãy trả lời dựa trên LỊCH SỬ và NGUỒN DỮ LIỆU.
                
                [LỊCH SỬ TRÒ CHUYỆN]:
                {history}
                
                [DỮ LIỆU NGUỒN]:
                {context_string}
                
                QUY TẮC:
                1. Trả lời NGẮN GỌN (dưới 100 từ) sử dụng các gạch đầu dòng. Tuyệt đối KHÔNG ghi 'Nguồn 1' hay '(1, 2)'.
                2. Dựa vào Lịch sử để hiểu các câu hỏi ngắn (ví dụ: 'Cần bằng cấp gì?').
                3. Nếu nguồn có bài 'Giải mã' hoặc 'Nghiên cứu', hãy dùng thông tin đó làm trọng tâm.
                4. Giọng văn dứt khoát, chuyên môn, không chào hỏi rườm rà.
                
                CÂU HỎI HIỆN TẠI: {prompt}"""

                # Gọi Gemini
                res_text = model.generate_content(sys_prompt).text
                
                # 3. Tạo phần Link tham khảo thông minh
                study_list = []
                normal_list = []
                seen_urls = set()

                for url, title in source_map.items():
                    if url != "#" and url not in seen_urls:
                        link_md = f"- 🔗 [{title}]({url})"
                        if any(kw in title.lower() for kw in study_keywords):
                            study_list.append(link_md)
                        else:
                            normal_list.append(link_md)
                        seen_urls.add(url)

                # Hiển thị tiêu đề link tùy theo loại dữ liệu tìm được
                header = "\n\n---\n**🔬 BẰNG CHỨNG KHOA HỌC & NGHIÊN CỨU:**\n" if study_list else "\n\n---\n**📚 TÀI LIỆU THAM KHẢO:**\n"
                
                # Lấy 2 link nghiên cứu + 2 link thường cho gọn
                final_links = study_list[:2] + normal_list[:2]
                final_res = res_text + header + "\n".join(final_links)
                
                st.markdown(final_res)
                
                # 4. Lưu vào bộ nhớ và cập nhật
                st.session_state.messages.append({"role": "assistant", "content": final_res})
                usage_db[user_key]["count"] += 1
                save_usage_data(usage_db)
                
                st.rerun()
                
# FORM ĐĂNG NHẬP SONG SONG (BÁC CẦN CÁI NÀY)
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập / Lấy thêm lượt (Dành cho Member)", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập", placeholder="Nhập username")
            p = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật mã")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("Đăng nhập", use_container_width=True):
                    if st.secrets["passwords"].get(u) == p:
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.rerun()
                    else: st.error("Sai rồi bác ơi!")
            with c2:
                st.markdown(f'<a href="https://zalo.me/84963759566" target="_blank" class="zalo-btn">💬 Lấy TK Zalo</a>', unsafe_allow_html=True)
