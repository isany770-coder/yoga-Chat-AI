import streamlit as st

# =====================================================
# 1. PAGE CONFIG - BẮT BUỘC ĐẦU TIÊN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. CSS - ÉP GIAO DIỆN TRẮNG & THANH TIẾN TRÌNH
# =====================================================
st.markdown("""
<style>
    /* Ép nền trắng tuyệt đối cho toàn bộ App */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #212121 !important;
    }
    
    /* Ẩn toolbar và footer */
    [data-testid="stToolbar"], header, footer {
        visibility: hidden !important;
        height: 0px !important;
    }

    /* THANH PROGRESS BAR CỐ ĐỊNH TRÊN CÙNG */
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
        font-size: 12px; color: #333; font-weight: bold;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 999998;
    }

    /* CHAT UI */
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa !important; border-radius: 15px; padding: 12px; margin-top: 25px;
    }
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd !important;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. IMPORT & CẤU HÌNH CLOUD
# =====================================================
import gdown
import zipfile
import os, re, json, datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# Thay ID file .zip 500MB của bác vào đây
FILE_ID_DRIVE = "1vOvvanNvDaLwP8Xs4nn1UhkciRvTxzyA" 
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
OUTPUT_ZIP = "/tmp/bo_nao_vector.zip"
EXTRACT_PATH = "/tmp/bo_nao_vector"

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Thiếu API KEY trong Secrets")
    st.stop()

# =====================================================
# 4. LOAD NÃO BỘ TỪ DRIVE (TỐI ƯU RAM)
# =====================================================
@st.cache_resource
def load_brain():
    if not os.path.exists(EXTRACT_PATH):
        try:
            with st.spinner("🚀 Đang nạp 500MB não bộ... Đợi tí nhé!"):
                # Tải file từ Drive
                gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False)
                # Giải nén
                with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                    zip_ref.extractall("/tmp/")
                # Xóa file zip ngay để tiết kiệm bộ nhớ server
                if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
        except Exception as e:
            st.error(f"Lỗi tải não: {e}")
            return None, None

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        return db, model
    except Exception as e:
        st.error(f"Lỗi khởi tạo AI: {e}")
        return None, None

db, model = load_brain()

# =====================================================
# 5. QUẢN LÝ LƯỢT DÙNG
# =====================================================
USAGE_DB_FILE = "/tmp/usage_database.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def load_usage():
    if not os.path.exists(USAGE_DB_FILE): return {}
    with open(USAGE_DB_FILE, "r") as f: return json.load(f)

def save_usage(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

# Khởi tạo session
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "guest_usage" not in st.session_state: st.session_state.guest_usage = 0
if "messages" not in st.session_state: st.session_state.messages = [{"role":"assistant","content":"Namaste! 🙏 Bạn cần hỗ trợ gì?"}]

# Tính lượt dùng
today = str(datetime.date.today())
db_usage = load_usage()
current_user = st.session_state.username if st.session_state.authenticated else "guest_default"

if current_user not in db_usage or db_usage[current_user]["date"] != today:
    db_usage[current_user] = {"date": today, "count": 0}
    save_usage(db_usage)

used = db_usage[current_user]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))

# HIỂN THỊ THANH TIẾN TRÌNH
st.markdown(f"""
    <div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div>
    <div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>
""", unsafe_allow_html=True)

# =====================================================
# 6. LOGIC CHAT
# =====================================================
can_chat = used < limit

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if can_chat:
    if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        st.rerun() # Rerun để hiện câu hỏi ngay

# Xử lý phản hồi AI (nằm ngoài block chat_input để tránh lag)
if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "user":
    last_prompt = st.session_state.messages[-1]["content"]
    with st.chat_message("assistant"):
        if db:
            docs = db.similarity_search(last_prompt, k=3)
            context = "\n".join([d.page_content for d in docs])
            
            sys_prompt = f"Bạn là chuyên gia Yoga. Dựa vào: {context}\nHãy trả lời câu hỏi: {last_prompt}\nYêu cầu: Ngắn gọn, dưới 100 từ, giọng thân thiện."
            
            res = model.generate_content(sys_prompt).text
            
            # Tăng lượt dùng và lưu
            db_usage[current_user]["count"] += 1
            save_usage(db_usage)
            
            # Gắn link tham khảo
            links = "\n\n---\n**📚 Tham khảo:**\n"
            for d in docs:
                if "url" in d.metadata: links += f"- 🔗 [{d.metadata.get('title','Tài liệu')}]({d.metadata['url']})\n"
            
            final_res = res + links
            st.markdown(final_content := final_res)
            st.session_state.messages.append({"role":"assistant","content":final_content})
            st.rerun()

# =====================================================
# 7. FORM ĐĂNG NHẬP (NẰM NGANG HÀNG)
# =====================================================
if not can_chat or not st.session_state.authenticated:
    st.markdown("---")
    with st.expander("🔐 Đăng nhập Thành viên / Lấy thêm lượt", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập")
            p = st.text_input("Mật khẩu", type="password")
            
            # Tạo 2 cột để đưa 2 nút nằm ngang hàng
            col_btn1, col_btn2 = st.columns([1, 1])
            
            with col_btn1:
                # Nút Submit mặc định của Streamlit
                if st.form_submit_button("Vào tập ngay", use_container_width=True):
                    if st.secrets["passwords"].get(u) == p:
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.rerun()
                    else:
                        st.error("Sai thông tin rồi bác ơi!")
            
            with col_btn2:
                # Nút Zalo giả lập giao diện nút Streamlit để nằm ngang hàng hoàn hảo
                st.markdown(f"""
                    <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: none;">
                        <div style="
                            background-color: white; 
                            color: #0f988b; 
                            border: 1px solid #0f988b;
                            padding: 8px 16px; 
                            border-radius: 8px; 
                            text-align: center; 
                            font-weight: 500;
                            font-size: 14px;
                            line-height: 1.6;
                            height: 38px;
                            transition: all 0.3s;
                        " onmouseover="this.style.background='#f0f9f8'" onmouseout="this.style.background='white'">
                            💬 Lấy TK Zalo
                        </div>
                    </a>
                """, unsafe_allow_html=True)

    # Hiển thị thêm thông báo nhỏ bên dưới nếu hết lượt
    if not can_chat and not st.session_state.authenticated:
        st.warning("⚡ Bạn đã dùng hết lượt dùng thử. Đăng nhập để tiếp tục hành trình Yoga nhé!")
