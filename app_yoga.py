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
# 2. LOGIC BACKEND (CẤU HÌNH & DATA)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data.zip"
EXTRACT_PATH = "/tmp/brain_data_extracted"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine():
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
        except: return None, None, "Lỗi tải dữ liệu"
    
    vector_path = None
    for root, _, files in os.walk(EXTRACT_PATH):
        for f in files:
            if f.endswith(".faiss"): vector_path = root; break
        if vector_path: break
    
    if not vector_path: return None, None, "Không tìm thấy vector"

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model, "OK"
    except Exception as e: return None, None, str(e)

db, model, status = load_brain_engine()
if status != "OK": st.stop()

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

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (V14 - Có nút X, Form hoạt động)
# =====================================================
if is_limit_reached:
    # Logic: Nếu người dùng bấm X, biến này sẽ thành True -> Ẩn thông báo đi
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False

    # Nếu chưa bấm đóng, thì hiện Modal chặn
    if not st.session_state.hide_limit_modal:
        # 1. Ẩn input chat để không cho chat tiếp
        st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
        
        # 2. Tạo lớp phủ mờ toàn màn hình
        st.markdown("""
            <style>
                .modal-backdrop {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0, 0, 0, 0.5); z-index: 9990;
                }
                .modal-card {
                    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    width: 90%; max-width: 420px;
                    background: white; border-radius: 20px;
                    padding: 25px; z-index: 9999;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    border: 2px solid #009688;
                    text-align: center;
                }
                /* Nút X đóng */
                .close-btn {
                    position: absolute; top: 10px; right: 15px;
                    font-size: 24px; color: #888; cursor: pointer;
                    font-weight: bold; text-decoration: none;
                }
                .close-btn:hover { color: #d32f2f; }
            </style>
            <div class="modal-backdrop"></div>
            <div class="modal-card">
        """, unsafe_allow_html=True)

        # 3. Nút Đóng (X) - Dùng thủ thuật tạo link để reload state
        # Khi bấm vào nút này, nó sẽ reload lại trang, nhưng ta cần xử lý logic ở Python
        col_close_1, col_close_2 = st.columns([9, 1])
        with col_close_2:
            if st.button("✕", key="close_modal_btn"):
                st.session_state.hide_limit_modal = True
                st.rerun()

        # 4. Nội dung thông báo (HTML thuần)
        st.markdown("""
            <div style="font-size: 50px; margin-bottom: 10px;">🧘‍♀️</div>
            <h3 style="color: #00796b; margin: 0 0 10px 0;">ĐÃ ĐẠT GIỚI HẠN!</h3>
            <p style="color: #555; font-size: 14px; margin-bottom: 20px;">
                Bạn đã dùng hết lượt thử miễn phí.<br>
                Vui lòng nâng cấp để tra cứu không giới hạn.
            </p>
            <a href="https://zalo.me/84963759566" target="_blank" 
               style="display: block; width: 100%; background: #009688; color: white; 
                      padding: 12px; border-radius: 25px; text-decoration: none; font-weight: bold;">
               💬 Nhận mã kích hoạt Zalo
            </a>
            <hr style="margin: 20px 0; border-top: 1px dashed #ccc;">
            <div style="font-size: 13px; color: #666; margin-bottom: 10px;">Hoặc đăng nhập thành viên:</div>
        """, unsafe_allow_html=True)

        # 5. Form Đăng nhập (Streamlit Widget - Hoạt động 100%)
        with st.form("login_form_modal"):
            u = st.text_input("Tên đăng nhập")
            p = st.text_input("Mật khẩu", type="password")
            btn = st.form_submit_button("Đăng Nhập", use_container_width=True)
            
            if btn:
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.session_state.hide_limit_modal = True # Tắt modal
                    st.success("Đăng nhập thành công!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Sai mật khẩu!")
        
        # Đóng thẻ div của modal
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Dừng chương trình để không hiện khung chat bên dưới khi modal đang mở
        st.stop()
    
    else:
        # Nếu đã bấm đóng (X), hiện thông báo nhỏ và CHẶN chat input
        st.markdown("""
        <div style="background:#ffebee; color:#c62828; padding:10px; text-align:center; border-radius:10px; margin-bottom:10px; border:1px solid #ef9a9a;">
            🚫 Bạn đang xem ở chế độ chỉ đọc (Hết lượt). <a href="https://zalo.me/84963759566" target="_blank" style="font-weight:bold;">Liên hệ Admin</a>
        </div>
        <style>div[data-testid="stChatInput"] {display: none !important;}</style>
        """, unsafe_allow_html=True)
        # Cho phép code chạy tiếp xuống dưới để hiển thị lịch sử chat cũ
