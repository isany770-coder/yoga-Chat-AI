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
# 1. CẤU HÌNH TRANG & CSS (GIỮ NGUYÊN BẢN GỐC)
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

    /* 2. Khung Chat Input */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* 3. Thanh Quảng Cáo */
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

    /* 4. Màn hình Hết Hạn */
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
    
    /* 5. Style Link Ref bấm được */
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 6px; border-radius: 4px; margin: 0 2px;
        font-size: 0.9em; border: 1px solid #b2dfdb;
    }
    .ref-link:hover { background: #00796b; color: white; border-color: #004d40; }

    .disclaimer-text { position: fixed; bottom: 15px; left: 0; width: 100%; text-align: center; color: #999; font-size: 11px; z-index: 999; }
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; font-size: 0.9em; }
    .source-link { display: block; color: #33691e; text-decoration: none; font-weight: 600; margin-bottom: 4px; }
    
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (ĐÃ SỬA: BỎ NÃO ẢNH CHO NHẸ)
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
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
        except: return None, "Lỗi tải dữ liệu từ Drive"
    
    # 2. Tìm não chữ (Text DB)
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path):
                    return check_path
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Lỗi: Không tìm thấy não chữ (vector_db)"

    # 3. Load DB Text (BỎ LOAD ẢNH Ở ĐÂY)
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        return db_text, "OK"
    except Exception as e: return None, str(e)

# Gọi hàm load
db_text, status = load_brain_engine_safe()
if status != "OK": st.error(f"Lỗi: {status}"); st.stop()

# =====================================================
# 3. QUẢN LÝ USER & GIỚI HẠN (GIỮ NGUYÊN 100%)
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
# --- BỔ SUNG MỚI: Biến đếm số lần hỏi linh tinh ---
if "bad_attempts" not in st.session_state: 
    st.session_state.bad_attempts = 0  # Đếm số thẻ phạt
if "is_blocked" not in st.session_state: 
    st.session_state.is_blocked = False # Trạng thái bị khóa

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

# --- THANH ĐẾM LƯỢT (Bác cần cái này đây) ---
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
                
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử...<br>
                            Liên hệ Admin để nhận mã kích hoạt:
                        </p>
                        <a href="https://zalo.me/84963759566" target="_blank" 
                           style="display: inline-block; width: 100%; background-color: #009688; 
                                  color: white; padding: 12px 0; border-radius: 30px; 
                                  text-decoration: none; font-weight: bold; margin: 15px 0;">
                           💬 Nhận mã kích hoạt qua Zalo
                        </a>
                    </div>
                """, unsafe_allow_html=True)

                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    if st.form_submit_button("Đăng Nhập Ngay"):
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Thành công!")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("❌ Sai thông tin")
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

# Upsell Dictionary
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","đau lưng","gối","đau gối","cột sống","thoát vị","thoát vị đĩa đệm","tim mạch","tim","huyết áp","cao huyết áp","hạ huyết áp","tuần hoàn","mạch máu","đau ngực","suy nhược"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","tập sai","lỗi sai","sai kỹ thuật","kỹ thuật","đúng kỹ thuật","chỉnh tư thế","canh chỉnh","căn chỉnh","hướng dẫn","định tuyến","quy trình","trình tự","bước thực hiện","chuẩn hóa","tối ưu","hiệu chỉnh","điều chỉnh","sửa lỗi","khắc phục"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress","căng thẳng","áp lực","lo âu","bất an","mệt mỏi tinh thần","ngủ","giấc ngủ","mất ngủ","ngủ sâu","ngủ không ngon","nghỉ ngơi","thiền","thiền định","chánh niệm","tĩnh tâm","an trú","thở","hít thở","điều hòa hơi thở"]}
}
# =====================================================
# HÀM XỬ LÝ AI (TỐI ƯU & CHẶN SPAM)
# =====================================================
def get_ai_response(prompt, context_text, history_context):
    try:
        # 1. Cấu hình Model cứng (Không lặp list_models để tránh lỗi và chậm)
        generation_config = {
            "temperature": 0.5,
            "max_output_tokens": 1000,
        }
        model = genai.GenerativeModel('models/gemini-1.5-flash', generation_config=generation_config)

        # 2. System Prompt Chặt chẽ (Cơ chế thẻ phạt)
        sys_prompt = f"""
        BẠN LÀ CHUYÊN GIA YOGA & TRỊ LIỆU.
        
        QUY TẮC QUAN TRỌNG NHẤT:
        - Nhiệm vụ duy nhất: Trả lời về Yoga, Sức khỏe, Giải phẫu học, Thiền, Dinh dưỡng tập luyện.
        - Nếu câu hỏi KHÔNG LIÊN QUAN đến các chủ đề trên (ví dụ: xổ số, chính trị, code, tình yêu, hỏi thời tiết...), hãy trả lời duy nhất cụm từ: REFUSE_TOPIC
        
        DỮ LIỆU TRA CỨU (RAG):
        {context_text}
        
        LỊCH SỬ CHAT:
        {history_context}
        
        CÂU HỎI HIỆN TẠI: "{prompt}"
        
        YÊU CẦU TRẢ LỜI:
        - Nếu liên quan Yoga: Trả lời ngắn gọn, có tâm, dùng HTML format đẹp.
        - Nếu dùng thông tin từ nguồn RAG: Ghi chú [Ref: ID].
        """
        
        response = model.generate_content(sys_prompt)
        return response.text.strip()
        
    except Exception as e:
        # Trả về lỗi cụ thể để mình biết đường sửa
        return f"ERR_SYS: {str(e)}"

# =====================================================
# 6. XỬ LÝ CHAT (ĐÃ TỐI ƯU: BLOCK SPAM + HIỆN LỖI RÕ RÀNG)
# =====================================================

# 1. Kiểm tra xem có bị khóa mõm không trước khi cho chat
if st.session_state.is_blocked:
    st.error("🚫 TÀI KHOẢN TẠM KHÓA: Hệ thống phát hiện bạn hỏi sai chủ đề quá 3 lần. Vui lòng tải lại trang (F5) để bắt đầu lại.")
    st.stop() # Dừng luôn, không hiện ô chat nữa

if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    # Hiển thị câu hỏi User
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id) # Trừ lượt dùng

    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            
            # --- A. Chuẩn bị dữ liệu ---
            # Lấy lịch sử chat (3 câu gần nhất)
            chat_history_context = ""
            recent_msgs = st.session_state.messages[-7:-1] 
            for msg in recent_msgs:
                role_txt = "User" if msg["role"] == "user" else "Bot"
                clean_content = re.sub(r'<[^>]*>', '', msg["content"]).strip()
                chat_history_context += f"{role_txt}: {clean_content}\n"

            # Tìm kiếm RAG (Giữ nguyên logic cũ của bạn)
            context_text = ""
            source_map = {}
            try:
                docs = db_text.similarity_search(prompt, k=4) # Giảm xuống k=4 cho nhanh
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    source_map[doc_id] = {"url": d.metadata.get('url', '#'), "title": d.metadata.get('title', 'Nguồn')}
                    context_text += f"\n[Nguồn {doc_id}]: {d.metadata.get('title')}\nNội dung: {d.page_content}\n"
            except Exception as search_err:
                st.warning(f"Lỗi tìm kiếm database: {search_err}")

            # --- B. Gọi AI & Xử lý Spam ---
            ai_raw = get_ai_response(prompt, context_text, chat_history_context)

            # --- C. Kiểm tra Spam ---
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                remaining = 3 - st.session_state.bad_attempts
                
                if st.session_state.bad_attempts >= 3:
                    st.session_state.is_blocked = True
                    msg_block = "🚫 **CẢNH BÁO:** Bạn đã hỏi sai chủ đề 3 lần. Hệ thống sẽ tạm khóa. Vui lòng F5."
                    st.markdown(msg_block)
                    st.session_state.messages.append({"role": "assistant", "content": msg_block})
                    st.stop() # Dừng chương trình ngay lập tức
                else:
                    msg_warn = f"⚠️ **Nhắc nhở:** Tôi chỉ là trợ lý Yoga thôi ạ. Vui lòng tập trung vào sức khỏe. (Vi phạm: {st.session_state.bad_attempts}/3)"
                    st.markdown(msg_warn)
                    st.session_state.messages.append({"role": "assistant", "content": msg_warn})
            
            # --- D. Xử lý Lỗi Hệ thống ---
            elif ai_raw.startswith("ERR_SYS:"):
                # In lỗi cụ thể ra để bạn debug
                real_error = ai_raw.replace("ERR_SYS:", "")
                st.error(f"❌ Hệ thống gặp lỗi: {real_error}")
                st.info("💡 Mẹo: Hãy thử F5 lại trang hoặc kiểm tra API Key.")
            
            # --- E. Trả lời thành công ---
            else:
                # Xử lý Link Ref (Giữ nguyên code cũ của bạn)
                def replace_ref(match):
                    ref_id = int(match.group(1))
                    if ref_id in source_map:
                        info = source_map[ref_id]
                        if info['url'] and info['url'] != '#':
                            return f" <a href='{info['url']}' target='_blank' class='ref-link' title='{info['title']}'>[{ref_id}]</a>"
                    return "" 
                
                final_html = re.sub(r'\[Ref:?\s*(\d+)\]', replace_ref, ai_raw)
                
                # Render
                st.markdown(final_html, unsafe_allow_html=True)
                
                # 7. Upsell (Bán hàng)
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div style='margin-top:15px'>"
                    for r in recs[:2]:
                        upsell_html += f"""<div style="background:#e0f2f1; padding:8px; border-radius:8px; margin-bottom:5px; border:1px solid #009688; display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:bold; color:#004d40; font-size:13px">{r['name']}</span><a href="{r['url']}" target="_blank" style="background:#00796b; color:white; padding:4px 8px; border-radius:12px; text-decoration:none; font-size:11px; font-weight:bold;">Xem ngay</a></div>"""
                    upsell_html += "</div>"
                    st.markdown(upsell_html, unsafe_allow_html=True)

                # Lưu vào lịch sử
                st.session_state.messages.append({"role": "assistant", "content": final_html + upsell_html})

            except Exception as e:
                st.error("Hệ thống đang bận. Vui lòng thử lại sau.")

            st.markdown('<div class="disclaimer-text">Trợ lý AI có thể mắc sai sót, hãy kiểm chứng thông tin.</div>', unsafe_allow_html=True)
