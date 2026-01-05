import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
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
    /* CSS Giao diện Chat Hiện đại */
    .stApp { background-color: #ffffff; }
    header, footer, .stDeployButton {display: none;}

    /* Khung Chat Input */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Thanh Quảng Cáo */
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

    /* Disclaimer & Link */
    .disclaimer-text { position: fixed; bottom: 5px; left: 0; width: 100%; text-align: center; color: #aaa; font-size: 10px; z-index: 999; }
    .ref-link { color: #00796b; font-weight: bold; text-decoration: none; background: #e0f2f1; padding: 0 4px; border-radius: 4px; }
    .ref-link:hover { background: #b2dfdb; text-decoration: underline; }
    
    /* Limit Modal CSS (Giữ nguyên form cũ) */
    .limit-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.95); z-index: 9999; display: flex; align-items: center; justify-content: center; }
    
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (CHỈ TẢI NÃO CHỮ - BỎ ẢNH)
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

@st.cache_resource
def load_brain_text_only():
    # 1. Tải và giải nén (nếu chưa có)
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu"
    
    # 2. Tìm đường dẫn não Text
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path):
                    return check_path
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Lỗi: Không tìm thấy não chữ"

    # 3. Load DB Text
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        return db_text, "OK"
    except Exception as e: return None, str(e)

# Gọi hàm load
db_text, status = load_brain_text_only()
if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# =====================================================
# 3. QUẢN LÝ USER & LIMIT (GIỮ NGUYÊN)
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

# Thanh đếm lượt
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
# 4. GIAO DIỆN HẾT HẠN (MODAL LOGIN)
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    if not st.session_state.hide_limit_modal:
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        with col_center:
            with st.container(border=True):
                if st.button("✕"): st.session_state.hide_limit_modal = True; st.rerun()
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px;">Để tiếp tục tra cứu <b>Kho dữ liệu 15 triệu từ</b> và nhận ưu đãi, mời bạn liên hệ Admin:</p>
                        <a href="https://zalo.me/84963759566" target="_blank" style="display: inline-block; width: 100%; background-color: #009688; color: white; padding: 12px 0; border-radius: 30px; text-decoration: none; font-weight: bold; margin: 15px 0;">💬 Nhận mã kích hoạt qua Zalo</a>
                    </div>
                """, unsafe_allow_html=True)
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập"):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.rerun()
                        else: st.error("Sai tài khoản")
        st.stop()

# =====================================================
# 5. HIỂN THỊ CHAT VÀ UPSELL
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Combo Thảm tập + Tài khoản VIP giảm 30%!</div><a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","lưng","gối","cột sống","thoát vị"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","chỉnh tư thế","hướng dẫn","sửa lỗi"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress","căng thẳng","ngủ","mất ngủ","thiền","thở"]}
}

# =====================================================
# 6. XỬ LÝ CHAT (FLASH MODEL - TẮT ẢNH - GẮN LINK REF)
# =====================================================
if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu..."):
            try:
                # 1. Tự động tìm Model FLASH (Tiết kiệm + Sống dai)
                valid_model = 'models/gemini-1.5-flash'
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            if 'flash' in m.name.lower():
                                valid_model = m.name
                                break
                except: pass
                
                model = genai.GenerativeModel(valid_model)
                
                # 2. Tìm kiếm (CHỈ TEXT)
                docs = db_text.similarity_search(prompt, k=5)
                
                context_text = ""
                source_map = {}

                for i, d in enumerate(docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu Yoga')
                    
                    # Lưu lại map để thay thế sau
                    source_map[doc_id] = {"url": url, "title": title}
                    context_text += f"\n[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                # 3. Prompt (Yêu cầu trích dẫn số)
                sys_prompt = f"""
                Bạn là chuyên gia Yoga Y Khoa.
                DỮ LIỆU THAM KHẢO:
                {context_text}
                
                CÂU HỎI: "{prompt}"
                
                YÊU CẦU:
                - Trả lời ngắn gọn (dưới 200 từ), đúng trọng tâm.
                - Khi dùng thông tin từ [Nguồn X], hãy ghi chú ngay cuối câu đó bằng ký hiệu: [Ref: X].
                - Ví dụ: Tập Yoga giúp giảm đau lưng [Ref: 1].
                - Nếu không có trong dữ liệu, hãy trả lời bằng kiến thức chung nhưng không bịa nguồn.
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text.strip()

                # 4. Xử lý Link Ref (Thay [Ref: 1] thành Link Clickable)
                # Dùng Regex để tìm và thay thế
                def replace_ref(match):
                    ref_id = int(match.group(1))
                    if ref_id in source_map:
                        info = source_map[ref_id]
                        if info['url'] and info['url'] != '#':
                            # Tạo link HTML nhỏ gọn
                            return f" <a href='{info['url']}' target='_blank' class='ref-link' title='{info['title']}'>[{ref_id}]</a>"
                    return "" # Nếu không có link thì ẩn luôn số Ref đi cho gọn

                # Thay thế pattern [Ref: X] hoặc [Ref:X]
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_resp)

                st.markdown(final_html, unsafe_allow_html=True)
                
                # Upsell
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div style='margin-top:15px'>"
                    for r in recs[:2]:
                        upsell_html += f"""<div style="background:#e0f2f1; padding:8px; border-radius:8px; margin-bottom:5px; border:1px solid #009688; display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:bold; color:#004d40; font-size:13px">{r['name']}</span><a href="{r['url']}" target="_blank" style="background:#00796b; color:white; padding:4px 8px; border-radius:12px; text-decoration:none; font-size:11px; font-weight:bold;">Xem ngay</a></div>"""
                    upsell_html += "</div>"
                    st.markdown(upsell_html, unsafe_allow_html=True)

                # Lưu lịch sử
                st.session_state.messages.append({"role": "assistant", "content": final_html + upsell_html})

            except Exception as e:
                st.error("Hệ thống đang bận. Vui lòng thử lại sau.")

            st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót, hãy kiểm chứng thông tin.</div>', unsafe_allow_html=True)
