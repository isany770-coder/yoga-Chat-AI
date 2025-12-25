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
# 1. CẤU HÌNH TRANG & CSS (CHUẨN UI/UX CŨ CỦA BẠN)
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

    /* 4. Màn hình Hết Hạn (Limit Screen) */
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
        border: 2px solid #26a69a;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }

    /* 5. Hiển thị nguồn (Citation) */
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { 
        display: block; color: #33691e; text-decoration: none; font-size: 14px; 
        margin-bottom: 6px; padding: 5px; border-radius: 5px; transition: 0.2s;
    }
    .source-link:hover { background-color: #dcedc8; }
    
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (CẤU HÌNH & DATA) - ĐÃ SỬA LỖI 404
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

# --- CẤU HÌNH ĐƯỜNG DẪN ---
ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

# Đổi tên hàm để ép xóa Cache cũ bị lỗi
@st.cache_resource
def load_data_safe_v2():
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

    # 3. Load Database (QUAN TRỌNG: KHÔNG GỌI MODEL Ở ĐÂY)
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        
        # Não Chữ
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # Não Ảnh (Nếu có)
        db_image = None
        if image_db_path:
            db_image = FAISS.load_local(image_db_path, embeddings, allow_dangerous_deserialization=True)

        # CHỈ TRẢ VỀ DỮ LIỆU - KHÔNG KHỞI TẠO MODEL GEMINI Ở ĐÂY ĐỂ TRÁNH LỖI
        return (db_text, db_image), "OK"
    except Exception as e: return None, str(e)

# --- GỌI HÀM LOAD ---
data_result, status = load_data_safe_v2()

if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# Tách ra để dùng ở dưới
db_text, db_image = data_result

# =====================================================
# 3. QUẢN LÝ USER & GIỚI HẠN (GIỮ NGUYÊN)
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
# 4. GIAO DIỆN HẾT HẠN (GIỮ NGUYÊN)
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
                    if st.button("✕"): st.session_state.hide_limit_modal = True; st.rerun()
                
                st.markdown("""
                    <div style="text-align: center;">
                        <h3 style="color: #00897b;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p>Vui lòng quay lại ngày mai hoặc đăng nhập.</p>
                        <a href="https://zalo.me/84963759566" target="_blank" style="display:block;width:100%;background:#009688;color:white;padding:10px;border-radius:20px;text-decoration:none;margin-bottom:15px;">💬 Nhận mã Zalo</a>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập", use_container_width=True):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True; st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True; st.success("OK"); time.sleep(1); st.rerun()
                        else: st.error("Sai thông tin")
        st.stop()

# =====================================================
# 5. GIAO DIỆN CHAT & LỊCH SỬ (GIỮ NGUYÊN)
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
                with cols[i % 3]:
                    st.markdown(f"""<div style="height:150px;overflow:hidden;border-radius:10px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;background:#f9f9f9;"><img src="{img['url']}" style="width:100%;height:100%;object-fit:cover;"></div>""", unsafe_allow_html=True)
                    with st.expander(f"🔍 Xem ảnh {i+1}"):
                        st.image(img['url'], caption=img['title'], use_container_width=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Upsell
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn", "key": ["đau","bệnh","trị liệu"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach", "url": "https://yogaismylife.vn", "key": ["tập đúng","kỹ thuật"]},
}

# =====================================================
# 6. XỬ LÝ CHAT (TỰ ĐỘNG CHỌN MODEL - KHÔNG LO CHẾT APP)
# =====================================================
def get_clean_history():
    history_text = ""
    recent_msgs = st.session_state.messages[-4:] 
    for msg in recent_msgs:
        role = "User" if msg["role"] == "user" else "AI"
        clean_content = re.sub(r'<[^>]+>', '', msg["content"]) 
        history_text += f"{role}: {clean_content}\n"
    return history_text

if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu dữ liệu..."):
            try:
                # --- THUẬT TOÁN TỰ TÌM MODEL (QUAN TRỌNG) ---
                # Code này sẽ hỏi server xem có model nào dùng được thì dùng
                # Không ép cứng tên model để tránh lỗi 404
                valid_model = 'models/gemini-pro' # Mặc định an toàn
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            # Ưu tiên Flash hoặc Pro mới nhất nếu có
                            if 'flash' in m.name or 'pro' in m.name:
                                valid_model = m.name
                                break
                except: pass
                
                # Khởi tạo model tại đây (Chắc chắn không lỗi vì đã check)
                model = genai.GenerativeModel(valid_model)

                # --- TÌM KIẾM DỮ LIỆU ---
                docs_text = db_text.similarity_search(prompt, k=4)
                docs_img = []
                if db_image: docs_img = db_image.similarity_search(prompt, k=2)
                
                # --- XỬ LÝ TEXT & ẢNH ---
                context_text = ""
                source_map = {}
                img_map = {}
                context_img_desc = ""
                found_images = []

                # Xử lý text
                for i, d in enumerate(docs_text):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu')
                    source_map[doc_id] = {"url": url, "title": title}
                    context_text += f"[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                # Xử lý ảnh
                idx_img = 100
                for d in docs_img:
                    url = d.metadata.get('image_url', '')
                    title = d.metadata.get('title', 'Ảnh minh họa')
                    if url:
                        img_map[idx_img] = {"url": url, "title": title}
                        context_img_desc += f"[ID ẢNH: {idx_img}] {title}\n"
                        idx_img += 1

                # --- PROMPT ---
                sys_prompt = f"""
                Bạn là chuyên gia Yoga Y Khoa.
                
                1. DỮ LIỆU THAM KHẢO:
                {context_text}
                
                2. ẢNH CÓ SẴN:
                {context_img_desc}

                3. CÂU HỎI: "{prompt}"

                YÊU CẦU:
                - Trả lời dựa trên dữ liệu. Ghi nguồn dạng [1], [2].
                - Nếu có ảnh phù hợp trong danh sách ảnh, hãy liệt kê ID ảnh ở cuối bài.
                - Nếu dữ liệu không khớp câu hỏi, hãy tự trả lời bằng kiến thức Yoga chuẩn xác (nhưng không được bịa nguồn).
                - Cấu trúc trả về:
                  [Nội dung trả lời...]
                  |||IMAGES|||
                  [ID ảnh]
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text.strip()

                # --- TÁCH ẢNH & TEXT ---
                if "|||IMAGES|||" in ai_resp:
                    main_txt, img_part = ai_resp.split("|||IMAGES|||")
                else:
                    main_txt, img_part = ai_resp, ""

                # Lấy ảnh
                selected_images = []
                found_ids = re.findall(r'\d+', img_part)
                for fid in found_ids:
                    fid = int(fid)
                    if fid in img_map:
                        selected_images.append(img_map[fid])

                # Hiển thị nội dung
                st.markdown(main_txt.strip())
                
                # Hiển thị ảnh (nếu có)
                if selected_images:
                    st.markdown("---")
                    st.markdown("##### 🖼️ Minh họa chi tiết:")
                    cols = st.columns(3)
                    for i, img in enumerate(selected_images):
                        with cols[i % 3]:
                            st.markdown(f"""<div style="height:150px;overflow:hidden;border-radius:10px;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;background:#f9f9f9;"><img src="{img['url']}" style="width:100%;height:100%;object-fit:cover;"></div>""", unsafe_allow_html=True)
                            with st.expander(f"🔍 Xem rõ hơn"):
                                st.image(img['url'], caption=img['title'], use_container_width=True)

                # Hiển thị nguồn
                used_ids = [int(m) for m in re.findall(r'\[(\d+)\]', main_txt)]
                if used_ids:
                    html_src = "<div class='source-box'><b>📚 Tài liệu tham khảo:</b><br>"
                    seen_links = set()
                    has_link = False
                    for uid in used_ids:
                        if uid in source_map:
                            info = source_map[uid]
                            if info['url'] != '#' and info['url'] not in seen_links:
                                html_src += f"• <a href='{info['url']}' target='_blank' class='source-link'>{info['title']}</a>"
                                seen_links.add(info['url'])
                                has_link = True
                    html_src += "</div>"
                    if has_link: st.markdown(html_src, unsafe_allow_html=True)
                    else: html_src = "" # Không hiện nếu không có link

                # Lưu lịch sử
                full_content = main_txt
                if 'html_src' in locals() and html_src: full_content += "\n\n" + html_src
                st.session_state.messages.append({"role": "assistant", "content": full_content, "images": selected_images})

            except Exception as e:
                st.error("Hệ thống đang bận hoặc quá tải. Vui lòng thử lại sau vài giây.")
                # st.error(f"Debug Info: {str(e)}") # Bật dòng này nếu muốn xem lỗi chi tiết
