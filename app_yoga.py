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
# 6. HIỂN THỊ CHAT & FORM ĐĂNG NHẬP SONG SONG
# =====================================================
can_chat = used < limit

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if can_chat:
    if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        st.rerun()

# Xử lý trả lời AI
if st.session_state.messages[-1]["role"] == "user":
    last_prompt = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        if db:
            docs = db.similarity_search(last_prompt, k=3)
            context = "\n".join([d.page_content for d in docs])
            sys_prompt = f"Bạn là chuyên gia Yoga. Dựa vào: {context}\n1. Trả lời CỰC KỲ NGẮN GỌN (Tối đa 5-6 gạch đầu dòng).
                2. Tổng độ dài KHÔNG QUÁ 100 TỪ.
                3. Đi thẳng vào trọng tâm, bỏ qua lời dẫn dắt vô nghĩa.
                4. Giọng văn thân thiện, dứt khoát.
                5. KHÔNG tự chèn link (Hệ thống sẽ tự làm).: {last_prompt}"
            
            res = model.generate_content(sys_prompt).text
            
            # Lưu lượt dùng
            usage_db[user_key]["count"] += 1
            save_usage_data(usage_db)
            
            links = "\n\n---\n**📚 Tham khảo:**\n"
            for d in docs:
                if "url" in d.metadata: links += f"- 🔗 [{d.metadata.get('title','Tài liệu')}]({d.metadata['url']})\n"
            
            st.markdown(final_res := res + links)
            st.session_state.messages.append({"role":"assistant","content":final_res})
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
                if st.form_submit_button("Vào tập ngay", use_container_width=True):
                    if st.secrets["passwords"].get(u) == p:
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.rerun()
                    else: st.error("Sai rồi bác ơi!")
            with c2:
                st.markdown(f'<a href="https://zalo.me/84963759566" target="_blank" class="zalo-btn">💬 Lấy TK Zalo</a>', unsafe_allow_html=True)
