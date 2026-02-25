import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import re
import time
import uuid
import gc
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
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}
    
    /* ---------------------------------------------------- */
    /* SỬA LỖI 1: Bắt buộc bẻ gãy các link dài trên Mobile */
    /* ---------------------------------------------------- */
    a, .stMarkdown a {
        word-wrap: break-word !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;
    }
    
    /* ---------------------------------------------------- */
    /* SỬA LỖI 2: Nâng ô chat lên cao hơn (bottom: 35px)    */
    /* ---------------------------------------------------- */
    div[data-testid="stChatInput"] {
        bottom: 35px !important; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Dòng cảnh báo Disclaimer ở đáy màn hình */
    .disclaimer-text {
        position: fixed; bottom: 5px; left: 0; right: 0;
        font-size: 11px; color: #888; z-index: 999; width: 100%; text-align: center;
        font-family: sans-serif; 
        pointer-events: none; /* Thêm cái này để lỡ bấm nhầm vào chữ nó xuyên qua luôn, ko bị kẹt */
    }
    
    /* Banner Welcome xịn sò */
    .welcome-banner {
        background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
        padding: 12px 15px; margin-bottom: 20px; border-radius: 12px;
        text-align: center; color: #2c3e50; font-size: 15px; font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;
    }
    
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
    .bottom-spacer { height: 130px; } /* Tăng khoảng đệm để cuộn xuống không bị che text */
</style>

<div class="disclaimer-text">
    AI can make mistakes. Verify medical information with a healthcare professional.
</div>
""", unsafe_allow_html=True)

# =====================================================
# 2. CẤU HÌNH ADMIN & UPSELL
# =====================================================
ADMIN_PROFILE = {
    "name": "YIML Assistant",
    "role": "Medical Yoga Expert",
    "certs": "Certified by Dr. Pham Van Quan",
    "contact": "Zalo (+84) 963.759.566",
    "mission": "Empowering the community with evidence-based yoga and medical science.",
}

BLOCKED_KEYWORDS = ["xổ số", "lô đề", "đánh bạc", "sex", "khiêu dâm", "chính trị", "phản động", "code python", "lập trình", "viết code"]

YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình Trị Liệu 8 Bước (8-Step Therapy)", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","gối","cột sống","thoát vị","tim mạch","huyết áp","mất ngủ","cổ vai gáy","pain","therapy","recovery","back","knee","spine","herniated"]},
    "AI_COACH": {"name": "🤖 AI Coach Chỉnh Tư Thế (Posture Correction)", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","định tuyến","chỉnh dáng","hướng dẫn","căn chỉnh","bắt đầu","correct","form","alignment","technique"]},
    "KHOA_HOC": {"name": "🎓 Khóa Đào Tạo HLV (Teacher Training)", "url": "https://yogaismylife.vn/dao-tao-hlv/", "key": ["huấn luyện viên","dạy yoga","bằng cấp","chứng chỉ","nghề yoga","teacher","training","certification"]}
}

# =====================================================
# 3. KẾT NỐI DATA & DATABASE
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Missing configuration in secrets.toml"); st.stop()

ZIP_PATH = "/tmp/brain_data_v6.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v6"
DB_PATH = "user_usage.db"

# --- A. DATABASE & BLACKLIST ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    c.execute('CREATE TABLE IF NOT EXISTS blacklist (user_id TEXT PRIMARY KEY, reason TEXT, timestamp TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, timestamp TEXT, prompt TEXT)')
    conn.commit(); conn.close()
init_db()

def check_ban_status(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT reason FROM blacklist WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close()
    return row[0] if row else None

def ban_user_forever(user_id, reason="Policy Violation"):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        now = str(datetime.datetime.now())
        c.execute("INSERT OR REPLACE INTO blacklist (user_id, reason, timestamp) VALUES (?, ?, ?)", (user_id, reason, now))
        conn.commit(); conn.close()
    except Exception as e: pass

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

def log_user_prompt(user_id, prompt):
    """Âm thầm lưu câu hỏi của khách vào DB"""
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO chat_logs (user_id, timestamp, prompt) VALUES (?, ?, ?)", (user_id, now, prompt))
        conn.commit(); conn.close()
    except Exception as e: pass

# --- B. LOAD AI ENGINE ---
@st.cache_resource
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            if not os.path.exists("/tmp"): os.makedirs("/tmp")
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            
            with st.spinner("Downloading database..."):
                url = f'https://drive.google.com/uc?id={file_id}'
                gdown.download(url, ZIP_PATH, quiet=True, fuzzy=True)
            
            if not zipfile.is_zipfile(ZIP_PATH): return None, "ZIP file error"

            with st.spinner("Extracting data..."):
                with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            os.remove(ZIP_PATH); gc.collect()
        except Exception as e: return None, str(e)
    
    def find_db_path(folder):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if folder in dirs and "index.faiss" in os.listdir(os.path.join(root, folder)):
                return os.path.join(root, folder)
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Database not found"

    try:
        with st.spinner("Initializing AI Engine..."):
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
            db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
            gc.collect()
        return db_text, "OK"
    except Exception as e: return None, str(e)

db_text, status = load_brain_engine_safe()
if status != "OK": st.error(f"Data Error: {status}"); st.stop()

# =====================================================
# 4. HÀM AI THÔNG MINH (BẢN 5.0: SẠCH BÓNG REF, TRỰC DIỆN)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        for kw in BLOCKED_KEYWORDS:
            if kw in prompt.lower(): return "VIOLATION_DETECTED"

        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        sys_prompt = f"""
        🛑 **SECURITY PROTOCOL:**
        - Input: "{prompt}"
        - Check: If user asks about Lottery, Gambling, Sex, Politics -> REPLY EXACTLY: "VIOLATION_DETECTED".

        ROLE: You are **{ADMIN_PROFILE['name']}**, the official Medical Yoga Expert for YogaIsMyLife.vn.

        🌍 **LANGUAGE RULE:**
        - User asks in VN -> Reply 100% in VN.
        - User asks in EN -> Reply 100% in EN. Translate ALL data into English.

        🎯 **EVIDENCE RULES (CRITICAL):**
        1. Extract ONLY the scientific studies explicitly present in the [DATA]. If there is only 1, list exactly 1. DO NOT invent or add any studies.
        2. SOURCE URL RULE (STRICT): 
           - Find "Link gốc:" or "DOI:" in the text and copy the exact URL.
           - FATAL ERROR: NEVER output any link containing "yogaismylife.vn" or ".vn" in the Scientific Evidence section.
           - If not found, print exactly: "Đang xác minh".
        3. Write naturally without [Ref: x] tags.

        🛠️ **MANDATORY RESPONSE FORMAT:**

        **[IF USER ASKS IN ENGLISH]**
        [Warm greeting and direct answer].

        🧠 **The Science Behind It**
        [Explain mechanisms using bullet points based on the data].

        📚 **Scientific Evidence**
        * 📘 **Study:** [Study Title / Document Name]
            * *Result:* [Result/Key Point]
            * *Source:* [Insert exact raw URL or "Verification In Progress"]
        *(List 1-3 items here. Follow the source URL rule exactly.)*

        💡 **Expert Advice**
        [Actionable advice].

        **[IF USER ASKS IN VIETNAMESE]**
        [Lời chào ấm áp và câu trả lời trực diện].

        🧠 **Góc nhìn Khoa học & Cơ chế**
        [Giải thích cơ chế bằng các gạch đầu dòng tự nhiên].

        📚 **Bằng chứng Y khoa**
        * 📘 **Nghiên cứu:** [Tên tài liệu]
            * *Kết quả:* [Điểm chính]
            * *Nguồn:* [Copy chính xác raw link. Cấm tuyệt đối link .vn]
        *(Chỉ liệt kê các nghiên cứu có thật trong DATA, tuyệt đối không tự bịa thêm).*

        💡 **Lời khuyên từ Chuyên gia**
        [Đưa ra lời khuyên thực tế. Nhắc nhở yoga là liệu pháp bổ trợ].

        --------------------------------------------------
        [DATA (CONTEXT)]:
        {context_text}

        [HISTORY]:
        {history_context}

        USER QUESTION: "{prompt}"
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e: return f"ERR_SYS: {str(e)}"

# =====================================================
# 5. QUẢN LÝ SESSION
# =====================================================
try:
    qp = st.query_params
    url_uid = qp.get("uid", None)
except:
    url_uid = None

if "user_id" not in st.session_state:
    if url_uid: st.session_state.user_id = url_uid
    else:
        new_uid = str(uuid.uuid4())[:8]
        st.session_state.user_id = new_uid
        try: st.query_params["uid"] = new_uid
        except: pass

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Hello! I am **{ADMIN_PROFILE['name']}**. How can I assist you with your health and yoga practice today?"}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id

ban_reason = check_ban_status(current_user)
if ban_reason:
    st.error(f"🚫 **ACCOUNT BLOCKED / TÀI KHOẢN ĐÃ BỊ KHÓA**\n\nReason: {ban_reason}\n\nContact Admin: {ADMIN_PROFILE['contact']}")
    st.stop()

used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 30
is_limit_reached = used >= LIMIT

# =====================================================
# 6. GIAO DIỆN SIDEBAR
# =====================================================
with st.sidebar:
    st.title("🔐 VIP Access")
    
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        
        if st.session_state.username == "admin_yiml": 
            import pandas as pd
            if st.button("👁️ Xem lịch sử khách hỏi"):
                st.markdown("### 🕵️ Hồ sơ Chat")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    df = pd.read_sql_query("SELECT timestamp, prompt, user_id FROM chat_logs ORDER BY id DESC LIMIT 50", conn)
                    st.dataframe(df, use_container_width=True)
                    conn.close()
                except Exception as e: st.error("Chưa có data!")

        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Wrong password")
    
    st.markdown("---")
    with st.expander("👨‍⚕️ About the Expert", expanded=True):
        st.markdown(f"**{ADMIN_PROFILE['name']}** *({ADMIN_PROFILE['role']})*\n\n🎖️ {ADMIN_PROFILE['certs']}\n\n💬 **{ADMIN_PROFILE['contact']}**\n\n> *\"{ADMIN_PROFILE['mission']}\"*")

percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""
<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;">
    <div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;">
        <span>⚡ {used}/{LIMIT}</span>
        <div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# =====================================================
# 7. GIAO DIỆN HẾT HẠN
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
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">LIMIT REACHED!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">Bạn đã sử dụng hết lượt hỏi hôm nay.<br><i>You have reached your daily limit.</i></p>
                    </div>
                """, unsafe_allow_html=True)
        st.stop()

# =====================================================
# 8. XỬ LÝ CHAT CHÍNH
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="welcome-banner">✨ Welcome to YIML Pro • Evidence-Based Medical Yoga Assistant</div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)
st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if prompt := st.chat_input(f"Ask {ADMIN_PROFILE['name']} about yoga & health / Hỏi về yoga và bệnh lý..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)
    log_user_prompt(current_user, prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing medical databases / Đang tra cứu hồ sơ y khoa..."):
            
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            context_text = ""
            try:
                docs = db_text.similarity_search(prompt, k=6)
                if docs:
                    for i, d in enumerate(docs):
                        meta = d.metadata
                        doi_raw = str(meta.get('doi', '')).strip()
                        url_raw = str(meta.get('url', meta.get('source', ''))).strip()
                        
                        final_link = "Đang xác minh"
                        if doi_raw and doi_raw not in ["", "None", "#"] and ".vn" not in doi_raw:
                            final_link = doi_raw
                        elif url_raw and url_raw not in ["", "None", "#"] and ".vn" not in url_raw:
                            final_link = url_raw
                            
                        title = meta.get('title_vi') or meta.get('title_en') or meta.get('title') or f"Tài liệu {i+1}"
                        
                        # KIỂM DUYỆT CỨNG: Xóa sạch mọi link .vn trong nội dung để chặn AI đọc trộm
                        clean_content = d.page_content
                        clean_content = re.sub(r'https?://[^\s]*\.vn[^\s]*', '', clean_content)
                        clean_content = re.sub(r'yogaismylife\.vn[^\s]*', '', clean_content)
                        
                        context_text += f"\n--- TÀI LIỆU {i+1} ---\nTên: {title}\nLink Y Khoa: {final_link}\nNội dung:\n{clean_content}\n"
            except: pass

            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)
            final_content = ""
            
            if ai_raw == "VIOLATION_DETECTED":
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    ban_user_forever(current_user, "Spam/Policy Violation")
                    st.session_state.is_blocked = True
                    msg = f"🚫 **ACCOUNT BLOCKED**\n\nID {current_user} has been permanently restricted."
                else:
                    msg = f"⚠️ **WARNING ({st.session_state.bad_attempts}/3)**\n\nPlease only ask about Health, Anatomy, and Yoga."
                st.markdown(msg); final_content = msg
                if st.session_state.is_blocked: time.sleep(3); st.rerun()

            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"System Error: {ai_raw}"); final_content = "Sorry, system error."

            else:
                # TRƯỜNG HỢP THÀNH CÔNG: Chữ sạch sẽ nguyên chất, KHÔNG RÁC
                clean_text = ai_raw.strip()

                # Bắt bóc ngôn ngữ thông minh
                vn_chars = "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ"
                is_vietnamese = any(char in prompt.lower() for char in vn_chars)

                # Cục Gợi ý Giải Pháp (CHỈ HIỂN THỊ NẾU LÀ TIẾNG VIỆT)
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs and is_vietnamese:
                    upsell_html += "<div class='upsell-box'><b>💡 Giải pháp gợi ý từ Chuyên gia:</b><br>"
                    for r in recs[:2]:
                        upsell_html += f"""<div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;"><span style="color:#33691e; font-weight:500">👉 {r['name']}</span><a href="{r['url']}" target="_blank" class="upsell-btn">Xem</a></div>"""
                    upsell_html += "</div>"
                
                st.markdown(clean_text, unsafe_allow_html=True)
                if upsell_html: st.markdown(upsell_html, unsafe_allow_html=True)
                
                final_content = clean_text + "\n" + upsell_html

            if final_content:
                st.session_state.messages.append({"role": "assistant", "content": final_content})
