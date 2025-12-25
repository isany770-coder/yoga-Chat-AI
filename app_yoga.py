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
# 1. CẤU HÌNH TRANG & CSS
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    footer {display: none !important;}
    header {display: none !important;}
    .disclaimer-text {
        position: fixed !important; bottom: 5px !important; left: 0; width: 100%;
        text-align: center; color: #bbb; font-size: 10px; z-index: 999; pointer-events: none;
    }
    div[data-testid="stChatInput"] {
        position: fixed !important; bottom: 35px !important; left: 50% !important;
        transform: translateX(-50%) !important; z-index: 1000 !important;
        width: 95% !important; max-width: 800px !important;
        background-color: white !important; border-radius: 30px !important;
        border: 1px solid #e0e0e0 !important; box-shadow: 0 4px 15px rgba(0,0,0,0.1) !important;
        padding: 5px !important;
    }
    .stMainBlockContainer { padding-top: 1rem !important; padding-bottom: 180px !important; }
    [data-testid="stChatMessage"] { margin-bottom: 10px !important; }
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { display: block; color: #33691e; text-decoration: none; font-size: 14px; margin-bottom: 6px; }
    .promo-banner {
        background: linear-gradient(90deg, #e0f2f1 0%, #b2dfdb 100%);
        padding: 10px 15px; margin-bottom: 20px; border-radius: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #80cbc4;
    }
    .promo-text { color: #00695c; font-weight: bold; font-size: 14px; }
    .promo-btn {
        background-color: #00796b; color: white !important; padding: 6px 12px;
        border-radius: 15px; text-decoration: none; font-weight: bold; font-size: 12px; white-space: nowrap;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (CHỈ LOAD DATA - KHÔNG LOAD MODEL)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

# Đổi tên hàm để xóa Cache cũ
@st.cache_resource
def load_data_only_safe():
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu từ Drive"
    
    # 2. Tìm đường dẫn
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

    # 3. Load Database (KHÔNG GỌI MODEL Ở ĐÂY)
    try:
        # Dùng model embedding mặc định
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)
        
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

# Gọi hàm load
data_res, status = load_data_only_safe()

if status != "OK": 
    st.error(f"Lỗi: {status}")
    st.stop()

db_text, db_image = data_res

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

# THANH ĐẾM LƯỢT
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
# 4. GIAO DIỆN HẾT HẠN
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
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
                st.markdown("""<div style="text-align: center;"><h3 style="color: #00897b;">ĐÃ ĐẠT GIỚI HẠN!</h3><p>Vui lòng quay lại ngày mai hoặc đăng nhập.</p></div>""", unsafe_allow_html=True)
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập"):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True; st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True; st.rerun()
                        else: st.error("Sai thông tin")
        st.stop()

# =====================================================
# 5. HIỂN THỊ LỊCH SỬ CHAT
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Ưu đãi Member VIP!</div><a href="https://yogaismylife.vn/" target="_blank" class="promo-btn">Xem Ngay</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if "images" in msg and msg["images"]:
            st.markdown("---")
            for img in msg["images"]:
                st.image(img['url'], caption=img['title'])

# Gợi ý Upsell
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "Lộ trình 8 Bước", "url": "https://yogaismylife.vn", "key": ["đau","bệnh","trị liệu"]},
    "AI_COACH": {"name": "AI Coach Trị Liệu", "url": "https://yogaismylife.vn", "key": ["kỹ thuật","tư thế"]},
}

def get_clean_history():
    history_text = ""
    for msg in st.session_state.messages[-4:]:
        role = "User" if msg["role"] == "user" else "AI"
        clean_content = re.sub(r'<[^>]+>', '', msg["content"]) 
        history_text += f"{role}: {clean_content}\n"
    return history_text

# =====================================================
# 6. XỬ LÝ CHAT (TỰ ĐỘNG CHỌN MODEL CÓ SẴN)
# =====================================================
is_locked = False 
if not is_locked:
    if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        increment_usage(user_id)

        with st.chat_message("assistant"):
            with st.spinner("Đang xử lý..."):
                try:
                    # --- THUẬT TOÁN TỰ TÌM MODEL (KHÔNG GÕ TAY NỮA) ---
                    valid_model = None
                    try:
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                valid_model = m.name
                                break 
                    except: pass
                    
                    if not valid_model: valid_model = 'models/gemini-pro' # Fallback an toàn

                    # Khởi tạo model
                    model = genai.GenerativeModel(valid_model)

                    # --- TÌM KIẾM DỮ LIỆU ---
                    docs_text = db_text.similarity_search(prompt, k=8)
                    docs_img = []
                    if db_image: docs_img = db_image.similarity_search(prompt, k=4)
                    
                    # --- XỬ LÝ TEXT ---
                    context_text = ""
                    source_map = {}
                    for i, d in enumerate(docs_text):
                        context_text += f"[Nguồn {i+1}]: {d.page_content}\n"
                        source_map[i+1] = {"url": d.metadata.get('url','#'), "title": d.metadata.get('title','Link')}

                    # --- XỬ LÝ ẢNH ---
                    img_map = {}
                    context_img = ""
                    idx_img = 100
                    seen_urls = set()
                    for d in docs_img:
                        url = d.metadata.get('image_url','')
                        if url and url not in seen_urls:
                            img_map[idx_img] = {"url": url, "title": d.metadata.get('title','')}
                            context_img += f"[ID: {idx_img}] {d.metadata.get('title','')}\n"
                            seen_urls.add(url)
                            idx_img += 1

                    # --- PROMPT ---
                    sys_prompt = f"""
                    Bạn là Trợ lý Yoga.
                    Dữ liệu: {context_text}
                    Ảnh có sẵn: {context_img}
                    Câu hỏi: {prompt}
                    
                    Yêu cầu:
                    1. Trả lời dựa trên dữ liệu. Ghi nguồn [1], [2].
                    2. Nếu có ảnh phù hợp trong danh sách, ghi: |||IMAGES||| [ID ảnh]
                    3. Ngắn gọn, gạch đầu dòng.
                    """

                    response = model.generate_content(sys_prompt)
                    text_resp = response.text

                    # --- HIỂN THỊ ---
                    if "|||IMAGES|||" in text_resp:
                        main_txt, img_part = text_resp.split("|||IMAGES|||")
                    else:
                        main_txt, img_part = text_resp, ""
                    
                    st.markdown(main_txt.strip())
                    
                    # Hiển thị 1 ảnh
                    selected_images = []
                    found_ids = re.findall(r'\d+', img_part)
                    for fid in found_ids:
                        if int(fid) in img_map:
                            img = img_map[int(fid)]
                            st.image(img['url'], caption=img['title'])
                            selected_images.append(img)
                            break # Chỉ lấy 1 ảnh

                    # Nguồn
                    used_ref_ids = set([int(m) for m in re.findall(r'\[(\d+)\]', main_txt)])
                    html_src = ""
                    if used_ref_ids:
                        html_src = "<div class='source-box'><b>📚 Tham khảo:</b><br>"
                        has_link = False
                        seen_links = set()
                        for uid in used_ref_ids:
                            if uid in source_map:
                                src = source_map[uid]
                                if src['url'] != '#' and src['url'] not in seen_links:
                                    html_src += f"• <a href='{src['url']}' target='_blank' class='source-link' style='display:inline;'>{src['title']}</a><br>"
                                    seen_links.add(src['url'])
                                    has_link = True
                        html_src += "</div>"
                        if has_link: st.markdown(html_src, unsafe_allow_html=True)
                        else: html_src = ""

                    # Lưu tin nhắn
                    full_content = main_txt
                    if html_src: full_content += "\n\n" + html_src
                    st.session_state.messages.append({"role": "assistant", "content": full_content, "images": selected_images})

                except Exception as e:
                    st.error(f"Lỗi hệ thống: {str(e)}")

st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót.</div>', unsafe_allow_html=True)