# =====================================================
# 5. GIAO DIỆN CHAT CHÍNH
# =====================================================

# Banner quảng cáo (Chỉ hiện khi chưa login)
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Gạch Yoga giảm 30% hôm nay!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# Hiển thị tin nhắn
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Gợi ý giải pháp (Upsell)
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["mới", "bắt đầu", "lộ trình"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["đau", "bệnh", "trị liệu", "lưng", "gối", "thoát vị"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress", "ngủ", "thiền", "thở"]}
}

# =====================================================
# 6. XỬ LÝ CHAT (ĐÃ BỎ BỘ LỌC CHẶT)
# =====================================================
if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm trong kho dữ liệu..."):
            try:
                # --- THAY ĐỔI QUAN TRỌNG: BỎ SCORE FILTER ---
                # Lấy thẳng 8 kết quả tương đồng nhất, bất kể điểm số bao nhiêu
                docs = db.similarity_search(prompt, k=8)
                
                context_text = ""
                source_map = {}
                
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu Yoga')
                    type_ = d.metadata.get('type', 'blog')
                    
                    source_map[doc_id] = {"url": url, "title": title, "type": type_}
                    context_text += f"\n[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                # Prompt để AI tự lọc
                sys_prompt = f"""
                Bạn là chuyên gia Yoga. Dưới đây là các tài liệu tìm được từ kho dữ liệu.
                
                YÊU CẦU:
                1. Trả lời câu hỏi: "{prompt}" dựa trên các nguồn sau.
                2. Nếu các nguồn có vẻ không liên quan trực tiếp, hãy cố gắng tìm ý liên quan nhất hoặc trả lời dựa trên kiến thức Yoga chuẩn xác của bạn, nhưng CẢNH BÁO người dùng là thông tin tham khảo.
                3. BẮT BUỘC: Khi dùng ý từ nguồn nào, phải ghi chú [Ref: X] (X là số nguồn).
                
                NGUỒN DỮ LIỆU:
                {context_text}
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text
                
                # Render kết quả
                clean_text = re.sub(r'\[Ref: \d+\]', ' 🔖', ai_resp)
                st.markdown(clean_text)
                
                # Logic hiển thị Link (Ref)
                used_ids = [int(m) for m in re.findall(r'\[Ref: (\d+)\]', ai_resp) if int(m) in source_map]
                unique_used_ids = sorted(list(set(used_ids)))
                
                html_sources = ""
                if unique_used_ids:
                    html_sources += "<div class='source-box'><b>📚 Nguồn tham khảo:</b>"
                    seen_urls = set()
                    for uid in unique_used_ids:
                        info = source_map[uid]
                        if info['url'] != '#' and info['url'] not in seen_urls:
                            seen_urls.add(info['url'])
                            color = "#e3f2fd" if info['type']=='science' else "#e8f5e9"
                            label = "NGHIÊN CỨU" if info['type']=='science' else "BÀI VIẾT"
                            html_sources += f"""<a href="{info['url']}" target="_blank" class="source-link"><span class="tag" style="background:{color}">{label}</span>{info['title']}</a>"""
                    html_sources += "</div>"
                    st.markdown(html_sources, unsafe_allow_html=True)

                # Logic Upsell (Gợi ý giải pháp)
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div style='margin-top:15px'>"
                    for r in recs[:2]:
                         upsell_html += f"""<div style="background:#e0f2f1; padding:10px; border-radius:10px; margin-bottom:8px; border:1px solid #009688; display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:bold; color:#004d40; font-size:14px">{r['name']}</span><a href="{r['url']}" target="_blank" style="background:#00796b; color:white; padding:5px 10px; border-radius:15px; text-decoration:none; font-size:12px; font-weight:bold;">Xem ngay</a></div>"""
                    upsell_html += "</div>"
                    st.markdown(upsell_html, unsafe_allow_html=True)
                
                # Lưu lịch sử
                full_save = clean_text
                if html_sources: full_save += "\n\n" + html_sources
                if upsell_html: full_save += "\n\n" + upsell_html
                st.session_state.messages.append({"role": "assistant", "content": full_save})

            except Exception as e: st.error("Hệ thống đang bận. Vui lòng thử lại.")
