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
# 1. CẤU HÌNH TRANG & CSS (FINAL CLEAN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Reset & Clean UI */
    .stApp { background-color: #ffffff; }
    header[data-testid="stHeader"], footer, .stDeployButton {display: none;}

    /* Khung Chat Input (Bo tròn, hiện đại) */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Thanh Quảng Cáo (Top Banner) */
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

    /* Hiển thị Nguồn (Citation Box) */
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { 
        display: block; color: #33691e; text-decoration: none; font-size: 14px; 
        margin-bottom: 6px; padding: 5px; border-radius: 5px; transition: 0.2s;
    }
    .source-link:hover { background-color: #dcedc8; }
    .tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; text-transform: uppercase; border: 1px solid; }
    
    /* Khoảng trống dưới cùng để không bị che chat */
    .bottom-spacer { height: 100px; }
    
    /* Cảnh báo chế độ chỉ đọc */
    .read-only-alert {
        background:#ffebee; color:#c62828; padding:12px; text-align:center; 
        border-radius:12px; margin-bottom:15px; border:1px solid #ffcdd2; font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. BACKEND ENGINE (SQLITE & GEMINI)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Lỗi: Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data.zip"
EXTRACT_PATH = "/tmp/brain_data_extracted"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine():
    # Tải dữ liệu từ Drive
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            gc.collect()
        except: return None, None, "Lỗi tải dữ liệu"
    
    # Tìm file vector
    vector_path = None
    for root, _, files in os.walk(EXTRACT_PATH):
        for f in files:
            if f.endswith(".faiss"): vector_path = root; break
        if vector_path: break
    
    if not vector_path: return None, None, "Không tìm thấy vector"

    # Load Model
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model, "OK"
    except Exception as e: return None, None, str(e)

db, model, status = load_brain_engine()
if status != "OK": st.stop()

# --- DATABASE QUẢN LÝ LƯỢT DÙNG ---
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

# --- SESSION & AUTH ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga Y Khoa.\nBạn cần tìm bài tập hay tư vấn bệnh lý gì hôm nay?"}]

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
# 3. GIAO DIỆN HẾT HẠN (V15 - NATIVE & CLEAN)
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    
    # Ẩn thanh chat input bằng CSS
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    if not st.session_state.hide_limit_modal:
        # Layout căn giữa bằng Columns (Không vỡ trên Mobile)
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        
        with col_center:
            with st.container(border=True):
                # Nút Đóng
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕", help="Đóng để xem lịch sử"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
                # Nội dung thông báo
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử.<br>
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

                # Form đăng nhập (Native Streamlit)
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập Ngay", use_container_width=True):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Đăng nhập thành công!")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("❌ Sai tên đăng nhập hoặc mật khẩu")
        st.stop()
    else:
        # Trạng thái đã đóng modal (Chế độ chỉ đọc)
        st.markdown("""<div class="read-only-alert">🚫 Bạn đang xem ở chế độ chỉ đọc. <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: underline; color: #b71c1c;">Nâng cấp ngay</a></div>""", unsafe_allow_html=True)

# =====================================================
# 4. GIAO DIỆN CHÍNH & UPSELL
# =====================================================

# Banner Quảng Cáo (Cho khách chưa đăng nhập)
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Freeship giảm 30% hôm nay!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Cấu hình Upsell (Gợi ý giải pháp)
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["mới", "bắt đầu", "lộ trình"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["đau", "bệnh", "trị liệu", "lưng", "gối", "thoát vị"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress", "ngủ", "thiền", "thở"]}
}

# =====================================================
# 5. XỬ LÝ CHAT (LOGIC FINAL)
# =====================================================
if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu kho dữ liệu..."):
            try:
                # 1. Tìm kiếm (Lấy 8 kết quả, KHÔNG lọc điểm số)
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

                # 2. Prompt Gemini (Yêu cầu trích dẫn chặt chẽ)
                sys_prompt = f"""
                Bạn là chuyên gia Yoga. Dựa vào các nguồn dữ liệu dưới đây để trả lời câu hỏi: "{prompt}"
                
                YÊU CẦU:
                1. Trả lời ngắn gọn, có tâm.
                2. Nếu dùng ý từ nguồn nào, BẮT BUỘC ghi chú [Ref: X] (X là số thứ tự nguồn).
                3. Nếu thông tin không có trong nguồn, hãy trả lời theo kiến thức Yoga chuẩn xác của bạn nhưng cảnh báo là "Thông tin bổ trợ".
                4. Số từ tối đa không quá 150.
                
                DỮ LIỆU:
                {context_text}
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text
                
                # 3. Render Kết quả & Nguồn
                clean_text = re.sub(r'\[Ref: \d+\]', ' 🔖', ai_resp)
                st.markdown(clean_text)
                
                # Lọc và hiển thị Link nguồn
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

                # 4. Upsell (Gợi ý giải pháp)
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
