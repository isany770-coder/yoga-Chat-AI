import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import re
import time
import uuid
import pandas as pd # Thêm thư viện này để xử lý bảng
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Ẩn Header/Footer */
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}

    /* Khung chat */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Banner Upsell */
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
    
    /* Link tham khảo */
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 8px; border-radius: 12px; margin: 0 2px;
        font-size: 0.85em; border: 1px solid #b2dfdb; display: inline-flex; align-items: center; gap: 4px;
    }
    .ref-link:hover { background: #b2dfdb; transform: translateY(-1px); }
    
    /* Upsell Box */
    .upsell-box {
        background: linear-gradient(135deg, #f1f8e9 0%, #dcedc8 100%);
        padding: 12px; border-radius: 12px; margin-top: 15px;
        border: 1px solid #aed581; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .upsell-btn {
        background-color: #33691e; color: white !important; padding: 6px 15px;
        border-radius: 20px; text-decoration: none; font-size: 13px; font-weight: bold;
        float: right; margin-top: -2px;
    }

    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. DỮ LIỆU UPSELL
# =====================================================
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình Trị Liệu 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","gối","cột sống","thoát vị","tim mạch","huyết áp","mất ngủ","cổ vai gáy","pain","therapy","recovery","back","knee","spine","herniated","heart","blood pressure","insomnia"]},
    "AI_COACH": {"name": "🤖 AI Coach Chỉnh Tư Thế", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","định tuyến","chỉnh dáng","hướng dẫn","căn chỉnh","bắt đầu","correct","form","alignment","technique","guide"]},
    "KHOA_HOC": {"name": "🎓 Khóa Đào Tạo HLV", "url": "https://yogaismylife.vn/dao-tao-hlv/", "key": ["huấn luyện viên","dạy yoga","bằng cấp","chứng chỉ","nghề yoga","teacher","training","certification","career"]}
}

# =====================================================
# 3. KẾT NỐI DATA & LOAD NÃO
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except: st.error("❌ Thiếu cấu hình secrets.toml"); st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            if not os.path.exists("/tmp"): os.makedirs("/tmp")
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            
            with st.spinner(f"Đang tải bộ não Yoga (690MB)..."):
                url = f'https://drive.google.com/uc?id={file_id}'
                gdown.download(url, ZIP_PATH, quiet=False, fuzzy=True)
            
            if not zipfile.is_zipfile(ZIP_PATH): return None, "Lỗi file ZIP"

            with st.spinner("Đang giải nén tri thức..."):
                with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            os.remove(ZIP_PATH)
        except Exception as e: return None, f"Lỗi tải: {str(e)}"
    
    def find_db_path(name):
        for r, d, f in os.walk(EXTRACT_PATH):
            if name in d and "index.faiss" in os.listdir(os.path.join(r, name)): return os.path.join(r, name)
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Không thấy vector_db"

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
        db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
        return db_text, "OK"
    except Exception as e: return None, str(e)

with st.spinner("Đang khởi động hệ thống..."):
    data_result, status = load_brain_engine_safe()
if status != "OK": st.error(status); st.stop()
db_text = data_result

# =====================================================
# 4. HÀM AI THÔNG MINH (Đa ngôn ngữ + Số liệu)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        ADMIN_NAME = "An Nguyễn" 
        WEBSITE = "yogaismylife.vn"
        PROFILE_LINK = "https://yogaismylife.vn/nguoi-sang-lap-hanh-trinh-tao-nen-yogaismylife-vn/"
        
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        data_instruction = "Dữ liệu tra cứu bên dưới."
        if not context_text.strip():
            data_instruction = "Không tìm thấy tài liệu. Dùng kiến thức chuyên gia để trả lời."
        
        science_priority = ""
        if "[LOẠI: BẰNG CHỨNG KHOA HỌC]" in context_text:
            science_priority = """
            ‼️ QUAN TRỌNG: Đã tìm thấy NGHIÊN CỨU KHOA HỌC.
            - Bắt buộc trích dẫn nghiên cứu (Nếu có).
            - Ưu tiên lấy CON SỐ, TỈ LỆ %, THỜI GIAN cụ thể.
            """

        sys_prompt = f"""
        ROLE: World-class Medical Yoga Expert for **{WEBSITE}** (Admin: {ADMIN_NAME}).
        
        🌍 **LANGUAGE INSTRUCTION:**
        - DETECT user language. IF English -> Reply English. IF Vietnamese -> Reply Vietnamese.

        MINDSET:
        1. Speak with EVIDENCE. Use facts from [DATA].
        2. Be concise (max 300 words). Use bullet points.
        
        PRIORITY:
        1. [DATA] (Science/Expert QA) is #1 source.
        2. Always cite sources as [Ref: ID].
        
        DATA STATUS: {data_instruction}
        {science_priority}
        
        [DATA]:
        {context_text}

        [HISTORY]:
        {history_context}

        QUESTION: "{prompt}"
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e: return f"ERR_SYS: {str(e)}"

# =====================================================
# 5. DATABASE & LOGGING (QUẢN LÝ USER + LỊCH SỬ CHAT)
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Bảng đếm lượt
    c.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    # Bảng lưu lịch sử chat (MỚI)
    c.execute('CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, timestamp DATETIME, question TEXT, answer TEXT)')
    conn.commit(); conn.close()
init_db()

def check_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    r = c.fetchone(); conn.close()
    return r[0] if r else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

# Hàm lưu lịch sử chat
def save_chat_log(user_id, question, answer):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Chỉ lưu text thuần túy, bỏ html
        clean_answer = re.sub(r'<[^>]*>', '', answer) 
        c.execute("INSERT INTO chat_logs (user_id, timestamp, question, answer) VALUES (?, ?, ?, ?)", (user_id, ts, question, clean_answer))
        conn.commit(); conn.close()
    except: pass

if "user_id" not in st.session_state: st.session_state.user_id = str(uuid.uuid4())[:8]
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga Y Khoa. Bạn cần hỗ trợ gì?"}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id
used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 6. SIDEBAR ADMIN (XEM LỊCH SỬ CHAT)
# =====================================================
with st.sidebar:
    st.title("🔐 Admin Panel")
    
    if st.session_state.authenticated:
        st.success(f"Hi Admin: {st.session_state.username}")
        
        # --- MODULE GIÁM SÁT ---
        st.markdown("---")
        st.subheader("🕵️‍♂️ Thám tử Yoga")
        if st.checkbox("Xem ai đang hỏi gì?"):
            try:
                conn = sqlite3.connect(DB_PATH)
                # Lấy 50 tin nhắn gần nhất
                df = pd.read_sql_query("SELECT timestamp, user_id, question, answer FROM chat_logs ORDER BY id DESC LIMIT 50", conn)
                conn.close()
                st.dataframe(df)
                
                # Nút tải về
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Tải Lịch Sử Chat (CSV)", csv, "yoga_chat_history.csv", "text/csv")
            except Exception as e:
                st.error("Chưa có dữ liệu chat.")

        if st.button("Đăng xuất"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai mật khẩu")

percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;"><div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;"><span>⚡ {used}/{LIMIT}</span><div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;"><div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div></div></div></div>""", unsafe_allow_html=True)

# Màn hình hết hạn
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
                st.markdown("""<div style="text-align: center;"><h3 style="color: #00897b;">LIMIT REACHED!</h3><p>Contact Admin for VIP Access:</p><a href="https://zalo.me/84963759566" target="_blank" style="display:inline-block;background:#009688;color:white;padding:10px 20px;border-radius:20px;text-decoration:none;">💬 Contact Zalo</a></div>""", unsafe_allow_html=True)
                with st.form("login_form_limit"):
                    u = st.text_input("User"); p = st.text_input("Password", type="password")
                    if st.form_submit_button("Login"):
                        if st.secrets["passwords"].get(u) == p: st.session_state.authenticated = True; st.session_state.username = u; st.session_state.hide_limit_modal = True; st.rerun()
                        else: st.error("Wrong info")
        st.stop()

# =====================================================
# 7. XỬ LÝ CHAT CHÍNH
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Special Offer: Yoga Mats + VIP Account 30% OFF!</div><a href="https://yogaismylife.vn/cua-hang/" class="promo-btn">Shop Now</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if st.session_state.is_blocked: st.error("🚫 BLOCKED / TÀI KHOẢN BỊ KHÓA"); st.stop()

if prompt := st.chat_input("Ask a question..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                chat_history += f"{msg['role']}: {re.sub(r'<[^>]*>', '', msg['content'])}\n"

            # 1. Tìm kiếm
            context_text = ""
            source_map = {}
            try:
                docs = db_text.similarity_search(prompt, k=6)
                if docs:
                    for i, d in enumerate(docs):
                        idx = i + 1
                        meta = d.metadata
                        doc_type = meta.get('type', 'general').upper()
                        type_label = "LOẠI: BẰNG CHỨNG KHOA HỌC" if 'SCIENCE' in doc_type else ("LOẠI: CHUYÊN GIA TƯ VẤN" if 'QA' in doc_type else "LOẠI: TỪ ĐIỂN")
                        link = meta.get('url') or meta.get('source') or '#'
                        title = meta.get('title') or f"Source {idx}"
                        source_map[idx] = {"url": link, "title": title, "type": doc_type}
                        context_text += f"\n[Ref: {idx}] [{type_label}] (Source: {title}):\n{d.page_content}\n"
            except: pass

            # 2. Gọi AI
            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            # 3. Hiển thị & Lưu log
            final_content_to_show = ""
            
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3: st.session_state.is_blocked = True; msg = "🚫 BLOCKED."
                else: msg = f"⚠️ I only answer Yoga & Health questions. (Warning {st.session_state.bad_attempts}/3)"
                st.markdown(msg)
                final_content_to_show = msg
                if st.session_state.is_blocked: st.stop()
            
            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"Error: {ai_raw}")
                final_content_to_show = f"Error: {ai_raw}"
            else:
                ref_ids = [int(m) for m in re.findall(r'\[Ref:?\s*(\d+)\]', ai_raw)]
                clean_text = re.sub(r'\[Ref:?\s*(\d+)\]', '', ai_raw).strip()
                split_patterns = ["Nguồn tham khảo", "Tài liệu tham khảo", "References", "Sources", "📚 Tài liệu", "📚 Nguồn"]
                for p in split_patterns:
                    if p in clean_text: clean_text = clean_text.split(p)[0].strip(); break

                unique_sources = {}
                for rid in ref_ids:
                    if rid in source_map:
                        src = source_map[rid]
                        if src['url'] != '#': unique_sources[src['url']] = src

                sources_html = ""
                if unique_sources:
                    sources_html += "\n\n---\n**📚 References & Scientific Evidence:**\n\n"
                    science_links, expert_links, other_links = [], [], []
                    for url, info in unique_sources.items():
                        title = info['title']
                        link_md = f"[{title}]({url})"
                        if 'SCIENCE' in info['type']: science_links.append(f"- 🧪 **Study:** {link_md}")
                        elif 'QA' in info['type']: expert_links.append(f"- 🚑 **Expert QA:** {link_md}")
                        else: other_links.append(f"- 🔗 {link_md}")
                    sources_html += "\n".join(science_links + expert_links + other_links)

                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div class='upsell-box'><b>💡 Recommended Solutions:</b><br>"
                    for r in recs[:2]:
                        upsell_html += f"""<div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;"><span style="color:#33691e; font-weight:500">👉 {r['name']}</span><a href="{r['url']}" target="_blank" class="upsell-btn">View</a></div>"""
                    upsell_html += "</div>"
                
                final_content_to_show = clean_text
                st.markdown(final_content_to_show, unsafe_allow_html=True)
                if sources_html: st.markdown(sources_html)
                if upsell_html: st.markdown(upsell_html, unsafe_allow_html=True)

                # Lưu vào DB Log (QUAN TRỌNG)
                save_chat_log(current_user, prompt, final_content_to_show) # <--- GHI LẠI LỊCH SỬ
                
                # Lưu vào session để hiển thị lại khi F5
                final_content_to_show = final_content_to_show + "\n" + sources_html + "\n" + upsell_html

            if final_content_to_show:
                st.session_state.messages.append({"role": "assistant", "content": final_content_to_show})
