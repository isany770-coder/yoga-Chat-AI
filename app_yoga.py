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
from gtts import gTTS
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder
import io

# =====================================================
# 1. CẤU HÌNH TRANG & CSS (GIỮ NGUYÊN BẢN GỐC CỦA BẠN)hỏi
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* 1. Ẩn Header/Footer thừa */
    header[data-testid="stHeader"], footer, .stDeployButton { display: none !important; }
    
    /* 2. Tinh chỉnh khoảng cách nội dung (Để không bị thanh chat che) */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 150px !important; /* Khoảng trống an toàn dưới đáy */
    }

    /* 3. TẠO CHỖ TRỐNG TRONG Ô NHẬP LIỆU (Để nút Mic không che chữ) */
    /* Chúng ta không can thiệp vị trí khung chat, chỉ can thiệp nội dung bên trong */
    [data-testid="stChatInput"] textarea {
        padding-right: 60px !important; /* Thụt lề phải text để chừa chỗ cho mic */
    }

    /* 4. ĐỊNH VỊ NÚT MIC (Nổi lên trên mọi thứ) */
    .mic-floating {
        position: fixed;
        z-index: 99999 !important;
        bottom: 25px; /* Canh chỉnh theo chiều cao mặc định của thanh chat */
        
        /* MẶC ĐỊNH (DESKTOP): Căn giữa + Dịch sang phải */
        left: 50%;
        transform: translateX(340px); /* 800px/2 - 60px */
        
        width: 40px;
        height: 40px;
        display: flex; align-items: center; justify-content: center;
        pointer-events: auto; /* Đảm bảo bấm được */
    }

    /* Style nút bấm cho đẹp */
    .mic-floating button {
        background: transparent !important;
        border: none !important;
        color: #e11d48 !important; 
        font-size: 1.4rem !important;
        padding: 0 !important; margin: 0 !important;
        width: 100% !important; height: 100% !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
    }
    .mic-floating button:hover {
        background: rgba(225, 29, 72, 0.1) !important;
        border-radius: 50%;
        transform: scale(1.1);
    }

    /* 5. MOBILE (Màn hình nhỏ) */
    @media (max-width: 800px) {
        .mic-floating {
            left: auto !important;
            transform: none !important;
            right: 60px !important; /* Ghim chặt vào bên phải, cạnh nút Gửi */
            bottom: 22px !important; /* Tinh chỉnh lại chút cho khớp mobile */
        }
    }
    /* 5. CÁC THÀNH PHẦN KHÁC (GIỮ NGUYÊN) */
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
    
    .bottom-spacer { height: 0px !important; } /* Đã xử lý ở block-container rồi nên cái này về 0 */
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (ĐÃ SỬA: CHỈ LOAD DATA, KHÔNG LOAD MODEL GÂY LỖI)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

# --- CẤU HÌNH ĐƯỜNG DẪN (GIỮ NGUYÊN) ---
ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine_safe():
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu từ Drive"
    
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
    
    if not text_db_path: return None, "Lỗi: Không tìm thấy não chữ (vector_db)"

    # 3. Load riêng biệt 2 não (KHÔNG GỌI MODEL Ở ĐÂY ĐỂ TRÁNH SẬP APP)
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        
        # Não Chữ
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # Não Ảnh (Nếu có)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # CHỈ TRẢ VỀ DB, KHÔNG TRẢ VỀ MODEL
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

# --- GỌI HÀM LOAD (ĐÃ SỬA LẠI CÁCH GỌI) ---
data_result, status = load_brain_engine_safe()

if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# Tách ra để dùng ở dưới
db_text, db_image = data_result

# --- HÀM XỬ LÝ GIỌNG NÓI ---
def text_to_speech(text):
    """Chuyển chữ thành giọng nói chị Google"""
    try:
        # Xóa các ký tự thừa để đọc cho mượt
        clean_text = re.sub(r'\[.*?\]', '', text) # Bỏ phần [Ref: 1]
        clean_text = clean_text.replace('*', '').replace('#', '')
        
        tts = gTTS(text=clean_text, lang='vi')
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return audio_bytes
    except: return None

def speech_to_text(audio_bytes):
    """Chuyển file ghi âm thành chữ"""
    r = sr.Recognizer()
    try:
        # Cần lưu tạm file để thư viện đọc được
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_bytes)
            
        with sr.AudioFile("temp_audio.wav") as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language="vi-VN")
            return text
    except: return None

# =====================================================
# 3. QUẢN LÝ USER & GIỚI HẠN (GIỮ NGUYÊN BẢN GỐC)
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
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga.\nBạn cần tìm bài tập hay tư vấn bệnh lý gì hôm nay?"}]

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

# --- THANH ĐẾM LƯỢT ---
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

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (GIỮ NGUYÊN BẢN GỐC - KHÔNG SỬA)
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False
    
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    if not st.session_state.hide_limit_modal:
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        with col_center:
            with st.container(border=True):
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
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

                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
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
        st.stop()

