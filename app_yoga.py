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
# 1. CẤU HÌNH TRANG & CSS (GIỮ NGUYÊN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    header[data-testid="stHeader"], footer {display: none;}
    .stDeployButton {display:none;}

    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
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
    
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 6px; border-radius: 4px; margin: 0 2px;
        font-size: 0.9em; border: 1px solid #b2dfdb;
    }
    .ref-link:hover { background: #00796b; color: white; border-color: #004d40; }

    .disclaimer-text { position: fixed; bottom: 15px; left: 0; width: 100%; text-align: center; color: #999; font-size: 11px; z-index: 999; }
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOAD DATA (TRẢ VỀ MODEL 004 NHƯ BẠN MUỐN)
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
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu"
    
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path):
                    return check_path
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Lỗi: Không tìm thấy vector_db"

    try:
        # --- ĐÂY: TRẢ VỀ MODEL 004 ---
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        return db_text, "OK"
    except Exception as e: return None, str(e)

db_text, status = load_brain_engine_safe()
if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# =====================================================
# 3. QUẢN LÝ USER & SESSION (THÊM BIẾN CHẶN)
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

# --- THÊM: BIẾN ĐẾM SPAM ---
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0  
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False

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

# --- THANH ĐẾM ---
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
                st.markdown("""<h3 style="color:#00897b;text-align:center;">ĐÃ ĐẠT GIỚI HẠN!</h3>""", unsafe_allow_html=True)
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập Ngay"):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Thành công!"); time.sleep(1); st.rerun()
                        else: st.error("❌ Sai thông tin")
        st.stop()

# =====================================================
# 5. HIỂN THỊ CHAT (GIỮ NGUYÊN)
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

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","kỹ thuật"]}
}

# =====================================================
# 6. XỬ LÝ CHAT (LOGIC BỔ SUNG KHÓA & ADMIN)
# =====================================================

# 1. KIỂM TRA KHÓA
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN ĐÃ BỊ KHÓA: Spam câu hỏi sai chủ đề. Vui lòng F5.")
    st.stop()

if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id) 

    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu..."):
            try:
                # --- CẤU HÌNH ADMIN (BẠN SỬA LINK Ở ĐÂY) ---
                ADMIN_NAME = "Coach Nguyễn Văn A" 
                PROFILE_LINK = "https://zalo.me/YOUR_PHONE_NUMBER"

                # 2. Tìm Model Flash
                valid_model = 'models/gemini-1.5-flash'
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            if 'flash' in m.name.lower(): valid_model = m.name; break
                except: pass
                model = genai.GenerativeModel(valid_model)
                
                # 3. Context
                chat_history_context = ""
                recent_msgs = st.session_state.messages[-7:-1] 
                for msg in recent_msgs:
                    role = "User" if msg["role"] == "user" else "Bot"
                    clean_content = re.sub(r'<[^>]*>', '', msg["content"]).strip()
                    chat_history_context += f"{role}: {clean_content}\n"

                # 4. Tìm kiếm (Dùng db_text load từ embedding-004)
                docs = db_text.similarity_search(prompt, k=5)
                
                context_text = ""
                source_map = {}
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu')
                    source_map[doc_id] = {"url": url, "title": title}
                    context_text += f"\n[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                # 5. PROMPT XỬ LÝ
                sys_prompt = f"""
                Bạn là chuyên gia Yoga Y Khoa.
                
                YÊU CẦU ĐẶC BIỆT:
                1. Nếu hỏi về ADMIN/TÁC GIẢ:
                   - Giới thiệu {ADMIN_NAME}.
                   - Bắt buộc kèm link: {PROFILE_LINK}
                
                2. Nếu hỏi SAI CHỦ ĐỀ (Xổ số, code, chính trị...):
                   - Trả lời duy nhất: REFUSE_TOPIC
                
                3. Nếu hỏi về YOGA (Đúng chủ đề):
                   - Dựa vào DỮ LIỆU TRA CỨU bên dưới.
                   - Nếu thiếu, dùng kiến thức của bạn.
                   - Ngắn gọn (Max 200 từ).
                   - Ghi nguồn: [Ref: X].
                
                DỮ LIỆU TRA CỨU:
                {context_text}
                
                LỊCH SỬ CHAT:
                {chat_history_context}
                
                CÂU HỎI MỚI: "{prompt}"
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text.strip()

                # --- XỬ LÝ LOGIC ---
                if "REFUSE_TOPIC" in ai_resp:
                    st.session_state.bad_attempts += 1
                    if st.session_state.bad_attempts >= 3:
                        st.session_state.is_blocked = True
                        msg = "🚫 ĐÃ KHÓA: Bạn hỏi sai chủ đề 3 lần. F5 để thử lại."
                        st.markdown(msg); st.session_state.messages.append({"role": "assistant", "content": msg}); st.stop()
                    else:
                        msg = f"⚠️ CHỈNH ĐỐN: Tôi chỉ hỗ trợ Yoga. (Vi phạm: {st.session_state.bad_attempts}/3)"
                        st.markdown(msg); st.session_state.messages.append({"role": "assistant", "content": msg})
                else:
                    def replace_ref(match):
                        ref_id = int(match.group(1))
                        if ref_id in source_map:
                            info = source_map[ref_id]
                            if info['url'] and info['url'] != '#':
                                return f" <a href='{info['url']}' target='_blank' class='ref-link' title='{info['title']}'>[{ref_id}]</a>"
                        return "" 

                    final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_resp)
                    if PROFILE_LINK in ai_resp:
                        final_html = final_html.replace(PROFILE_LINK, f"<a href='{PROFILE_LINK}' target='_blank'><b>👉 Xem Profile Admin</b></a>")

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

                    st.session_state.messages.append({"role": "assistant", "content": final_html + upsell_html})

            except Exception as e:
                st.error("Hệ thống đang bận. Vui lòng thử lại sau.")

            st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót, hãy kiểm chứng thông tin.</div>', unsafe_allow_html=True)
