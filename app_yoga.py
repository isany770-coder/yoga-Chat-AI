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
    /* 1. Ép nền trắng và font chữ chuẩn */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #212121 !important;
    }
    
    /* 2. FIX MOBILE: Cố định thanh Input không bị trôi khi hiện bàn phím */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 10px !important; /* Đẩy lên 1 tí để không chạm viền dưới iPhone */
        left: 0;
        right: 0;
        z-index: 999999;
        background-color: rgba(255,255,255,0.9) !important;
        padding: 10px 1rem !important;
        border-top: 1px solid #f0f0f0;
    }

    /* 3. Tạo khoảng trống an toàn để không che nội dung cuối cùng */
    .main .block-container {
        padding-bottom: 150px !important; 
        padding-top: 2rem !important;
    }

    /* 4. Thanh Progress Bar & Lượt dùng */
    .usage-bar-container {
        position: fixed; top: 0; left: 0; width: 100%; height: 5px;
        background-color: #f0f0f0; z-index: 1000000;
    }
    .usage-bar-fill {
        height: 100%; 
        background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%);
        transition: width 0.5s ease-in-out;
    }
    .usage-text {
        position: fixed; top: 10px; right: 15px; 
        background: rgba(15, 152, 139, 0.1); padding: 4px 12px; border-radius: 20px;
        font-size: 11px; color: #0f988b; font-weight: bold;
        border: 1px solid #0f988b; z-index: 1000001;
    }

    /* 5. Ẩn các thành phần thừa của Streamlit */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
    }

    /* 6. Chỉnh Chat Message cho mượt trên Mobile */
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa !important; border-radius: 12px; 
        padding: 8px !important; margin-bottom: 10px !important;
    }
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
# 6. HIỂN THỊ CHAT & XỬ LÝ TRẢ LỜI (TỐI ƯU GIAO DIỆN)
# =====================================================

# --- Hiển thị lịch sử chat ---
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- Kiểm tra lượt dùng ---
can_chat = used < limit

if can_chat:
    if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
        # 1. Thêm tin nhắn người dùng
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Xử lý trả lời từ AI
        with st.chat_message("assistant"):
            if db:
                # Tìm kiếm tài liệu (k=5)
                docs = db.similarity_search(prompt, k=5)
                
                context_parts = []
                source_map = {} # Lọc link trùng
                
                for i, d in enumerate(docs):
                    t = d.metadata.get('title', 'Tài liệu Yoga')
                    u = d.metadata.get('url', '#')
                    context_parts.append(f"--- NGUỒN {i+1} ---\nTIÊU ĐỀ: {t}\nURL: {u}\nNỘI DUNG: {d.page_content}")
                    source_map[u] = t 

                context_string = "\n\n".join(context_parts)
                
                # System Prompt: Ép AI tập trung vào nguồn
                sys_prompt = (
                    f"Bạn là chuyên gia Yoga. Hãy trả lời dựa trên DỮ LIỆU NGUỒN.\n"
                    f"1. Trả lời NGẮN GỌN (tối đa 6-7 gạch đầu dòng, dưới 100 từ).\n"
                    f"2. Đi thẳng vào trọng tâm chuyên môn.\n"
                    f"3. Chỉ dùng thông tin có trong NGUỒN bên dưới.\n"
                    f"4. Tuyệt đối không tự bịa link hoặc chèn link vào bài viết.\n\n"
                    f"DỮ LIỆU NGUỒN:\n{context_string}\n\n"
                    f"CÂU HỎI: {prompt}"
                )

                # Gọi Gemini Flash
                res_text = model.generate_content(sys_prompt).text
                
                # 3. Tạo phần Tài liệu tham khảo (Unique links)
                links_html = "\n\n---\n**📚 Tài liệu tham khảo:**\n"
                seen_urls = set()
                count = 0
                for url, title in source_map.items():
                    if url != "#" and url not in seen_urls and count < 3:
                        links_html += f"- 🔗 [{title}]({url})\n"
                        seen_urls.add(url)
                        count += 1
                
                final_res = res_text + links_html
                st.markdown(final_res)
                
                # 4. Lưu vào bộ nhớ và cập nhật lượt dùng
                st.session_state.messages.append({"role": "assistant", "content": final_res})
                
                usage_db[user_key]["count"] += 1
                save_usage_data(usage_db)
                
                # Rerun để cập nhật UI
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