# =====================================================
# 5. HIỂN THỊ LỊCH SỬ CHAT (GIỮ NGUYÊN)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Freeship + tài khoản VIP giảm 30%!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            st.markdown("##### 🖼️ Minh họa chi tiết:")
            cols = st.columns(3)
            for i, img in enumerate(msg["images"]):
                col = cols[i % 3]
                with col:
                    st.markdown(f"""<div style="height:150px;overflow:hidden;border-radius:10px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;background:#f9f9f9;"><img src="{img['url']}" style="width:100%;height:100%;object-fit:cover;"></div>""", unsafe_allow_html=True)
                    with st.expander(f"🔍 Phóng to {i+1}"):
                        st.image(img['url'], caption=img['title'], use_container_width=True)
                        st.markdown(f"[Tải ảnh]({img['url']})")

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Upsell Dictionary
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","đau lưng","gối","đau gối","cột sống","thoát vị","thoát vị đĩa đệm","tim mạch","tim","huyết áp","cao huyết áp","hạ huyết áp","tuần hoàn","mạch máu","đau ngực","suy nhược"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","tập sai","lỗi sai","sai kỹ thuật","kỹ thuật","đúng kỹ thuật","chỉnh tư thế","canh chỉnh","căn chỉnh","hướng dẫn","định tuyến","quy trình","trình tự","bước thực hiện","chuẩn hóa","tối ưu","hiệu chỉnh","điều chỉnh","sửa lỗi","khắc phục"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress","căng thẳng","áp lực","lo âu","bất an","mệt mỏi tinh thần","ngủ","giấc ngủ","mất ngủ","ngủ sâu","ngủ không ngon","nghỉ ngơi","thiền","thiền định","chánh niệm","tĩnh tâm","an trú","thở","hít thở","điều hòa hơi thở"]}
}

# =====================================================
# 6. XỬ LÝ CHAT & GIỌNG NÓI (GIAO DIỆN PRO V3)
# =====================================================

# --- A. BIẾN TRẠNG THÁI ---
if "spam_count" not in st.session_state: st.session_state.spam_count = 0
if "lock_until" not in st.session_state: st.session_state.lock_until = None

# --- B. KIỂM TRA KHÓA ---
is_locked = False
if st.session_state.lock_until:
    if time.time() < st.session_state.lock_until:
        is_locked = True
        remaining = int((st.session_state.lock_until - time.time()) / 60)
        st.warning(f"⚠️ Bạn đã thao tác quá nhanh. Vui lòng đợi {remaining + 1} phút.")
    else:
        st.session_state.lock_until = None; st.session_state.spam_count = 0

