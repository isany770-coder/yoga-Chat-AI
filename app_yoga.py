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
# 1. CẤU HÌNH TRANG & CSS (GIỮ NGUYÊN BẢN GỐC CỦA BẠN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* 1. Tối ưu khung nền */
    .stApp { background-color: #ffffff; }
    header[data-testid="stHeader"], footer {display: none;}
    .stDeployButton {display:none;}

    /* 2. Khung Chat Input (Hiện đại, bo tròn) */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* 3. Thanh Quảng Cáo (Banner) */
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

    /* 4. Màn hình Hết Hạn (Limit Screen - Chuẩn mẫu ảnh) */
    .limit-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(255, 255, 255, 0.95); z-index: 9999;
        display: flex; align-items: center; justify-content: center;
        flex-direction: column;
    }
    .limit-card {
        background: white; width: 90%; max-width: 400px;
        padding: 30px 20px; border-radius: 20px;
        text-align: center;
        border: 2px solid #26a69a; /* Viền xanh như ảnh */
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .limit-icon { font-size: 50px; margin-bottom: 15px; display: block; }
    .limit-title { 
        font-size: 18px; font-weight: bold; color: #00897b; 
        margin-bottom: 10px; text-transform: uppercase;
    }
    .limit-desc { font-size: 14px; color: #555; line-height: 1.5; margin-bottom: 25px; }
    .zalo-btn-limit {
        display: block; width: 100%; padding: 12px;
        background-color: #009688; color: white !important;
        text-decoration: none; font-weight: bold; border-radius: 25px;
        margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0, 150, 136, 0.3);
    }
    /* 4. DÒNG DISCLAIMER NẰM GỌN DƯỚI ĐÁY */
    .disclaimer-text {
        position: fixed;
        bottom: 15px;
        left: 0;
        width: 100%;
        text-align: center;
        color: #999;
        font-size: 11px;
        z-index: 999;
    }
    .login-link { color: #00796b; font-size: 13px; cursor: pointer; text-decoration: underline;}

    /* 5. Hiển thị nguồn (Citation) */
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { 
        display: block; color: #33691e; text-decoration: none; font-size: 14px; 
        margin-bottom: 6px; padding: 5px; border-radius: 5px; transition: 0.2s;
    }
    .source-link:hover { background-color: #dcedc8; }
    .tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; text-transform: uppercase; border: 1px solid; }
    
    .bottom-spacer { height: 100px; }
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
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga.\nHôm nay chúng ta nên bắt đầu từ đâu?"}]

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
# 8. XỬ LÝ CHAT (CHẾ ĐỘ ĐA NHIỆM: VỪA SOI DÁNG, VỪA CHÉM GIÓ)
# =====================================================

# 1. Hiển thị lịch sử chat cũ (Giữ nguyên ký ức của bot)
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# --- KHỐI XỬ LÝ LOGIC ---

# Biến chứa nội dung cần xử lý (đến từ 2 nguồn)
final_input = None
is_auto_mode = False

# Nguồn A: Từ URL (Do file JS bắn về sau khi tập xong)
if "auto_prompt" in st.query_params:
    final_input = st.query_params["auto_prompt"]
    is_auto_mode = True
    # Xóa ngay tham số trên URL để tránh F5 lại bị spam, 
    # nhưng vẫn giữ nội dung trong biến final_input để xử lý lần này
    st.query_params.clear() 

# Nguồn B: Từ ô nhập liệu (User tự gõ chém gió)
# Lưu ý: Luôn hiện ô chat_input để user thích hỏi gì thì hỏi
user_chat = st.chat_input("Hỏi tôi về Yoga, tư thế, đau mỏi...")
if user_chat:
    final_input = user_chat
    is_auto_mode = False

# --- KHI CÓ ĐẦU VÀO (DÙ LÀ TỰ ĐỘNG HAY TỰ GÕ) ---
if final_input:
    # 1. Lưu vào lịch sử hiển thị
    # Nếu là auto (kết quả tập), ta thêm prefix icon cho đẹp
    display_text = final_input
    
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)

    # 2. Lưu vào Database hành vi (chỉ tính lượt nếu user tự gõ, tùy bác)
    if not is_auto_mode:
        db_data[user_key]["count"] += 1
        save_data(db_data)

    # 3. GỌI "NÃO" (FAISS + GEMINI)
    with st.chat_message("assistant"):
        if db:
            # Bước A: Tìm kiếm trong não bộ (Vector Search)
            # Lấy 4 đoạn tài liệu liên quan nhất đến câu hỏi/kết quả tập
            docs = db.similarity_search(final_input, k=4) 
            
            context_parts = []
            source_map = {}
            
            for i, d in enumerate(docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                label = "KIẾN THỨC" if dtype == 'science' else "KINH NGHIỆM"
                context_parts.append(f"--- NGUỒN {i+1} [{label}]: {title} ---\n{d.page_content}")
                
                if url != "#" and url is not None:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)

            # Bước B: Xây dựng Prompt (Linh hoạt theo ngữ cảnh)
            if is_auto_mode:
                # Prompt chuyên dụng cho việc nhận xét tư thế
                sys_prompt = f"""
                Bạn là Yoga Coach chuyên nghiệp. Học viên vừa gửi kết quả tập luyện: "{final_input}".
                Dựa trên DỮ LIỆU CHUYÊN SÂU sau đây:
                {full_context}
                
                Hãy:
                1. Khen ngợi ngắn gọn (động viên).
                2. Phân tích lỗi sai dựa trên kiến thức trong dữ liệu (nếu có lỗi).
                3. Đề xuất bài tập bổ trợ hoặc cách sửa.
                Giọng văn: Thân thiện, khuyến khích.
                """
            else:
                # Prompt cho chat chit thông thường
                sys_prompt = f"""
                Bạn là Trợ lý Yoga AI. Trả lời câu hỏi của người dùng dựa trên DỮ LIỆU:
                {full_context}
                
                Câu hỏi: "{final_input}"
                Giọng văn: Chuyên gia, ngắn gọn, súc tích.
                """
            
            try:
                with st.spinner("🧠 Đang tham vấn chuyên gia..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                # Bước C: Hiển thị câu trả lời
                st.markdown(res_text, unsafe_allow_html=True)
                
                # Hiển thị sản phẩm gợi ý (nếu có trong logic cũ)
                solutions = get_recommended_solutions(final_input)
                if solutions:
                    for sol in solutions:
                        st.markdown(f"""<div class="solution-card">... (code render thẻ như cũ) ...</div>""", unsafe_allow_html=True)

                # Hiển thị nguồn tham khảo
                if source_map:
                    links_html = "<div class='source-box'><strong>📚 Tham khảo thêm:</strong><div style='margin-top:8px'>"
                    for url, info in source_map.items():
                         links_html += f"<div><a href='{url}' target='_blank'>{info['title']}</a></div>"
                    links_html += "</div></div>"
                    st.markdown(links_html, unsafe_allow_html=True)

                # Lưu câu trả lời vào lịch sử
                db_data[user_key]["history"].append({"role": "assistant", "content": res_text})
                save_data(db_data)
                
            except Exception as error:
                st.error(f"Hệ thống bận: {error}")

                st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót, vì vậy, nhớ xác minh câu trả lời.</div>', unsafe_allow_html=True)
