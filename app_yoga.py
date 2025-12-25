import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import re
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS (CHUẨN UI/UX MOBILE)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* 1. XÓA BỎ THANH FOOTER RÁC (Built with Streamlit) */
    footer {display: none !important;}
    header {display: none !important;}

    /* 2. CỐ ĐỊNH DISCLAIMER Ở ĐÁY CÙNG (Làm mờ tinh tế) */
    .disclaimer-text {
        position: fixed !important;
        bottom: 5px !important;
        left: 0;
        width: 100%;
        text-align: center;
        color: #bbb;
        font-size: 10px;
        z-index: 999;
        pointer-events: none;
    }

    /* 3. NÂNG THANH CHAT & TRẢ LẠI KHUNG TRẮNG BO TRÒN XỊN SÒ */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 35px !important; /* Đẩy lên để không đè Disclaimer */
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 1000 !important;
        width: 95% !important;
        max-width: 800px !important;
        background-color: white !important; /* Trả lại nền trắng */
        border-radius: 30px !important; /* Trả lại khung bo tròn */
        border: 1px solid #e0e0e0 !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
        padding: 5px !important;
    }

    /* 4. CHÌA KHÓA: ĐẨY NỘI DUNG LÊN (FIX LỖI HỞ BỤNG & DÍNH CHỮ) */
    .stMainBlockContainer {
        padding-top: 1rem !important; /* Thu hẹp khoảng trống sau câu chào */
        padding-bottom: 180px !important; /* Đẩy nội dung qua mặt Input */
    }
    
    [data-testid="stChatMessage"] {
        margin-bottom: 10px !important;
    }

    /* 5. CÁC MỤC QUAN TRỌNG CỦA BÁC (GIỮ NGUYÊN 100%) */
    .promo-banner {
        background: linear-gradient(90deg, #e0f2f1 0%, #b2dfdb 100%);
        padding: 10px 15px; margin-bottom: 20px; border-radius: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #80cbc4;
    }
    .promo-text { color: #00695c; font-weight: bold; font-size: 14px; }
    .promo-btn {
        background-color: #00796b; color: white !important; padding: 6px 12px;
        border-radius: 15px; text-decoration: none; font-weight: bold; font-size: 12px;
        white-space: nowrap;
    }

    .limit-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(255, 255, 255, 0.95); z-index: 9999;
        display: flex; align-items: center; justify-content: center;
        flex-direction: column;
    }
    .limit-card {
        background: white; width: 90%; max-width: 400px;
        padding: 30px 20px; border-radius: 20px; text-align: center;
        border: 2px solid #26a69a; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .limit-icon { font-size: 50px; margin-bottom: 15px; display: block; }
    .limit-title { font-size: 18px; font-weight: bold; color: #00897b; margin-bottom: 10px; text-transform: uppercase; }
    .limit-desc { font-size: 14px; color: #555; line-height: 1.5; margin-bottom: 25px; }
    .zalo-btn-limit {
        display: block; width: 100%; padding: 12px;
        background-color: #009688; color: white !important;
        text-decoration: none; font-weight: bold; border-radius: 25px;
        margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0, 150, 136, 0.3);
    }
    .login-link { color: #00796b; font-size: 13px; cursor: pointer; text-decoration: underline;}

    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { display: block; color: #33691e; text-decoration: none; font-size: 14px; margin-bottom: 6px; padding: 5px; border-radius: 5px; transition: 0.2s; }
    .source-link:hover { background-color: #dcedc8; }
    .tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; text-transform: uppercase; border: 1px solid; }
    
    .bottom-spacer { height: 0px !important; } /* Xóa spacer cũ để tránh hở thêm */
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (CẤU HÌNH & DATA)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

# --- CẤU HÌNH ĐƯỜNG DẪN (Vẫn giữ v3 hoặc đổi v5 để ép tải lại nếu cần) ---
ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine():
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, None, "Lỗi tải dữ liệu từ Drive"
    
    # 2. Hàm tìm đường dẫn
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path):
                    return check_path
        return None

    text_db_path = find_db_path("vector_db")
    image_db_path = find_db_path("vector_db_images")
    
    if not text_db_path: return None, None, "Lỗi: Không tìm thấy não chữ (vector_db)"

    # 3. Load riêng biệt 2 não
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        
        # Não Chữ
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # Não Ảnh (Nếu có)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
            print("✅ Đã load thành công não ảnh riêng biệt!")

        model = genai.GenerativeModel('gemini-flash-latest')
        
        # TRẢ VỀ CẢ 2 NÃO RIÊNG BIỆT (KHÔNG GỘP)
        return (db_text, db_image), model, "OK"
    except Exception as e: return None, None, str(e)

# --- QUAN TRỌNG: CÁCH LẤY DỮ LIỆU RA ---
databases, model, status = load_brain_engine()
if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# Tách ra để dùng ở dưới
db_text, db_image = databases
# =====================================================
# 3. QUẢN LÝ USER & GIỚI HẠN
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    conn.commit(); conn.close()
init_db()

def check_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    res = c.fetchone(); conn.close()
    return res[0] if res else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý YIML AI.\nHôm nay chúng ta nên bắt đầu từ đâu?"}]

def get_user_id():
    if st.session_state.authenticated: return st.session_state.username
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        return _get_headers().get("X-Forwarded-For", "guest").split(",")[0]
    except: return "guest"

user_id = get_user_id()
used = check_usage(user_id)
LIMIT = 30 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# --- CHÈN THÊM ĐOẠN NÀY ĐỂ HIỆN THANH ĐẾM LƯỢT ---
percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""
<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;">
    <div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; 
                border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;">
        <span>⚡ {used}/{LIMIT}</span>
        <div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
# ------------------------------------------------

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (V15 - SIÊU BỀN, KHÔNG VỠ)
# =====================================================
if is_limit_reached:
    # 1. Logic nút Đóng (X)
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False
    
    # CSS để ẩn thanh chat input
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    # Nếu chưa bấm đóng, hiện màn hình thông báo
    if not st.session_state.hide_limit_modal:
        
        # --- LAYOUT CĂN GIỮA (Chìa khóa để không bị vỡ) ---
        # Chia màn hình làm 3 cột: [Lề trái] - [Nội dung chính] - [Lề phải]
        # Trên mobile cột giữa sẽ tự to ra, trên PC nó sẽ gọn lại.
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        
        with col_center:
            # Tạo một cái hộp có viền bo tròn (Native Streamlit)
            with st.container(border=True):
                
                # Nút X đóng (Dùng cột nhỏ bên trong để đẩy sang phải)
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕", help="Đóng để xem lại lịch sử"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
                # --- PHẦN HÌNH ẢNH & TEXT (HTML) ---
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử. Hãy quay lại vào ngày mai<br>
                            Để tra cứu <b>Kho dữ liệu 15 triệu từ</b> và nhận ưu đãi 
                            <b>Mua Thảm tặng Tài khoản Member</b>, mời bạn liên hệ Admin:
                        </p>
                        <a href="https://zalo.me/84963759566" target="_blank" 
                           style="display: inline-block; width: 100%; background-color: #009688; 
                                  color: white; padding: 12px 0; border-radius: 30px; 
                                  text-decoration: none; font-weight: bold; font-size: 16px;
                                  margin: 15px 0 25px 0; box-shadow: 0 4px 10px rgba(0,150,136,0.3);">
                           💬 Nhận mã kích hoạt qua Zalo
                        </a>
                        <div style="border-top: 1px dashed #ccc; margin: 10px 0;"></div>
                        <p style="font-size: 13px; color: #666; margin-top: 10px;">Hoặc đăng nhập thành viên:</p>
                    </div>
                """, unsafe_allow_html=True)

                # --- PHẦN FORM ĐĂNG NHẬP (Native Widget - Bấm bao nhạy) ---
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    
                    # Nút đăng nhập full width
                    btn_login = st.form_submit_button("Đăng Nhập Ngay", use_container_width=True)
                    
                    if btn_login:
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Đăng nhập thành công!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Sai tên đăng nhập hoặc mật khẩu")

        # Dừng app để người dùng tập trung vào thông báo
        st.stop()
    
    else:
        # TRẠNG THÁI ĐÃ BẤM ĐÓNG (CHỈ ĐỌC)
        st.markdown("""
        <div style="background:#ffebee; color:#c62828; padding:12px; text-align:center; border-radius:12px; margin-bottom:15px; border:1px solid #ffcdd2; font-weight: 500;">
            🚫 Bạn đang xem ở chế độ chỉ đọc. <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: underline; color: #b71c1c;">Nâng cấp ngay</a> để tiếp tục hỏi.
        </div>
        """, unsafe_allow_html=True)
# =====================================================
# 5. GIAO DIỆN CHAT & XỬ LÝ (CÓ LƯU LẠI ẢNH)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Freeship + tài khoản VIP giảm 30%!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# --- VÒNG LẶP HIỂN THỊ LỊCH SỬ (BẢN SẠCH - CHỈ HIỆN 1 LẦN) ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # 1. Hiện nội dung chữ (đã bao gồm nguồn + upsell)
        st.markdown(msg["content"], unsafe_allow_html=True)
        
        # 2. Hiện lại ảnh (CHỈ GIỮ 1 KHỐI CODE NÀY THÔI)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            st.markdown("##### 🖼️ Minh họa chi tiết:")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                with cols[i % 3]:
                    # Thumbnail
                    st.markdown(f"""<div style="height:150px;overflow:hidden;border-radius:10px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;background:#f9f9f9;"><img src="{img['url']}" style="width:100%;height:100%;object-fit:cover;"></div>""", unsafe_allow_html=True)
                    # Zoom
                    with st.expander(f"🔍 Phóng to {i+1}"):
                        st.image(img['url'], caption=img['title'], use_container_width=True)
                        st.markdown(f"[Tải ảnh]({img['url']})")

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Gợi ý giải pháp (Upsell)
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","đau lưng","gối","đau gối","cột sống","thoát vị","thoát vị đĩa đệm","tim mạch","tim","huyết áp","cao huyết áp","hạ huyết áp","tuần hoàn","mạch máu","đau ngực","suy nhược"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","tập sai","lỗi sai","sai kỹ thuật","kỹ thuật","đúng kỹ thuật","chỉnh tư thế","canh chỉnh","căn chỉnh","hướng dẫn","định tuyến","quy trình","trình tự","bước thực hiện","chuẩn hóa","tối ưu","hiệu chỉnh","điều chỉnh","sửa lỗi","khắc phục"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress","căng thẳng","áp lực","lo âu","bất an","mệt mỏi tinh thần","ngủ","giấc ngủ","mất ngủ","ngủ sâu","ngủ không ngon","nghỉ ngơi","thiền","thiền định","chánh niệm","tĩnh tâm","an trú","thở","hít thở","điều hòa hơi thở"]}
}

# =====================================================
# 6. XỬ LÝ CHAT (ĐÃ BỎ BỘ LỌC CHẶT)
# =====================================================
# --- HÀM MỚI: LỌC LỊCH SỬ CHAT (BỎ HTML ĐỂ AI KHÔNG BỊ LOẠN) ---
def get_clean_history():
    """Lấy 4 câu hội thoại gần nhất, lọc bỏ code HTML"""
    history_text = ""
    # Lấy 4 tin nhắn cuối cùng (bỏ qua tin nhắn chào hỏi đầu tiên nếu muốn)
    recent_msgs = st.session_state.messages[-4:] 
    for msg in recent_msgs:
        role = "User" if msg["role"] == "user" else "AI"
        # Xóa các thẻ HTML như <div>, <a>, <br>... chỉ giữ lại chữ
        clean_content = re.sub(r'<[^>]+>', '', msg["content"]) 
        history_text += f"{role}: {clean_content}\n"
    return history_text
# -------------------------------------------------------------
# =====================================================
# 6. XỬ LÝ CHAT (CÓ CHẶN SPAM & CÂU HỎI NGOÀI LỀ)
# =====================================================

# --- A. KHỞI TẠO BIẾN TRẠNG THÁI (Nếu chưa có) ---
if "spam_count" not in st.session_state: 
    st.session_state.spam_count = 0
if "lock_until" not in st.session_state: 
    st.session_state.lock_until = None

# --- B. KIỂM TRA TRẠNG THÁI KHÓA ---
is_locked = False
if st.session_state.lock_until:
    if time.time() < st.session_state.lock_until:
        is_locked = True
        remaining = int((st.session_state.lock_until - time.time()) / 60)
        st.warning(f"⚠️ Bạn đã vi phạm quy định nội dung. Khung chat sẽ mở lại sau {remaining + 1} phút.")
    else:
        # Tự động mở khóa sau khi hết thời gian
        st.session_state.lock_until = None
        st.session_state.spam_count = 0

# --- C. LOGIC XỬ LÝ CHAT CHÍNH (CHUẨN: LỌC TRÙNG & BIẾN AN TOÀN) ---
if not is_locked:
    if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        increment_usage(user_id)

        with st.chat_message("assistant"):
            with st.spinner("Đang tra cứu từ kho dữ liệu..."):
                try:
                    # --- BƯỚC 1: TRA CỨU SÂU (DEEP RETRIEVAL) ---
                    # 1. Tăng số lượng tìm kiếm Text lên 15 để đào sâu vào kho PubMed 200MB
                    docs_text = db_text.similarity_search(prompt, k=8)
                    
                    # 2. Tìm ảnh (Lấy rộng ra để AI có nhiều lựa chọn)
                    docs_img = []
                    if db_image:
                        docs_img = db_image.similarity_search(prompt, k=4)
                    
                    history_text = get_clean_history()

                    context_text_prompt = ""
                    context_img_prompt = ""
                    
                    source_map = {}
                    image_map = {} 

                    # A. Xử lý Text Sources
                    current_id = 1
                    for d in docs_text:
                        url = d.metadata.get('url', '#')
                        title = d.metadata.get('title', 'Tài liệu Y Khoa')
                        source_map[current_id] = {"url": url, "title": title}
                        # Gắn nhãn rõ ràng để AI biết đây là dữ liệu chuyên môn
                        context_text_prompt += f"[Nguồn {current_id}]: {title}\nNội dung: {d.page_content}\n----------------\n"
                        current_id += 1

                    # B. Xử lý Image Candidates (LỌC TRÙNG KÉP: URL + TIÊU ĐỀ)
                    img_start_id = 100
                    seen_img_keys = set() # Dùng key là (URL + Title) để lọc triệt để
                    
                    for d in docs_img:
                        img_url = d.metadata.get('image_url', '')
                        img_title = d.metadata.get('title', 'Ảnh minh họa')
                        
                        # Tạo khóa định danh duy nhất cho ảnh
                        unique_key = f"{img_url}_{img_title}"
                        
                        if img_url and unique_key not in seen_img_keys:
                            image_map[img_start_id] = {"url": img_url, "title": img_title}
                            context_img_prompt += f"[ID: {img_start_id}] {img_title}\n"
                            seen_img_keys.add(unique_key)
                            img_start_id += 1

                    # --- BƯỚC 2: TẠO PROMPT CHUYÊN GIA PUBMED ---
                    sys_prompt = f"""
                    Bạn là Chuyên gia Yoga Trị liệu (YIML AI), được huấn luyện trên dữ liệu Y khoa PubMed.
                    
                    1. DỮ LIỆU NGHIÊN CỨU (TEXT):
                    {context_text_prompt}
                    
                    2. KHO ẢNH (IMAGE):
                    {context_img_prompt}

                    3. LỊCH SỬ: {history_text}

                    4. NHIỆM VỤ:
                    Dựa vào "Dữ liệu nghiên cứu", hãy trả lời câu hỏi: "{prompt}"
                    
                    5. YÊU CẦU NGHIÊM NGẶT:
                    - **Dữ liệu:** Ưu tiên tuyệt đối thông tin từ mục (1). Nếu tìm thấy thông tin khớp (ví dụ bài tập cho bệnh lý cụ thể), hãy trích dẫn `[1]`, `[2]`.
                    - **Nếu không tìm thấy:** Nếu dữ liệu mục (1) hoàn toàn không liên quan đến câu hỏi (ví dụ hỏi Lưng ra bài Mất ngủ), hãy tự trả lời bằng kiến thức chuẩn y khoa của bạn và **KHÔNG** bịa số nguồn.
                    - **Hình ảnh (QUAN TRỌNG):** Chọn **DUY NHẤT 1 ẢNH** khớp nhất, chính xác nhất từ mục (2). Nếu không có ảnh nào thực sự đúng, hãy bỏ qua.
                    - **Trình bày:** Gạch đầu dòng (-), In đậm (**từ khóa**), Ngắn gọn không quá 150 từ.

                    6. OUTPUT FORMAT:
                    [Nội dung trả lời...]
                    
                    |||IMAGES|||
                    [ID của 1 ảnh duy nhất]
                    """

                    # --- BƯỚC 3: XỬ LÝ KẾT QUẢ ---
                    response = model.generate_content(sys_prompt)
                    raw_resp = response.text.strip()

                    if "OFFTOPIC" in raw_resp.upper():
                        st.warning("Vui lòng đặt câu hỏi liên quan đến Yoga & Sức khỏe.")
                    else:
                        parts = raw_resp.split("|||IMAGES|||")
                        main_content = parts[0].strip()
                        
                        # 1. Xử lý Ảnh: CHỈ LẤY 1 ẢNH ĐẦU TIÊN (Strict Mode)
                        selected_images = []
                        if len(parts) > 1:
                            img_part = parts[1].strip()
                            found_ids = re.findall(r'\d+', img_part)
                            for fid in found_ids:
                                fid = int(fid)
                                if fid in image_map:
                                    selected_images.append(image_map[fid])
                                    break # <--- LỆNH QUAN TRỌNG: Tìm thấy 1 cái là dừng ngay.

                        # 2. Hiển thị Text
                        st.markdown(main_content)

                        # 3. Hiển thị 1 Ảnh duy nhất (To & Rõ)
                        if selected_images:
                            img = selected_images[0]
                            st.markdown("---")
                            st.markdown("##### 🖼️ Minh họa:")
                            # Hiển thị ảnh to full cột
                            st.image(img['url'], caption=f"Minh họa: {img['title']}", use_container_width=True)

                        # 4. Hiển thị Nguồn (Chỉ hiện nguồn ĐÚNG)
                        used_ref_ids = set([int(m) for m in re.findall(r'\[(\d+)\]', main_content)])
                        html_src = ""
                        if used_ref_ids:
                            valid_sources = []
                            seen_links = set()
                            for uid in used_ref_ids:
                                if uid in source_map:
                                    src = source_map[uid]
                                    if src['url'] != '#' and src['url'] not in seen_links:
                                        valid_sources.append(src)
                                        seen_links.add(src['url'])
                            
                            if valid_sources:
                                html_src = "<div class='source-box'><b>📚 Nghiên cứu tham khảo:</b><br>"
                                for src in valid_sources:
                                    html_src += f"• <a href='{src['url']}' target='_blank' class='source-link' style='display:inline;'>{src['title']}</a><br>"
                                html_src += "</div>"
                                st.markdown(html_src, unsafe_allow_html=True)

                        # 5. Upsell & Save
                        upsell_html = ""
                        recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                        if recs:
                            upsell_html += "<div style='margin-top:15px'>"
                            for r in recs[:2]:
                                 upsell_html += f"""<div style="background:#e0f2f1; padding:10px; border-radius:10px; margin-bottom:8px; border:1px solid #009688; display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:bold; color:#004d40; font-size:14px">{r['name']}</span><a href="{r['url']}" target="_blank" style="background:#00796b; color:white; padding:5px 10px; border-radius:15px; text-decoration:none; font-size:12px; font-weight:bold;">Xem ngay</a></div>"""
                            upsell_html += "</div>"
                            st.markdown(upsell_html, unsafe_allow_html=True)

                        full_content_to_save = main_content
                        if html_src: full_content_to_save += "\n\n" + html_src
                        if upsell_html: full_content_to_save += "\n\n" + upsell_html
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_content_to_save,
                            "images": selected_images
                        })
                except Exception as e:
                    st.error(f"Lỗi: {e}")

                    # =====================================================
# 7. DISCLAIMER (CHÂN TRANG CỐ ĐỊNH)
# =====================================================
st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót, vì vậy, nhớ xác minh câu trả lời.</div>', unsafe_allow_html=True)