# --- C. CSS "MA THUẬT" ĐỂ ĐẨY NÚT MIC VÀO INPUT ---
st.markdown("""
<style>
    /* 1. Tạo vùng chứa cho nút Mic, ghim cứng góc dưới phải */
    .mic-floating-container {
        position: fixed;
        bottom: 28px; /* Canh độ cao trùng với thanh input */
        right: 70px;  /* Cách lề phải 70px (để tránh nút Gửi của Streamlit) */
        z-index: 1001; /* Nổi lên trên cùng */
        display: flex;
        align-items: center;
        justify-content: center;
        background: transparent;
    }

    /* 2. Tùy chỉnh cái nút của thư viện mic-recorder */
    .mic-floating-container button {
        background-color: transparent !important; /* Làm nền trong suốt */
        border: none !important;
        color: #e11d48 !important; /* Màu đỏ cho icon mic */
        padding: 5px !important;
        font-size: 1.2rem !important;
        transition: transform 0.2s;
    }
    
    /* Hiệu ứng khi di chuột */
    .mic-floating-container button:hover {
        transform: scale(1.2);
        background-color: rgba(225, 29, 72, 0.1) !important;
        border-radius: 50%;
    }

    /* 3. Đẩy nội dung chat input sang trái xíu để không bị mic che chữ (nếu gõ dài) */
    .stChatInput textarea {
        padding-right: 50px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- D. GIAO DIỆN MICRO & INPUT ---
voice_text = None

if not is_locked:
    # 1. Vẽ nút Mic (Nó sẽ tự bay xuống dưới nhờ CSS ở trên)
    # Bác chú ý: start_prompt là icon Mic, stop_prompt là icon Dừng
    with st.container():
        st.markdown('<div class="mic-fixed-container">', unsafe_allow_html=True)
        audio_data = mic_recorder(
            start_prompt="🎙️", 
            stop_prompt="🟥", 
            just_once=True,
            key='voice_recorder_pro'
        )
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 2. Xử lý Audio nếu có
    if audio_data:
        with st.spinner("🎧 Đang dịch giọng nói..."):
            transcribed = speech_to_text(audio_data['bytes'])
            if transcribed:
                voice_text = transcribed
            else:
                st.toast("❌ Ồn quá, bác nói lại to hơn chút nhé!")

# --- E. XỬ LÝ CHAT (Logic cũ giữ nguyên) ---
# Ưu tiên lấy text từ giọng nói, nếu không thì lấy từ ô chat
user_input = voice_text if voice_text else st.chat_input("Hỏi tôi bất cứ điều gì về Yoga, sức khỏe...")

if user_input and not is_locked:
    # Hiển thị câu hỏi
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    increment_usage(user_id)

    # ... (Phần logic gọi Gemini và trả lời giữ nguyên như cũ) ...
    # Bác copy đoạn logic xử lý assistant response ở code cũ dán vào đây
    # Hoặc nếu bác cần tôi viết lại đoạn đó thì bảo nhé!
    with st.chat_message("assistant"):
        with st.spinner("🧘 Đang suy nghĩ..."):
            try:
                # --- TỰ ĐỘNG TÌM MODEL SỐNG ---
                valid_model = 'models/gemini-pro'
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            if 'flash' in m.name or 'pro' in m.name:
                                valid_model = m.name; break
                except: pass
                
                model = genai.GenerativeModel(valid_model)
                
                # ... (Phần tìm kiếm Vector DB giữ nguyên) ...
                docs_text = db_text.similarity_search(user_input, k=6)
                docs_img = []
                if db_image: docs_img = db_image.similarity_search(user_input, k=2)
                docs = docs_text + docs_img
                
                context_text = ""
                source_map = {}
                found_images = []

                for i, d in enumerate(docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu Yoga')
                    type_ = d.metadata.get('type', 'blog')
                    img_url = d.metadata.get('image_url', '')
                    source_map[doc_id] = {"url": url, "title": title, "type": type_}
                    
                    if type_ == 'image' and img_url:
                        found_images.append({"url": img_url, "title": title})
                        context_text += f"\n[Nguồn {doc_id} - HÌNHẢNH]: {title}.\nNội dung ảnh: {d.page_content}\n"
                    else:
                        context_text += f"\n[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                sys_prompt = f"""
                Bạn là chuyên gia Yoga. DỮ LIỆU: {context_text}. CÂU HỎI: "{user_input}".
                YÊU CẦU:
                    - Nếu câu hỏi KHÔNG liên quan đến Yoga/Sức khỏe: trả lời "OFFTOPIC".
                    - Trả lời đúng trọng tâm.
                    - Ưu tiên. Kiểm tra dữ liệu: Nếu có [HÌNH ẢNH], hãy mời xem ảnh bên dưới. Ghi nguồn [Ref: X].
                    - Nếu dữ liệu không khớp, tự trả lời bằng kiến thức Yoga chuẩn (nhưng không bịa nguồn).
                    - Tối đa 150 từ. Sử dụng gạch đầu dòng.
                    """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text.strip()

                if "OFFTOPIC" in ai_resp.upper():
                    st.warning("Vui lòng đặt câu hỏi liên quan.")
                else:
                    clean_text = re.sub(r'\[Ref:?\s*(\d+)\]', ' 🔖', ai_resp)
                    st.markdown(clean_text)
                    
                    # --- PHÁT TIẾNG NẾU DÙNG MICRO ---
                    if voice_text: 
                        audio_resp = text_to_speech(clean_text)
                        if audio_resp:
                            st.audio(audio_resp, format='audio/mp3', autoplay=True)

                    # --- HIỂN THỊ ẢNH ---
                    if found_images:
                        st.markdown("---")
                        st.markdown("##### 🖼️ Minh họa chi tiết:")
                        cols = st.columns(3)
                        for i, img in enumerate(found_images):
                            with cols[i % 3]:
                                st.markdown(f"""<div style="height:150px;overflow:hidden;border-radius:10px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;background:#f9f9f9;"><img src="{img['url']}" style="width:100%;height:100%;object-fit:cover;"></div>""", unsafe_allow_html=True)
                                with st.expander(f"🔍 Phóng to ảnh {i+1}"):
                                    st.image(img['url'], caption=img['title'], use_container_width=True)

                    # --- HIỂN THỊ NGUỒN ---
                    used_ids = [int(m) for m in re.findall(r'\[Ref:?\s*(\d+)\]', ai_resp) if int(m) in source_map]
                    if used_ids:
                        html_src = "<div class='source-box'><b>📚 Nguồn tham khảo:</b>"
                        seen = set()
                        for uid in used_ids:
                            info = source_map[uid]
                            if info['url'] != '#' and info['url'] not in seen:
                                seen.add(info['url'])
                                html_src += f" <a href='{info['url']}' target='_blank' class='source-link'>{info['title']}</a>"
                        html_src += "</div>"
                        st.markdown(html_src, unsafe_allow_html=True)
                    
                    # Lưu lịch sử
                    st.session_state.messages.append({"role": "assistant", "content": clean_text + ("\n\n" + html_src if 'html_src' in locals() else "") , "images": found_images})

            except Exception as e:
                st.error(f"Hệ thống đang bận: {e}")
            except Exception as e:
                st.error(f"Hệ thống đang bận: {e}")
