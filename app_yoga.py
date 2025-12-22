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
    /* 1. CẤU HÌNH RESET (ÉP MÀU CHỮ ĐEN TUYỆT ĐỐI) */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #31333F !important; /* Màu đen xám chuẩn dễ đọc */
    }
    
    /* Ép tất cả văn bản, tiêu đề về màu đen */
    p, h1, h2, h3, h4, h5, h6, span, div, label {
        color: #31333F !important;
    }

    /* Ẩn header/footer */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
    }

    /* 2. CHAT INPUT "NỔI" - FIX MÀU NỀN & MÀU CHỮ */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: calc(20px + env(safe-area-inset-bottom)) !important;
        left: 10px !important; right: 10px !important;
        width: auto !important;
        z-index: 999999;
        background-color: white !important; /* Nền trắng tuyệt đối */
        border-radius: 25px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        padding: 5px !important;
        border: 1px solid #e0e0e0;
    }

    /* Xử lý ô nhập liệu: Chữ đen, Nền xám nhạt */
    textarea[data-testid="stChatInputTextArea"] {
        font-size: 16px !important;
        color: #333333 !important; /* CHỮ MÀU ĐEN ĐẬM */
        -webkit-text-fill-color: #333333 !important; /* Fix lỗi trên iPhone */
        background-color: #f0f2f6 !important; /* Nền xám nhẹ để nổi bật */
        border-radius: 20px !important;
        caret-color: #0f988b !important; /* Con trỏ chuột màu xanh */
    }
    
    /* Placeholder (chữ gợi ý) màu xám rõ ràng */
    textarea[data-testid="stChatInputTextArea"]::placeholder {
        color: #888 !important;
        opacity: 1 !important;
    }

    /* Nút Gửi */
    button[data-testid="stChatInputSubmit"] {
        background-color: #0f988b !important;
        color: white !important;
        border-radius: 50% !important;
        right: 10px !important; bottom: 8px !important;
    }
    button[data-testid="stChatInputSubmit"] svg {
        fill: white !important; /* Mũi tên màu trắng */
    }

    /* 3. TIN NHẮN CHAT */
    div[data-testid="stChatMessage"] {
        background-color: #f8f9fa !important; 
        border: 1px solid #eee;
    }
    /* Bong bóng chat của người dùng */
    div[data-testid="stChatMessage"][data-test-role="user"] {
        background-color: #e3f2fd !important;
    }

    /* 4. CÁC THÀNH PHẦN KHÁC (THANH BAR, BUTTON) */
    .usage-bar-container {
        position: fixed; top: 0; left: 0; width: 100%; height: 5px;
        background-color: #f0f0f0; z-index: 1000000;
    }
    .usage-bar-fill {
        height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%);
    }
    .usage-text {
        position: fixed; top: 10px; right: 15px; 
        background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px;
        font-size: 11px; color: #0f988b !important; font-weight: bold;
        border: 1px solid #0f988b; z-index: 1000001;
    }
    
    .main .block-container {
        padding-top: 3rem !important;
        padding-bottom: 180px !important;
    }

    /* Nút Zalo & Login */
    .zalo-btn {
        display: flex !important; align-items: center; justify-content: center;
        width: 100%; background-color: white; color: #0f988b !important;
        border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px;
        height: 45px !important; text-decoration: none !important; box-sizing: border-box !important; margin: 0 !important;
    }
    div[data-testid="stForm"] button {
        height: 45px !important; border-radius: 8px !important; font-weight: 500 !important;
        color: #31333F !important; /* Chữ nút đen */
    }
    /* =============================================
       6. MODAL HẾT LƯỢT (Z-INDEX CAO NHẤT VŨ TRỤ)
       ============================================= */
    .limit-modal {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(255, 255, 255, 0.95); /* Nền trắng mờ che hết nội dung */
        backdrop-filter: blur(10px);
        z-index: 2147483647 !important; /* Cao hơn cả thanh chat */
        display: flex; align-items: center; justify-content: center;
        flex-direction: column;
    }
    .limit-box {
        background: white; padding: 40px; border-radius: 25px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        text-align: center; max-width: 90%; width: 400px;
        border: 2px solid #0f988b;
        animation: popup 0.5s cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }
    @keyframes popup { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
    
    .limit-icon { font-size: 60px; margin-bottom: 20px; }
    .limit-title { font-size: 24px; font-weight: 800; color: #ff6b6b; margin-bottom: 10px; }
    .limit-desc { color: #333; margin-bottom: 25px; line-height: 1.6; font-size: 16px; }
    
    /* Nút liên hệ Admin */
    .limit-btn {
        background: linear-gradient(135deg, #0f988b, #14b8a6);
        color: white !important; padding: 12px 35px; border-radius: 50px;
        text-decoration: none; font-weight: bold; display: inline-block;
        box-shadow: 0 5px 15px rgba(15, 152, 139, 0.4);
        transition: transform 0.2s;
    }
    .limit-btn:hover { transform: translateY(-3px); }
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
# 5. QUẢN LÝ LƯỢT DÙNG (AUTO-RESET MỖI NGÀY)
# =====================================================
USAGE_DB_FILE = "/tmp/usage_db_v2.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_usage_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    try:
        with open(USAGE_DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_usage_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

# Khởi tạo trạng thái đăng nhập
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state: st.session_state.messages = [{"role":"assistant","content":"Namaste! 🙏 Thật vui được gặp bạn. Hôm nay chúng ta sẽ bắt đầu từ đâu?"}]

# --- LOGIC RESET TỰ ĐỘNG ---
today = str(datetime.date.today())
usage_db = get_usage_data()
user_key = st.session_state.username if st.session_state.authenticated else "anonymous_guest"

# Nếu user chưa tồn tại HOẶC ngày trong file khác với ngày hôm nay -> RESET
if user_key not in usage_db or usage_db[user_key].get("date") != today:
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
# 6. HIỂN THỊ CHAT & XỬ LÝ TRẢ LỜI (FULL LOGIC)
# =====================================================

# --- 1. Hiển thị lịch sử chat ---
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 2. KIỂM TRA GIỚI HẠN - CHẶN NẾU HẾT LƯỢT ---
# Đây là phần quan trọng để hiện Modal và chặn Hack
if used >= limit:
    st.markdown(f"""
    <div class="limit-modal">
        <div class="limit-box">
            <div class="limit-icon">🧘‍♀️</div>
            <div class="limit-title">Đã hết năng lượng!</div>
            <div class="limit-desc">
                Bạn đã dùng hết <b>{limit} câu hỏi</b> miễn phí hôm nay.<br>
                Hãy đăng nhập hoặc liên hệ Admin để mở khóa không giới hạn nhé!
            </div>
            <a href="https://zalo.me/84963759566" target="_blank" class="limit-btn">💬 Liên hệ Admin ngay</a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop() # Dừng chương trình ngay lập tức, không hiện ô chat bên dưới

# --- 3. XỬ LÝ CHAT (NẾU CÒN LƯỢT) ---
if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
    # A. TĂNG LƯỢT DÙNG NGAY LẬP TỨC (Trừ tiền trước, nói chuyện sau)
    usage_db[user_key]["count"] += 1
    save_usage_data(usage_db)
    
    # B. Hiển thị tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # C. AI Trả lời
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
            
            # System Prompt: (Giữ nguyên theo ý bác)
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
            try:
                res_text = model.generate_content(sys_prompt).text
                
                # Tạo phần Tài liệu tham khảo (Giữ nguyên logic của bác)
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
                
                # Lưu vào bộ nhớ
                st.session_state.messages.append({"role": "assistant", "content": final_res})
                
                # Rerun để cập nhật thanh Progress Bar trên cùng ngay lập tức
                st.rerun()
                
            except Exception as e:
                st.error("AI đang thở gấp, thử lại sau nhé!")
                
# FORM ĐĂNG NHẬP SONG SONG - ĐÃ FIX LỆCH NÚT
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập / Lấy thêm lượt (Dành cho Member)", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập", placeholder="Username")
            p = st.text_input("Mật khẩu", type="password", placeholder="Password")
            
            # Tạo khoảng trống nhẹ để nút không dính vào ô Password
            st.write("") 
            
            c1, c2 = st.columns(2)
            with c1:
                submit = st.form_submit_button("Đăng nhập", use_container_width=True)
            with c2:
                # Bọc trong div để kiểm soát margin tuyệt đối
                st.markdown(f"""
                    <div style="margin-top: 0px;">
                        <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: none;">
                            <div class="zalo-btn">💬 Lấy TK Zalo</div>
                        </a>
                    </div>
                """, unsafe_allow_html=True)

            if submit:
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.rerun()
                else: 
                    st.error("Sai rồi bác ơi!")
